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

    def _query_openalex(self, topic, results_per_page=10):
        print(f"Querying OpenAlex for topic: {topic}")
        url = f"https://api.openalex.org/works?search={topic}&per_page={results_per_page}"
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
            return sources
        except requests.exceptions.RequestException as e:
            print(f"Error querying OpenAlex: {e}")
            return []

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

    def _query_google_search(self, topic, num_results=10):
        print(f"Querying Google Search for topic: {topic}")
        try:
            results = self.tavily.search(query=topic, search_depth="advanced", max_results=num_results)
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
            return sources
        except Exception as e:
            print(f"Error querying Google Search: {e}")
            return []

    def rerank_and_filter_sources(self, sources, topic, k=10):
        print("Reranking and filtering sources...")
        if not sources:
            return []

        for source in sources:
            # Simple relevance score based on abstract
            score = 0
            if source.get('abstract'):
                if topic.lower() in source['abstract'].lower():
                    score += 1
            # Recency score
            if source.get('year'):
                try:
                    year_diff = 2025 - int(source['year'])
                    if year_diff < 5:
                        score += 2 # High score for recent papers
                    elif year_diff < 10:
                        score += 1
                except (ValueError, TypeError):
                    pass # Ignore if year is not a valid integer
            # Citation score (for academic sources)
            if source.get('citations'):
                if source['citations'] > 100:
                    score += 3
                elif source['citations'] > 20:
                    score += 2
            # Authority score (for web sources)
            if source.get('source') == 'Web Search' and any(domain in source.get('url', '') for domain in ['.gov', '.edu', 'nature.com', 'science.org']):
                score += 2
            source['relevance_score'] = score

        # Sort by relevance score, then by citations/recency as a tie-breaker
        sorted_sources = sorted(sources, key=lambda x: x.get('relevance_score', 0), reverse=True)
        return sorted_sources[:k]

    def retrieve(self, topic, k=10):
        cached_results = self.redis_client.get(f"rag:{topic}")
        if cached_results:
            print(f"Retrieving from cache for topic: {topic}")
            return json.loads(cached_results)

        print("---GATHERING SOURCES---")
        all_sources = []
        all_sources.extend(self._query_openalex(topic))
        all_sources.extend(self._query_google_search(topic))

        print("---RERANKING AND FILTERING---")
        high_quality_sources = self.rerank_and_filter_sources(all_sources, topic, k=k)

        if high_quality_sources:
            self.redis_client.setex(f"rag:{topic}", 604800, json.dumps(high_quality_sources))

        return high_quality_sources

if __name__ == '__main__':
    retriever = RetrieverAgent()
    # sources = retriever.retrieve("impact of AI on scientific research")
    # for s in sources:
    #     print(f"Title: {s.get('title')}, Score: {s.get('relevance_score')}, Source: {s.get('source')}")