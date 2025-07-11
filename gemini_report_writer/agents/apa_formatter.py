from pydantic import BaseModel, Field
from typing import List, Optional
import re
from utils import create_gemini_model

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
        self.model = create_gemini_model(agent_role="apa_formatter")

    def _extract_year_from_source(self, source_info):
        """Extract year from various source fields using intelligent parsing"""
        # Try direct year field first
        year = source_info.get("year")
        if year and str(year).isdigit() and 1900 <= int(year) <= 2030:
            return str(year)
            
        # Try to extract from URL
        url = source_info.get("url", "")
        if url:
            # Look for 4-digit years in URL
            year_match = re.search(r'\b(20[0-9]{2}|19[0-9]{2})\b', url)
            if year_match:
                return year_match.group(1)
                
        # Try to extract from title or abstract
        for field in ["title", "abstract"]:
            text = source_info.get(field, "")
            if text:
                year_match = re.search(r'\b(20[0-9]{2}|19[0-9]{2})\b', text)
                if year_match:
                    return year_match.group(1)
                    
        return "n.d."
    
    def _improve_author_extraction(self, source_info):
        """Enhanced author extraction with intelligent parsing"""
        authors = source_info.get("authors", [])
        
        # Clean up author list
        cleaned_authors = []
        for author in authors:
            if author and author.strip() and author.strip().lower() not in ["no author specified", "unknown", "n/a", "null"]:
                # Clean up author name format
                cleaned_author = author.strip()
                # Convert "FirstName LastName" to "LastName, F."
                if ", " not in cleaned_author and " " in cleaned_author:
                    parts = cleaned_author.split()
                    if len(parts) >= 2:
                        last_name = parts[-1]
                        first_initial = parts[0][0].upper() if parts[0] else ""
                        cleaned_author = f"{last_name}, {first_initial}."
                cleaned_authors.append(cleaned_author)
                
        # If no good authors found, try to extract from title or source
        if not cleaned_authors:
            # Try to extract organization name from source or URL
            source_name = source_info.get("source", "")
            url = source_info.get("url", "")
            
            if "nature.com" in url:
                cleaned_authors = ["Nature Publishing Group"]
            elif "ieee.org" in url:
                cleaned_authors = ["IEEE"]
            elif "acm.org" in url:
                cleaned_authors = ["ACM"]
            elif ".gov" in url:
                cleaned_authors = ["Government Source"]
            elif ".edu" in url:
                cleaned_authors = ["Academic Institution"]
            elif source_name and source_name != "Web Search":
                cleaned_authors = [source_name]
                
        return cleaned_authors if cleaned_authors else ["Unknown Author"]
        
    def _format_inline_citation(self, source_info):
        authors = self._improve_author_extraction(source_info)
        year = self._extract_year_from_source(source_info)

        if not authors or authors == ["Unknown Author"]:
            return f"(Unknown, {year})"
        
        # Format author names for inline citation (last name only)
        formatted_authors = []
        for author in authors:
            if ", " in author:
                # Already in "LastName, F." format
                last_name = author.split(", ")[0]
            else:
                # Use as-is for organizations
                last_name = author
            formatted_authors.append(last_name)
        
        # APA style for inline citations
        if len(formatted_authors) == 1:
            return f"({formatted_authors[0]}, {year})"
        elif len(formatted_authors) == 2:
            return f"({formatted_authors[0]} & {formatted_authors[1]}, {year})"
        else:
            return f"({formatted_authors[0]} et al., {year})"
    
    def _generate_title_from_content(self, abstract):
        """Generate a descriptive title from abstract content"""
        # Truncate abstract and clean it up
        cleaned_abstract = abstract.strip()[:200]
        
        prompt = f"""
        Generate a concise, descriptive title (maximum 10 words) for a research paper based on this abstract excerpt:
        
        Abstract: {cleaned_abstract}
        
        The title should:
        - Capture the main topic or focus
        - Be specific but not overly technical
        - Follow academic title conventions
        
        Respond with only the title, no quotes or extra text:
        """
        
        try:
            response = self.model.invoke(prompt)
            title = response.content.strip()
            # Clean up the response
            title = title.strip('"\'\\')
            if len(title) > 100:  # Fallback if too long
                title = cleaned_abstract.split('.')[0][:50] + "..."
            return title
        except Exception as e:
            print(f"Error generating title: {e}")
            return "Research Paper"

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
            # Use improved extraction methods
            authors = self._improve_author_extraction(source)
            year = self._extract_year_from_source(source)
            
            # Enhanced title and source formatting
            title = source.get("title", "").strip()
            if not title or title.lower() in ["untitled", "no title", "n/a"]:
                # Try to generate a descriptive title from abstract
                abstract = source.get("abstract", "")
                if abstract and len(abstract) > 20:
                    title = self._generate_title_from_content(abstract)
                else:
                    title = "Untitled"
            
            # Better source identification
            source_name = source.get("source", "")
            if source_name == "Web Search" or not source_name:
                url = source.get("url", "")
                if url:
                    # Extract domain for better source identification
                    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                    if domain_match:
                        source_name = domain_match.group(1)
                    else:
                        source_name = "Web Source"
                else:
                    source_name = "Unpublished"

            references.append(APAReference(
                authors=authors,
                year=year,
                title=title,
                source=source_name,
                doi=source.get("doi")
            ))
        
        # Sort references alphabetically by the first author's last name
        references.sort(key=lambda x: x.authors[0].split(',')[0].strip().lower() if x.authors else '')

        return FormattedReport(
            report_text=report_with_citations,
            references=references
        )