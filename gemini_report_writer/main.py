import os
import argparse
import hashlib
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from agents.planner import PlannerAgent
from agents.critic import CriticAgent
from agents.researcher import ResearcherAgent
from agents.writer import WriterAgent
from agents.retriever import RetrieverAgent
from agents.apa_formatter import APAFormatterAgent, FormattedReport
from agents.citation_verifier import CitationVerifierAgent
from agents.grammar_gate import GrammarGateAgent
from agents.quality_controller import QualityControllerAgent

class AgentState(TypedDict):
    topic: str
    outline: List[str]
    critique: str
    research_plan: str
    research_results: Dict[str, str] # Store research results per section
    report: str
    formatted_report: FormattedReport
    feedback: str
    outline_revisions: int
    report_revisions: int
    sources: List[str]
    citation_revisions: int
    current_section: str # Track the current section being researched
    section_index: int # Track the index of the current section
    skipped_sections: List[Dict] # Track sections that were skipped due to quality issues

class ReportWorkflow:
    def __init__(self):
        self.planner = PlannerAgent()
        self.critic = CriticAgent()
        self.researcher = ResearcherAgent()
        self.writer = WriterAgent()
        self.retriever = RetrieverAgent()
        self.apa_formatter = APAFormatterAgent()
        self.citation_verifier = CitationVerifierAgent()
        self.grammar_gate = GrammarGateAgent()
        self.quality_controller = QualityControllerAgent()

    def run(self, topic):
        initial_state = {
            "topic": topic,
            "outline": [],
            "critique": "",
            "research_plan": "",
            "research_results": {},
            "report": "",
            "formatted_report": None,
            "feedback": "",
            "outline_revisions": 0,
            "report_revisions": 0,
            "sources": [],
            "citation_revisions": 0,
            "current_section": "",
            "section_index": 0,
            "skipped_sections": [],
        }

        workflow = StateGraph(AgentState)

        workflow.add_node("planner", self.plan)
        workflow.add_node("critic_outline", self.critique_outline)
        workflow.add_node("research_section", self.research_section)
        workflow.add_node("writer", self.write)
        workflow.add_node("apa_formatter", self.format_report)
        workflow.add_node("citation_verifier", self.verify_citations)
        workflow.add_node("critic_report", self.critique_report)
        workflow.add_node("quality_control", self.quality_control)
        workflow.add_node("grammar_gate", self.check_grammar)
        workflow.add_node("human_feedback", self.get_human_feedback)

        workflow.set_entry_point("planner")

        workflow.add_edge("planner", "critic_outline")
        workflow.add_conditional_edges(
            "critic_outline", self.decide_outline, {"continue": "research_section", "revise": "planner"}
        )
        workflow.add_conditional_edges(
            "research_section",
            self.decide_next_section,
            {"continue": "research_section", "end_research": "writer"},
        )
        workflow.add_edge("writer", "apa_formatter")
        workflow.add_edge("apa_formatter", "citation_verifier")
        workflow.add_conditional_edges(
            "citation_verifier",
            self.decide_citation_verification,
            {"continue": "critic_report", "revise": "writer"},
        )
        workflow.add_conditional_edges(
            "critic_report", self.decide_report, {"continue": "quality_control", "revise": "writer"}
        )
        workflow.add_conditional_edges(
            "quality_control", self.decide_quality_control, {"continue": "grammar_gate", "revise": "writer"}
        )
        workflow.add_conditional_edges(
            "grammar_gate", self.decide_grammar, {"continue": "human_feedback", "revise": "writer"}
        )
        workflow.add_conditional_edges(
            "human_feedback", self.decide_human_feedback, {"continue": END, "revise": "writer"}
        )

        app = workflow.compile()
        final_state = app.invoke(initial_state, config={"recursion_limit": 200})

        formatted_report_obj = final_state.get("formatted_report")
        if formatted_report_obj:
            report_text = formatted_report_obj.report_text
            references_list = "\n\nReferences:\n"
            if formatted_report_obj.references:
                for ref in formatted_report_obj.references:
                    authors = ", ".join(ref.authors)
                    references_list += f"- {authors} ({ref.year}). {ref.title}. {ref.source}\n"
            final_report_content = report_text + references_list
            
            # Save the report to a Markdown file
            topic_hash = hashlib.sha256(topic.encode()).hexdigest()[:10]
            report_filename = f"{topic.replace(' ', '_').replace('/', '_')[:50]}_{topic_hash}_report.txt"
            report_filepath = os.path.join(os.getcwd(), report_filename)
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(report_filepath), exist_ok=True)
            
            with open(report_filepath, "w", encoding="utf-8") as f:
                f.write(final_report_content)
            print(f"---FINAL REPORT SAVED TO {report_filepath}---")
            
            return final_report_content
        return "No report generated."

    def plan(self, state: AgentState):
        print("---PLANNING---")
        outline_revisions = state.get("outline_revisions", 0)
        if state.get("critique"):
            outline = self.planner.refine_outline(state["topic"], state["critique"])
        else:
            outline = self.planner.create_outline(state["topic"])
        # The outline is now a list of strings
        outline_list = [section.strip() for section in outline.split('\n') if section.strip()]
        return {"outline": outline_list, "outline_revisions": outline_revisions + 1}

    def critique_outline(self, state: AgentState):
        print("---CRITIQUING OUTLINE---")
        critique = self.critic.critique_outline("\n".join(state["outline"]))
        return {"critique": critique}

    def decide_outline(self, state: AgentState):
        if state["outline_revisions"] > 5:
            print("---OUTLINE REVISION LIMIT REACHED, PROCEEDING ANYWAY---")
            return "continue"
        if state["critique"].startswith("APPROVED"):
            return "continue"
        return "revise"

    def research_section(self, state: AgentState):
        section_index = state.get("section_index", 0)
        current_section = state["outline"][section_index]
        main_topic = state["topic"]
        print(f"---RESEARCHING SECTION: {current_section}---")
        
        # Retrieve sources for the current section
        sources = self.retriever.retrieve(f"{main_topic}: {current_section}")
        
        # Validate research feasibility before proceeding
        validation = self.researcher.validate_research_feasibility(current_section, sources, main_topic)
        
        if not validation['feasible']:
            print(f"⚠️  SKIPPING SECTION: {validation['reason']}")
            print(f"   Recommendation: {validation['recommendation']}")
            
            # Track skipped sections
            skipped_sections = state.get("skipped_sections", [])
            skipped_sections.append({
                'section': current_section,
                'reason': validation['reason'],
                'recommendation': validation['recommendation']
            })
            
            return {
                "research_results": state.get("research_results", {}),
                "sources": state.get("sources", []),
                "section_index": section_index + 1,
                "current_section": current_section,
                "skipped_sections": skipped_sections
            }
        
        print(f"✓ Research feasible: {validation.get('source_count', 0)} sources, avg relevance: {validation.get('quality_score', 0):.2f}")
        
        # Conduct research for the current section with topic context
        research_result = self.researcher.conduct_research(current_section, sources, main_topic)
        
        # Update the research results
        current_results = state.get("research_results", {})
        
        if research_result.get('skipped'):
            print(f"⚠️  RESEARCH DECLINED: {research_result['reason']}")
            skipped_sections = state.get("skipped_sections", [])
            skipped_sections.append({
                'section': current_section,
                'reason': research_result['reason'],
                'recommendation': research_result.get('recommendation', 'skip_section')
            })
            
            return {
                "research_results": current_results,
                "sources": state.get("sources", []),
                "section_index": section_index + 1,
                "current_section": current_section,
                "skipped_sections": skipped_sections
            }
        else:
            # Store successful research with quality metrics
            current_results[current_section] = {
                'content': research_result['content'],
                'quality_metrics': research_result.get('quality_metrics', {}),
                'source_count': research_result.get('source_count', 0)
            }
            print(f"✓ Research completed: {research_result.get('source_count', 0)} sources used")
        
        # Update all sources gathered so far (only from successful research)
        all_sources = state.get("sources", [])
        all_sources.extend(sources)
        # Remove duplicates
        # Convert lists to tuples for hashability before creating a set
        def make_hashable(obj):
            if isinstance(obj, dict):
                return frozenset({k: make_hashable(v) for k, v in obj.items()}.items())
            elif isinstance(obj, list):
                return tuple(make_hashable(elem) for elem in obj)
            else:
                return obj

        unique_sources = [dict(item) for item in {make_hashable(d) for d in all_sources}]

        return {
            "research_results": current_results,
            "sources": unique_sources,
            "section_index": section_index + 1,
            "current_section": current_section,
            "skipped_sections": state.get("skipped_sections", [])
        }

    def decide_next_section(self, state: AgentState):
        if state["section_index"] >= len(state["outline"]):
            return "end_research"
        return "continue"

    def write(self, state: AgentState):
        print("---WRITING---")
        report_revisions = state.get("report_revisions", 0)
        
        # Process research results to extract content and add quality context
        processed_research = {}
        quality_summary = {}
        
        for section, research_data in state["research_results"].items():
            if isinstance(research_data, dict) and 'content' in research_data:
                # New format with quality metrics
                processed_research[section] = research_data['content']
                quality_summary[section] = research_data.get('quality_metrics', {})
            else:
                # Old format - just content string
                processed_research[section] = research_data
                quality_summary[section] = {}
        
        # Check for completely empty report scenario
        total_sections = len(state.get("outline", []))
        completed_sections = len(processed_research)
        skipped_sections = state.get("skipped_sections", [])
        skipped_count = len(skipped_sections)
        
        if completed_sections == 0 and total_sections > 0:
            # No sections could be researched - create a minimal report explaining the situation
            print("⚠️  WARNING: No sections could be researched due to insufficient quality sources!")
            report = f"""# Report Generation Failed: Insufficient Quality Sources

## Summary
This report could not be generated for the topic "{state['topic']}" due to insufficient high-quality, relevant sources for all planned sections.

## Attempted Sections
{total_sections} sections were planned but all {skipped_count} were skipped:

""" + "\\n".join([f"- **{s['section']}**: {s['reason']}" for s in skipped_sections]) + f"""

## Recommendations
1. **Refine the topic**: The topic may be too narrow, specialized, or lack recent research
2. **Check spelling**: Ensure the topic is spelled correctly and uses standard terminology
3. **Broaden scope**: Consider expanding the topic to include related areas
4. **Check source availability**: Verify that academic sources exist for this topic

## Research Quality Standards
This system maintains high quality standards by requiring:
- Minimum {self.researcher.minimum_sources_threshold} relevant sources per section
- Minimum {self.researcher.minimum_relevance_threshold:.1f} average relevance score
- Minimum {self.researcher.section_alignment_threshold:.1f} section-topic alignment

*This quality-first approach prevents the generation of inaccurate or irrelevant content.*
"""
            return {"report": report, "report_revisions": report_revisions + 1}
        
        # Include information about skipped sections
        skipped_info = ""
        if skipped_sections:
            skipped_info = f"\\n\\n**Research Quality Note:** {len(skipped_sections)} sections were skipped due to insufficient or irrelevant sources: {[s['section'] for s in skipped_sections]}"
        
        if state.get("feedback"):
            report = self.writer.refine_report(state["report"], state["feedback"], state["sources"])
        else:
            # Pass processed research with quality context
            report = self.writer.write_report(processed_research, state["sources"], quality_summary, skipped_info)
        
        # Log writing statistics
        print(f"📊 Writing Stats: {completed_sections}/{total_sections} sections completed, {skipped_count} skipped")
        
        return {"report": report, "report_revisions": report_revisions + 1}

    def format_report(self, state: AgentState):
        print("---FORMATTING REPORT (APA)---")
        formatted_report = self.apa_formatter.format_report(state["report"], state["sources"])
        return {"formatted_report": formatted_report}

    def verify_citations(self, state: AgentState):
        print("---VERIFYING CITATIONS---")
        citation_revisions = state.get("citation_revisions", 0)
        verification_result = self.citation_verifier.verify_citations(state["formatted_report"].report_text, state["sources"])
        if verification_result.get("needs_revision"):
            return {"feedback": "REVISE: Citations need correction or better support.", "citation_revisions": citation_revisions + 1}
        return {"feedback": "APPROVED: Citations verified.", "citation_revisions": citation_revisions + 1}

    def decide_citation_verification(self, state: AgentState):
        if state["citation_revisions"] > 3:
            print("---CITATION REVISION LIMIT REACHED, PROCEEDING ANYWAY---")
            return "continue"
        if state["feedback"].startswith("APPROVED"):
            return "continue"
        return "revise"

    def critique_report(self, state: AgentState):
        print("---CRITIQUING REPORT---")
        feedback = self.critic.critique_report(state["formatted_report"].report_text)
        return {"feedback": feedback}

    def decide_report(self, state: AgentState):
        if state["report_revisions"] > 5:
            print("---REPORT REVISION LIMIT REACHED, PROCEEDING ANYWAY---")
            return "continue"
        if state["feedback"].startswith("APPROVED"):
            return "continue"
        return "revise"

    def quality_control(self, state: AgentState):
        print("---QUALITY CONTROL ASSESSMENT---")
        report_content = state["formatted_report"].report_text
        sources = state["sources"]
        section_research_results = state.get("research_results", {})
        
        quality_assessment = self.quality_controller.assess_content_quality(
            report_content, sources, section_research_results
        )
        
        print(f"📊 Quality Score: {quality_assessment['overall_score']:.2f}")
        if quality_assessment['needs_revision']:
            print("⚠️  Quality issues detected")
            recommendations = quality_assessment.get('recommendations', [])
            feedback = "REVISE: " + "; ".join(recommendations[:3])  # Top 3 recommendations
        else:
            print("✓ Quality assessment passed")
            feedback = "APPROVED: Quality control passed"
            
        return {"feedback": feedback}

    def decide_quality_control(self, state: AgentState):
        if state["report_revisions"] > 5:
            print("---QUALITY CONTROL REVISION LIMIT REACHED, PROCEEDING ANYWAY---")
            return "continue"
        if state["feedback"].startswith("APPROVED"):
            return "continue"
        return "revise"

    def check_grammar(self, state: AgentState):
        print("---CHECKING GRAMMAR AND STYLE---")
        grammar_check_result = self.grammar_gate.check_grammar_and_style(state["formatted_report"].report_text)
        error_count = grammar_check_result.get("error_count", 0)
        if error_count > 2:
            return {"feedback": f"REVISE: Grammar and style issues found. Errors: {error_count}"}
        return {"feedback": "APPROVED: Grammar and style check passed."}

    def decide_grammar(self, state: AgentState):
        if state["feedback"].startswith("APPROVED"):
            return "continue"
        return "revise"

    def get_human_feedback(self, state: AgentState):
        print("---AWAITING HUMAN FEEDBACK---")
        feedback = "APPROVED"
        print(f"Simulated human feedback: {feedback}")
        return {"feedback": feedback}

    def decide_human_feedback(self, state: AgentState):
        if state["feedback"].strip().upper() == "APPROVED":
            return "continue"
        return "revise"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="The topic for the report.")
    args = parser.parse_args()

    workflow = ReportWorkflow()
    report = workflow.run(args.topic)
    print("---FINAL REPORT---")
    print(report)