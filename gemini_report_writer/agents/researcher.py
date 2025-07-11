from textwrap import dedent
from utils import create_gemini_model

class ResearcherAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="researcher")
        
        # Quality thresholds for research validation
        self.minimum_sources_threshold = 3  # Minimum sources needed for research
        self.minimum_relevance_threshold = 0.5  # Minimum average relevance needed

    def validate_research_feasibility(self, section_title, sources, main_topic):
        """Check if research can be conducted with given sources for the section"""
        if not sources:
            return {
                'feasible': False,
                'reason': 'No sources available',
                'recommendation': 'skip_section'
            }
        
        # Check minimum source count
        if len(sources) < self.minimum_sources_threshold:
            return {
                'feasible': False,
                'reason': f'Insufficient sources: {len(sources)} < {self.minimum_sources_threshold}',
                'recommendation': 'skip_section'
            }
        
        # Check source relevance quality
        relevance_scores = [s.get('topic_relevance', 0.0) for s in sources]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        
        if avg_relevance < self.minimum_relevance_threshold:
            return {
                'feasible': False,
                'reason': f'Low source relevance: {avg_relevance:.2f} < {self.minimum_relevance_threshold}',
                'recommendation': 'skip_section'
            }
        
        # Additional topic-section coherence check
        section_relevance = self._assess_section_topic_alignment(section_title, main_topic, sources)
        
        if section_relevance < 0.6:
            return {
                'feasible': False,
                'reason': f'Section-topic misalignment: {section_relevance:.2f} < 0.6',
                'recommendation': 'skip_section'
            }
        
        return {
            'feasible': True,
            'quality_score': avg_relevance,
            'source_count': len(sources),
            'section_relevance': section_relevance
        }
    
    def _assess_section_topic_alignment(self, section_title, main_topic, sources):
        """Assess how well the section aligns with the main topic given available sources"""
        # Create a summary of available source content
        source_summaries = []
        for source in sources[:5]:  # Limit to top 5 sources to avoid context overflow
            title = source.get('title', '')
            abstract = source.get('abstract', '')[:200]  # Truncate long abstracts
            source_summaries.append(f"- {title}: {abstract}")
        
        sources_summary = "\n".join(source_summaries)
        
        prompt = f"""
        Assess the alignment between this section and the main topic based on available sources.
        
        Main Topic: {main_topic}
        Section Title: {section_title}
        
        Available Sources:
        {sources_summary}
        
        Rate the alignment on a scale of 0.0 to 1.0:
        - 1.0 = Perfect alignment, sources strongly support this section for the topic
        - 0.8 = Good alignment, sources adequately support this section
        - 0.6 = Moderate alignment, some useful content available
        - 0.4 = Weak alignment, limited relevant content
        - 0.2 = Poor alignment, minimal relevant content
        - 0.0 = No alignment, sources don't support this section
        
        Consider:
        - Do the sources contain information relevant to both the section AND main topic?
        - Can a meaningful section be written from these sources?
        - Is there enough substantive content to justify including this section?
        
        Respond with only the numerical score (e.g., 0.7):
        """
        
        try:
            response = self.model.invoke(prompt)
            score = float(response.content.strip())
            return max(0.0, min(1.0, score))
        except Exception as e:
            print(f"Error assessing section alignment: {e}")
            return 0.5  # Default to moderate alignment if assessment fails
    
    def conduct_research(self, section_title, sources, main_topic=None):
        """Conduct focused research with quality validation"""
        # First validate if research is feasible
        if main_topic:
            validation = self.validate_research_feasibility(section_title, sources, main_topic)
            if not validation['feasible']:
                return {
                    'content': f"[SECTION SKIPPED: {validation['reason']}]",
                    'skipped': True,
                    'reason': validation['reason'],
                    'recommendation': validation['recommendation']
                }
        
        formatted_sources = []
        for i, source in enumerate(sources):
            title = source.get('title', 'N/A')
            abstract = source.get('abstract', 'N/A')
            doi = source.get('doi', 'N/A')
            authors_list = [author for author in source.get('authors', []) if author]
            authors = ", ".join(authors_list) if authors_list else "N.A."
            year = source.get('year', 'N.A.')
            relevance = source.get('topic_relevance', 'N/A')
            formatted_sources.append(f"Source {i+1}:\nTitle: {title}\nAbstract: {abstract}\nDOI: {doi}\nAuthors: {authors}\nYear: {year}\nRelevance Score: {relevance}\n---")
        sources_text = "\n".join(formatted_sources)
        
        quality_note = ""
        if main_topic:
            avg_relevance = sum(s.get('topic_relevance', 0) for s in sources) / len(sources)
            quality_note = f"\n\n**Research Quality Context:**\n- {len(sources)} sources available\n- Average relevance score: {avg_relevance:.2f}\n- Main topic: {main_topic}"
        
        prompt = dedent(f"""
            You are an expert researcher. Your task is to synthesize information for the following section of a report:

            **Section Title:** {section_title}
            **Main Topic Context:** {main_topic or 'Not specified'}

            IMPORTANT GUIDELINES:
            1. Only use information that is DIRECTLY relevant to both the section title AND the main topic
            2. If sources don't contain adequate information for this specific section, acknowledge the limitation
            3. Focus on quality over quantity - better to have a concise, accurate section than a long, irrelevant one
            4. Explicitly cite sources and mention when information is corroborated by multiple sources
            5. If you cannot find sufficient relevant information, state this clearly

            Based on the provided sources, synthesize information for this section. Be very explicit about which source (by Source number) supports which claim. Ensure all claims are grounded in the provided sources and relevant to the section topic.

            **Provided Sources:**
            {sources_text}{quality_note}
        """)
        
        research_content = self.model.invoke(prompt).content
        
        return {
            'content': research_content,
            'skipped': False,
            'source_count': len(sources),
            'quality_metrics': {
                'avg_relevance': sum(s.get('topic_relevance', 0) for s in sources) / len(sources) if sources else 0,
                'source_count': len(sources)
            }
        }

    def refine_research(self, research_plan, critique, sources, main_topic=None):
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