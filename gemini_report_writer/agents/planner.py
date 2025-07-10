from textwrap import dedent
from utils import create_gemini_model

class PlannerAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="planner")

    def create_outline(self, topic):
        prompt = dedent(f"""
            You are an expert planner specializing in academic and policy reports on economics.
            Your task is to create a detailed, well-structured outline for a report on the following topic:

            **Topic:** {topic}

            The outline should include:
            1.  **Introduction:** State the research question, hypothesis, and thesis statement clearly.
            2.  **Literature Review:** Identify key themes, debates, and gaps in the existing literature.
            3.  **Methodology:** Describe the research methods, data sources, and analytical techniques in detail.
            4.  **Analysis:** Outline the main analytical sections, the arguments to be developed, and the evidence to be used.
            5.  **Conclusion:** Summarize the findings, discuss policy implications, and suggest areas for future research.
            6.  **References:** A list of at least 5-10 key academic and policy sources.

            Please provide a comprehensive and logically flowing outline that is ready for a critic's review.
        """)
        return self.model.invoke(prompt).content

    def refine_outline(self, topic, critique):
        prompt = dedent(f"""
            You are an expert planner. You have received the following critique on your initial outline for a report on **{topic}**.

            **Critique:**
            {critique}

            Please revise the outline to address all the points in the critique. Be specific and ensure the new outline is more robust, comprehensive, and directly responds to the feedback provided. The revised outline should be a significant improvement over the previous version.
        """)
        return self.model.invoke(prompt).content