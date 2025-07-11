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
    
    def _validate_topic_relevance_batch(self, sources, original_topic):
        """Use LLM to validate multiple sources in a single call for better performance"""
        if not sources:
            return {}
            
        # Prepare batch validation prompt
        source_summaries = []
        for i, source in enumerate(sources):
            title = source.get('title', 'No title')
            abstract = source.get('abstract', 'No abstract')
            # Limit abstract length to prevent context overflow
            abstract = abstract[:300] + "..." if len(abstract) > 300 else abstract
            source_summaries.append(f"Source {i+1}:\nTitle: {title}\nAbstract: {abstract}")
        
        sources_text = "\n---\n".join(source_summaries)
        
        prompt = f"""
        Evaluate the relevance of these sources to the topic: "{original_topic}"
        
        Rate each source on a scale of 0.0 to 1.0 where:
        - 1.0 = Directly addresses the topic with substantial content
        - 0.8 = Highly relevant with significant overlap  
        - 0.6 = Moderately relevant with some useful content
        - 0.4 = Tangentially related
        - 0.2 = Minimal relevance
        - 0.0 = No relevance or completely off-topic
        
        Consider for each source:
        - Does the content directly address the topic?
        - Are the key concepts and terminology aligned?
        - Would this source provide valuable information for the topic?
        
        IMPORTANT: Respond with ONLY a JSON object mapping source numbers to scores:
        {{"1": 0.8, "2": 0.2, "3": 0.9, "4": 0.0, "5": 0.7}}
        
        Sources to evaluate:
        {sources_text}
        
        JSON Response:
        """
        
        try:
            response = self.model.invoke(prompt)
            score_text = response.content.strip()
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', score_text, re.DOTALL)
            if json_match:
                scores_dict = json.loads(json_match.group())
                # Convert string keys to integers and validate scores
                validated_scores = {}
                for key, score in scores_dict.items():
                    try:
                        idx = int(key) - 1  # Convert to 0-based index
                        if 0 <= idx < len(sources):
                            validated_scores[idx] = max(0.0, min(1.0, float(score)))
                    except (ValueError, TypeError):
                        continue
                return validated_scores
            else:
                print("Warning: Could not parse JSON response from batch validation")
                return {}
                
        except Exception as e:
            print(f"Error in batch validation: {e}")
            return {}
    
    def _validate_topic_relevance(self, source, original_topic):
        """Fallback method for single source validation"""
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
        """Intelligent reranking and filtering using batch LLM-based relevance validation"""
        print("Validating and reranking sources with batch LLM validation...")
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
        
        # Batch validate topic relevance for better performance
        batch_scores = self._validate_topic_relevance_batch(unique_sources, original_topic)
        
        # If batch validation failed, fallback to individual validation
        if not batch_scores:
            print("Batch validation failed, falling back to individual validation...")
            batch_scores = {}
            for i, source in enumerate(unique_sources):
                batch_scores[i] = self._validate_topic_relevance(source, original_topic)
        
        # Calculate quality scores and apply dynamic thresholding
        scored_sources = []
        for i, source in enumerate(unique_sources):
            topic_relevance = batch_scores.get(i, 0.0)
            
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
            scored_sources.append(source)
        
        # Sort by quality score first
        sorted_sources = sorted(scored_sources, key=lambda x: x.get('quality_score', 0), reverse=True)
        
        # Dynamic thresholding: adjust threshold based on available sources
        current_threshold = self.relevance_threshold
        validated_sources = []
        
        for threshold in [0.7, 0.5, 0.3, 0.1]:  # Progressive fallback thresholds
            validated_sources = [s for s in sorted_sources if s.get('topic_relevance', 0) >= threshold]
            
            if len(validated_sources) >= min(k, 5):  # Ensure we have at least 5 sources or k sources
                print(f"Using threshold {threshold:.1f} - found {len(validated_sources)} relevant sources")
                break
            elif threshold == 0.1:
                print(f"⚠️  Warning: Only {len(validated_sources)} sources meet minimum relevance threshold")
                break
        
        # Log acceptance/rejection
        for source in sorted_sources[:k*2]:  # Show top 2k sources for debugging
            relevance = source.get('topic_relevance', 0)
            quality = source.get('quality_score', 0)
            title = source.get('title', 'No title')[:60]
            
            if source in validated_sources:
                print(f"✓ Accepted: {title}... (relevance: {relevance:.2f}, quality: {quality:.1f})")
            else:
                print(f"✗ Rejected: {title}... (relevance: {relevance:.2f}, quality: {quality:.1f})")
        
        final_sources = validated_sources[:k]
        print(f"Selected {len(final_sources)} high-quality, topic-relevant sources from {len(sources)} candidates")
        
        # Performance logging
        if len(batch_scores) > 0:
            print(f"📊 Performance: Used 1 batch LLM call instead of {len(unique_sources)} individual calls")
        
        return final_sources

    def retrieve(self, topic, k=10):
        # Extract just the core topic for caching (remove section-specific info)
        core_topic = topic.split(':')[0].strip() if ':' in topic else topic
        cache_key = f"rag:{core_topic}"
        
        cached_results = self.redis_client.get(cache_key)
        if cached_results:
            print(f"Retrieving from cache for topic: {core_topic}")
            cached_data = json.loads(cached_results)
            
            # Handle both old and new cache formats
            if isinstance(cached_data, dict) and 'sources' in cached_data:
                # New cache format with metadata
                cached_sources = cached_data['sources']
                cache_age = self.redis_client.time()[0] - float(cached_data.get('cached_at', 0))
                print(f"Cache age: {cache_age/3600:.1f} hours, method: {cached_data.get('validation_method', 'unknown')}")
            else:
                # Old cache format - just the sources list
                cached_sources = cached_data
                
            # Re-validate cached sources for the specific topic/section if needed
            # Since we now cache with relevance scores, we can reuse them for most cases
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

        # Cache the validated sources with relevance scores (only if we found quality sources)
        if high_quality_sources:
            # Cache all scored sources for potential reuse with different sections
            # Include relevance scores to avoid re-validation
            sources_with_scores = [s for s in all_sources if 'topic_relevance' in s and 'quality_score' in s]
            if sources_with_scores:
                # Create cache object with metadata
                cache_data = {
                    'sources': sources_with_scores,
                    'core_topic': core_topic,
                    'cached_at': self.redis_client.time()[0],  # Unix timestamp
                    'validation_method': 'batch'  # We now use batch validation by default
                }
                self.redis_client.setex(cache_key, 604800, json.dumps(cache_data))
                print(f"Cached {len(sources_with_scores)} validated sources with relevance scores for future use")
        else:
            print("⚠️  WARNING: No high-quality sources found for this topic!")
            print("This may indicate the topic is too narrow, misspelled, or lacks recent research.")

        return high_quality_sources

if __name__ == '__main__':
    retriever = RetrieverAgent()
    # sources = retriever.retrieve("impact of AI on scientific research")
    # for s in sources:
    #     print(f"Title: {s.get('title')}, Score: {s.get('relevance_score')}, Source: {s.get('source')}")