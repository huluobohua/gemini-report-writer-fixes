
from textwrap import dedent
from utils import create_gemini_model

class WriterAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="writer", temperature=0.7)

    def write_report(self, research_results, sources, temperature=0.0):
        """Generates the full report from section-specific research.
        Leaves specific APA formatting to the APAFormatterAgent.
        """
        report_sections = []
        for section_title, section_content in research_results.items():
            prompt = dedent(f"""
                You are an expert academic writer. Your task is to write a single, cohesive section of a larger report. The section you are writing is titled: **{section_title}**.

                You must base your writing *entirely* on the provided research content for this section.

                **Research Content for '{section_title}':**
                {section_content}

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
