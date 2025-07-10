
from textwrap import dedent
from utils import create_gemini_model

class CriticAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="critic")

    def critique_outline(self, outline):
        prompt = dedent(f"""
            You are an expert critic. Your task is to provide a constructive and actionable critique of the following report outline.

            **Outline:**
            {outline}

            Focus on:
            -   **Clarity and Coherence:** Is the structure logical? Is the research question, hypothesis, and thesis statement clear and well-defined?
            -   **Completeness:** Are there any missing sections or key points? Is the literature review comprehensive? Is the methodology sufficiently detailed?
            -   **Feasibility:** Is the scope of the report realistic for a standard academic or policy paper?

            If the outline is well-structured and comprehensive, start your response with "APPROVED".
            Otherwise, start your response with "REVISE" and provide specific, numbered points of feedback. Each point should be a clear and actionable suggestion for improvement.
        """)
        return self.model.invoke(prompt).content

    def critique_research(self, research_plan, research_results):
        prompt = dedent(f"""
            You are an expert critic. You need to verify if the research results align with the research plan.

            **Research Plan:**
            {research_plan}

            **Research Results:**
            {research_results}

            Does the research adequately address all aspects of the plan? Are the sources credible and academic? Is the information relevant and sufficient to support the planned analysis?

            If the research is sufficient and well-aligned with the plan, start your response with "APPROVED".
            Otherwise, start with "REVISE" and provide specific feedback on what needs to be improved, added, or clarified.
        """)
        return self.model.invoke(prompt).content

    def critique_report(self, report):
        prompt = dedent(f"""
            You are an expert critic. Critique the following draft report.

            **Report:**
            {report}

            Focus on:
            -   **Argumentation:** Is the central argument clear, consistent, and well-supported by the evidence?
            -   **Evidence:** Is the evidence used effectively, interpreted correctly, and cited properly?
            -   **Clarity and Style:** Is the report well-written, logically structured, and easy to understand for the target audience?

            If the report is ready for publication, start your response with "APPROVED".
            Otherwise, start with "REVISE" and provide specific, actionable feedback for improvement.
        """)
        return self.model.invoke(prompt).content
