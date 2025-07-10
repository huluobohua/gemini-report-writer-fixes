import json
import os
import requests
import redis
from utils import create_gemini_model
from tavily import TavilyClient

class RetrieverAgent:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
        self.model = create_gemini_model(agent_role="retriever")
        self.tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        
        # Topic relevance threshold for filtering sources
        self.relevance_threshold = 0.7

    def _generate_core_queries(self, topic):
        """Generate focused, topic-specific queries for better source retrieval"""
        prompt = f"""
        Generate 3-5 focused search queries for the topic: "{topic}"
        
        Requirements:
        - Each query should target different aspects of the topic
        - Use specific academic and technical terminology
        - Include synonyms and related concepts
        - Avoid overly broad or generic terms
        - Format as a JSON list of strings
        
        Example for "machine learning":
        ["machine learning algorithms", "artificial intelligence neural networks", "deep learning models", "supervised learning techniques"]
        
        Topic: {topic}
        Queries:
        """
        
        try:
            response = self.model.invoke(prompt)
            queries_text = response.content.strip()
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', queries_text, re.DOTALL)
            if json_match:
                queries = json.loads(json_match.group())
                return queries[:5]  # Limit to 5 queries
            else:
                # Fallback to original topic if parsing fails
                return [topic]
        except Exception as e:
            print(f"Error generating queries: {e}")
            return [topic]
    
    def _validate_topic_relevance(self, source, original_topic):
        """Use LLM to validate if a source is relevant to the original topic"""
        title = source.get('title', '')
        abstract = source.get('abstract', '')
        
        if not title and not abstract:
            return 0.0
        
        prompt = f"""
        Evaluate the relevance of this source to the topic: "{original_topic}"
        
        Source Title: {title}
        Source Abstract: {abstract[:500]}...
        
        Rate the relevance on a scale of 0.0 to 1.0 where:
        - 1.0 = Directly addresses the topic with substantial content
        - 0.8 = Highly relevant with significant overlap
        - 0.6 = Moderately relevant with some useful content
        - 0.4 = Tangentially related
        - 0.2 = Minimal relevance
        - 0.0 = No relevance or completely off-topic
        
        Consider:
        - Does the content directly address the topic?
        - Are the key concepts and terminology aligned?
        - Would this source provide valuable information for the topic?
        
        Respond with only the numerical score (e.g., 0.8):
        """
        
        try:
            response = self.model.invoke(prompt)
            score_text = response.content.strip()
            score = float(score_text)
            return max(0.0, min(1.0, score))  # Clamp between 0.0 and 1.0
        except Exception as e:
            print(f"Error validating relevance: {e}")
            return 0.0  # Default to irrelevant if validation fails

    def _query_openalex(self, queries, results_per_page=10):
        """Query OpenAlex with multiple focused queries"""
        all_sources = []
        for query in queries:
            print(f"Querying OpenAlex for query: {query}")
            url = f"https://api.openalex.org/works?search={query}&per_page={results_per_page}"
            headers = {
                'User-Agent': 'gemini-report-writer/1.0 (mailto:gemini-report-writer-support@example.com)'
            }
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                sources = []
                for work in data.get('results', [])[:results_per_page]: # Limit results
                    doi = work.get('doi')
                    if doi and doi.startswith("https://doi.org/"):
                        doi = doi[len("https://doi.org/"):]

                    abstract_inverted_index = work.get('abstract_inverted_index')
                    abstract = ""
                    if abstract_inverted_index:
                        words = [(word, idx) for word, indices in abstract_inverted_index.items() for idx in indices]
                        words.sort(key=lambda x: x[1])
                        abstract = " ".join([word for word, idx in words])

                    authors = [author.get('display_name') for author in work.get('authorships', []) if author.get('display_name')]
                    year = work.get('publication_year')
                    citations = work.get('cited_by_count', 0)

                    primary_location = work.get('primary_location') or {}
                    source_info = primary_location.get('source') or {}
                    journal_name = source_info.get('display_name')

                    biblio = work.get('biblio') or {}
                    first_page = biblio.get('first_page')
                    last_page = biblio.get('last_page')
                    pages = f"{first_page}-{last_page}" if first_page and last_page else None

                    sources.append({
                        "title": work.get('title'),
                        "abstract": abstract,
                        "doi": doi,
                        "source": "OpenAlex",
                        "authors": authors,
                        "year": year,
                        "journal": journal_name,
                        "citations": citations,
                        "url": work.get('id')
                    })
                all_sources.extend(sources)
            except requests.exceptions.RequestException as e:
                print(f"Error querying OpenAlex for query '{query}': {e}")
                continue
        
        return all_sources

    def _extract_author_with_llm(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            content = response.text
            prompt = f"""Please extract the author's name from the following web page content. The author might be an individual or an organization. If no author is explicitly mentioned, state 'No Author Specified'.

            Content:
            {content[:4000]}

            Author:"""
            author_response = self.model.invoke(prompt)
            return author_response.content.strip()
        except requests.exceptions.RequestException as e:
            print(f"Could not fetch URL {url} for author extraction: {e}")
            return "No Author Specified"
        except Exception as e:
            print(f"An error occurred during author extraction with LLM: {e}")
            return "No Author Specified"

    def _query_google_search(self, queries, num_results=10):
        """Query Google Search with multiple focused queries"""
        all_sources = []
        for query in queries:
            print(f"Querying Google Search for query: {query}")
            try:
                results = self.tavily.search(query=query, search_depth="advanced", max_results=num_results)
                sources = []
                for res in results.get('results', [])[:num_results]: # Limit results
                    author = res.get('author')
                    if not author:
                        author = self._extract_author_with_llm(res.get('url'))

                    sources.append({
                        "title": res.get('title'),
                        "abstract": res.get('content'),
                        "url": res.get('url'),
                        "source": "Web Search",
                        "authors": [author], # Ensure it's a list
                        "year": res.get('published_date', '').split('-')[0] if res.get('published_date') else "n.d."
                    })
                all_sources.extend(sources)
            except Exception as e:
                print(f"Error querying Google Search for query '{query}': {e}")
                continue
        
        return all_sources

    def rerank_and_filter_sources(self, sources, original_topic, k=10):
        """Intelligent reranking and filtering using LLM-based relevance validation"""
        print("Validating and reranking sources with LLM...")
        if not sources:
            return []

        # Remove duplicates based on title and URL
        seen = set()
        unique_sources = []
        for source in sources:
            identifier = (source.get('title', ''), source.get('url', ''), source.get('doi', ''))
            if identifier not in seen:
                seen.add(identifier)
                unique_sources.append(source)
        
        print(f"Processing {len(unique_sources)} unique sources for relevance validation...")
        
        # Validate topic relevance for each source
        validated_sources = []
        for source in unique_sources:
            topic_relevance = self._validate_topic_relevance(source, original_topic)
            
            # Only include sources that meet the relevance threshold
            if topic_relevance >= self.relevance_threshold:
                # Calculate comprehensive quality score
                quality_score = topic_relevance * 10  # Base score from relevance
                
                # Recency bonus
                if source.get('year'):
                    try:
                        year_diff = 2025 - int(source['year'])
                        if year_diff < 3:
                            quality_score += 3  # Very recent
                        elif year_diff < 5:
                            quality_score += 2  # Recent
                        elif year_diff < 10:
                            quality_score += 1  # Moderately recent
                    except (ValueError, TypeError):
                        pass
                
                # Citation authority bonus (for academic sources)
                if source.get('citations'):
                    if source['citations'] > 500:
                        quality_score += 4  # Highly cited
                    elif source['citations'] > 100:
                        quality_score += 3
                    elif source['citations'] > 20:
                        quality_score += 2
                
                # Source authority bonus
                url = source.get('url', '')
                if any(domain in url for domain in ['.gov', '.edu', 'nature.com', 'science.org', 'ieee.org', 'acm.org']):
                    quality_score += 3
                elif any(domain in url for domain in ['arxiv.org', 'pubmed.ncbi.nlm.nih.gov']):
                    quality_score += 2
                
                source['topic_relevance'] = topic_relevance
                source['quality_score'] = quality_score
                validated_sources.append(source)
                print(f"✓ Accepted: {source.get('title', 'No title')[:60]}... (relevance: {topic_relevance:.2f}, quality: {quality_score:.1f})")
            else:
                print(f"✗ Rejected: {source.get('title', 'No title')[:60]}... (relevance: {topic_relevance:.2f} < {self.relevance_threshold})")

        # Sort by quality score (which includes topic relevance)
        sorted_sources = sorted(validated_sources, key=lambda x: x.get('quality_score', 0), reverse=True)
        
        final_sources = sorted_sources[:k]
        print(f"Selected {len(final_sources)} high-quality, topic-relevant sources from {len(sources)} candidates")
        
        return final_sources

    def retrieve(self, topic, k=10):
        # Extract just the core topic for caching (remove section-specific info)
        core_topic = topic.split(':')[0].strip() if ':' in topic else topic
        cache_key = f"rag:{core_topic}"
        
        cached_results = self.redis_client.get(cache_key)
        if cached_results:
            print(f"Retrieving from cache for topic: {core_topic}")
            cached_sources = json.loads(cached_results)
            # Re-validate cached sources for the specific topic/section
            return self.rerank_and_filter_sources(cached_sources, topic, k=k)

        print("---GENERATING FOCUSED QUERIES---")
        queries = self._generate_core_queries(core_topic)
        print(f"Generated {len(queries)} focused queries: {queries}")

        print("---GATHERING SOURCES---")
        all_sources = []
        all_sources.extend(self._query_openalex(queries))
        all_sources.extend(self._query_google_search(queries))
        
        print(f"Gathered {len(all_sources)} total sources from all queries")

        print("---INTELLIGENT FILTERING AND RANKING---")
        high_quality_sources = self.rerank_and_filter_sources(all_sources, topic, k=k)

        # Cache the validated sources (only if we found quality sources)
        if high_quality_sources:
            # Cache the raw sources for potential reuse with different sections
            raw_sources_for_cache = [s for s in all_sources if s.get('topic_relevance', 0) >= self.relevance_threshold]
            if raw_sources_for_cache:
                self.redis_client.setex(cache_key, 604800, json.dumps(raw_sources_for_cache))
                print(f"Cached {len(raw_sources_for_cache)} validated sources for future use")
        else:
            print("⚠️  WARNING: No high-quality sources found for this topic!")
            print("This may indicate the topic is too narrow, misspelled, or lacks recent research.")

        return high_quality_sources

if __name__ == '__main__':
    retriever = RetrieverAgent()
    # sources = retriever.retrieve("impact of AI on scientific research")
    # for s in sources:
    #     print(f"Title: {s.get('title')}, Score: {s.get('relevance_score')}, Source: {s.get('source')}")