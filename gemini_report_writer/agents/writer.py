
from textwrap import dedent
from utils import create_gemini_model

class WriterAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="writer", temperature=0.7)

    def write_report(self, research_results, sources, quality_summary=None, skipped_info="", temperature=0.0):
        """Generates the full report from section-specific research with quality awareness.
        Leaves specific APA formatting to the APAFormatterAgent.
        """
        if quality_summary is None:
            quality_summary = {}
            
        report_sections = []
        
        # Add quality context if there are skipped sections
        if skipped_info:
            report_sections.append(f"**Research Methodology Note:** This report focuses on sections where sufficient high-quality, topic-relevant sources were available. Some planned sections were excluded due to insufficient research materials.{skipped_info}")
        
        for section_title, section_content in research_results.items():
            # Get quality metrics for this section
            section_quality = quality_summary.get(section_title, {})
            source_count = section_quality.get('source_count', 'unknown')
            avg_relevance = section_quality.get('avg_relevance', 'unknown')
            
            quality_context = ""
            if section_quality:
                quality_context = f"\n\n**Quality Context:** This section is based on {source_count} sources with average relevance score of {avg_relevance:.2f}."
            
            prompt = dedent(f"""
                You are an expert academic writer. Your task is to write a single, cohesive section of a larger report. The section you are writing is titled: **{section_title}**.

                You must base your writing *entirely* on the provided research content for this section. Focus on creating a high-quality, academically rigorous section that synthesizes the available information effectively.

                **Research Content for '{section_title}':**
                {section_content}{quality_context}

                IMPORTANT GUIDELINES:
                1. Write only content that is well-supported by the research
                2. If the research content indicates limitations or gaps, acknowledge them appropriately
                3. Focus on quality and accuracy over quantity
                4. Maintain academic rigor and avoid speculation beyond what the sources support

                Write a well-structured, analytical, and comprehensive section. Ensure the prose is continuous, with NO line breaks within paragraphs, and the tone is formal and academic. Do NOT add a title to the section, as it will be added later. When you use information from a source, simply mention the source number, like [Source 1], [Source 2], etc. The formatting of citations and the reference list will be handled by another agent.
            """)
            
            section_text = self.model.invoke(prompt).content
            report_sections.append(f"## {section_title}\n\n{section_text}")

        return "\n\n".join(report_sections)

    def refine_report(self, report, critique, sources):
        """Refines the full report based on feedback.
        This is a simplified refinement process. A more advanced implementation would
        map the critique to specific sections and refine them individually.
        """
        prompt = dedent(f"""
            You are an expert academic writer. You have received the following critique on your report. Please revise the full report to address the feedback.

            **Original Report:**
            {report}

            **Critique:**
            {critique}

            Revise the report to improve its clarity, argumentation, and style. Ensure the prose is continuous, with NO line breaks within paragraphs, and the tone is formal and academic. When you use information from a source, simply mention the source number, like [Source 1], [Source 2], etc. The formatting of citations and the reference list will be handled by another agent.
        """)
        
        revised_content = self.model.invoke(prompt).content
        return revised_content
