
import re
from utils import create_gemini_model

class CitationVerifierAgent:
    def __init__(self, firecrawl_api_key=None):
        self.model = create_gemini_model(agent_role="citation_verifier")

    def extract_dois(self, text):
        dois = re.findall(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', text, re.IGNORECASE)
        return list(set(dois))

    def verify_citations(self, report, cached_sources=None):
        dois = self.extract_dois(report)
        flags = []

        if not cached_sources:
            print("Warning: No cached sources provided for citation verification. Verification will be limited.")

        for doi in dois:
            print(f"Attempting to verify DOI: {doi}")
            matching_source = None
            if cached_sources:
                for source in cached_sources:
                    if source and source.get('doi') == doi:
                        matching_source = source
                        break

            if not matching_source:
                flags.append({"doi": doi, "label": "source_not_found", "message": "DOI not found in cached sources."})
                continue

            source_abstract = matching_source.get('abstract', 'No abstract available.')
            source_title = matching_source.get('title', 'No title available.')

            llm_prompt = f"""
                You are a highly accurate citation verifier. Your task is to determine if the provided report content is supported, disputed, or merely mentioned by the provided source abstract.

                Report Content:
                {report}

                Source Title: {source_title}
                Source Abstract:
                {source_abstract}

                Based on the source abstract, is the report content (specifically any claims that might relate to this source):
                - 'supported' (the abstract explicitly states or strongly implies the claim)
                - 'disputed' (the abstract contradicts the claim)
                - 'mentioned' (the abstract talks about the topic but doesn't directly support or dispute the specific claim)

                Provide only one of these labels as your answer.
            """
            
            try:
                llm_response = self.model.invoke(llm_prompt).content.strip().lower()

                if "supported" in llm_response:
                    flags.append({"doi": doi, "label": "supported"})
                elif "disputed" in llm_response:
                    flags.append({"doi": doi, "label": "disputed"})
                else:
                    flags.append({"doi": doi, "label": "mentioned"})

            except Exception as e:
                print(f"Error verifying DOI {doi} with LLM: {e}")
                flags.append({"doi": doi, "label": "error", "message": str(e)})

        needs_revision = any(flag["label"] != "supported" for flag in flags if flag["label"] != "error" and flag["label"] != "source_not_found")

        return {"status": "completed", "needs_revision": needs_revision, "flags": flags}

if __name__ == '__main__':
    # Example usage (replace with your actual Firecrawl API key)
    # verifier = CitationVerifierAgent(firecrawl_api_key="YOUR_FIRECRAWL_API_KEY")
    # report_text = "This is a report with a claim supported by DOI 10.1000/xyz123. Another claim is here DOI 10.9876/abc456."
    # cached_data = [{'doi': '10.1000/xyz123', 'label': 'supporting'}]
    # result = verifier.verify_citations(report_text, cached_data)
    # print(result)
    pass

if __name__ == '__main__':
    # Example usage (replace with your actual Firecrawl API key)
    # verifier = CitationVerifierAgent(firecrawl_api_key="YOUR_FIRECRAWL_API_KEY")
    # report_text = "This is a report with a claim supported by DOI 10.1000/xyz123. Another claim is here DOI 10.9876/abc456."
    # cached_data = [{'doi': '10.1000/xyz123', 'label': 'supporting'}]
    # result = verifier.verify_citations(report_text, cached_data)
    # print(result)
    pass
