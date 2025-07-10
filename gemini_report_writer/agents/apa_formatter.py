from pydantic import BaseModel, Field
from typing import List, Optional

class APAReference(BaseModel):
    """Represents a single APA-formatted reference entry."""
    authors: List[str] = Field(..., description="List of authors' last names and initials.")
    year: str = Field(..., description="Year of publication.")
    title: str = Field(..., description="Title of the work.")
    source: str = Field(..., description="Journal, book, or source of the work.")
    doi: Optional[str] = Field(None, description="Digital Object Identifier, if available.")

class FormattedReport(BaseModel):
    """The final, formatted report with inline citations and a reference list."""
    report_text: str = Field(..., description="The main body of the report, with inline APA citations.")
    references: List[APAReference] = Field(..., description="A list of all sources cited in the report, formatted in APA style.")

class APAFormatterAgent:
    def __init__(self):
        pass

    def _format_inline_citation(self, source_info):
        authors = source_info.get("authors", [])
        year = source_info.get("year", "n.d.")

        if not authors:
            return "(n.d.)"
        
        # APA style for inline citations
        if len(authors) == 1:
            return f"({authors[0]}, {year})"
        elif len(authors) == 2:
            return f"({authors[0]} & {authors[1]}, {year})"
        else:
            return f"({authors[0]} et al., {year})"

    def _format_apa_reference_entry(self, ref: APAReference) -> str:
        authors_list = ref.authors
        if not authors_list:
            authors_formatted = "Unknown Author"
        elif len(authors_list) == 1:
            authors_formatted = authors_list[0]
        elif len(authors_list) == 2:
            authors_formatted = f"{authors_list[0]} & {authors_list[1]}"
        else:
            authors_formatted = f"{authors_list[0]} et al."

        title_formatted = ref.title
        source_formatted = ref.source
        doi_formatted = f"DOI: {ref.doi}" if ref.doi else ""

        return f"{authors_formatted} ({ref.year}). {title_formatted}. {source_formatted}. {doi_formatted}".strip()

    def format_report(self, raw_content: str, sources: list) -> FormattedReport:
        """
        Takes raw report content and source information, and returns a
        structured report with inline citations and an APA reference list.

        Args:
            raw_content: The text of the report from the WriterAgent.
            sources: A list of dictionaries, where each dictionary represents a source.

        Returns:
            A FormattedReport object containing the final report and reference list.
        """
        # This is a placeholder implementation for inline citation placement.
        # A sophisticated model would intelligently place citations.
        # For now, we'll just append a generic one or replace placeholders.
        
        report_with_citations = raw_content
        
        # Replace placeholders like [Source 1] with actual inline citations
        for i, source_info in enumerate(sources):
            placeholder = f"[Source {i+1}]"
            inline_citation = self._format_inline_citation(source_info)
            report_with_citations = report_with_citations.replace(placeholder, inline_citation)

        references = []
        for source in sources:
            authors = [author for author in source.get("authors", []) if author]
            if not authors:
                authors = ["Unknown Author"]

            references.append(APAReference(
                authors=authors,
                year=str(source.get("year", "n.d.")), # Convert year to string
                title=source.get("title") or "Untitled",
                source=source.get("source", "Unpublished"),
                doi=source.get("doi")
            ))
        
        # Sort references alphabetically by the first author's last name
        references.sort(key=lambda x: x.authors[0].split(',')[0].strip().lower() if x.authors else '')

        return FormattedReport(
            report_text=report_with_citations,
            references=references
        )