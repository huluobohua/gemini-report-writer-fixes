from textwrap import dedent
from utils import create_gemini_model

class ResearcherAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="researcher")

    def conduct_research(self, section_title, sources):
        formatted_sources = []
        for i, source in enumerate(sources):
            title = source.get('title', 'N/A')
            abstract = source.get('abstract', 'N/A')
            doi = source.get('doi', 'N/A')
            authors_list = [author for author in source.get('authors', []) if author]
            authors = ", ".join(authors_list) if authors_list else "N.A."
            year = source.get('year', 'N.A.')
            formatted_sources.append(f"Source {i+1}:\nTitle: {title}\nAbstract: {abstract}\nDOI: {doi}\nAuthors: {authors}\nYear: {year}\n---")
        sources_text = "\n".join(formatted_sources)
        
        prompt = dedent(f"""
            You are an expert researcher. Your task is to synthesize information for the following section of a report:

            **Section Title:** {section_title}

            Based on the provided sources, answer specific questions related to this section. Explicitly mention when information is corroborated by multiple sources. Provide a concise summary of your findings for this section, including key statistics, arguments, and citations. Ensure all claims are grounded in the provided sources. Be very explicit about which source (by Source number) supports which claim.

            **Provided Sources:**
            {sources_text}
        """)
        return self.model.invoke(prompt).content

    def refine_research(self, research_plan, critique, sources):
        formatted_sources = []
        for i, source in enumerate(sources):
            title = source.get('title', 'N/A')
            abstract = source.get('abstract', 'N/A')
            doi = source.get('doi', 'N/A')
            authors_list = [author for author in source.get('authors', []) if author]
            authors = ", ".join(authors_list) if authors_list else "N.A."
            year = source.get('year', 'N.A.')
            formatted_sources.append(f"Source {i+1}:\nTitle: {title}\nAbstract: {abstract}\nDOI: {doi}\nAuthors: {authors}\nYear: {year}\n---")
        sources_text = "\n".join(formatted_sources)
        
        prompt = dedent(f"""
            You are an expert researcher. You have received the following critique on your research for a specific section.

            **Research Plan (for this section):**
            {research_plan}

            **Critique:**
            {critique}

            **Provided Sources:**
            {sources_text}

            Please refine your research for this section to address the critique. Find additional information from the provided sources, clarify points, and ensure the research is comprehensive. Explicitly mention when information is corroborated by multiple sources. Ensure all claims are grounded in the provided sources. Be very explicit about which source (by Source number) supports which claim.
        """)
        return self.model.invoke(prompt).content