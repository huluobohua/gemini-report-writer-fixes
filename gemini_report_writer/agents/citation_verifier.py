
import re
import json
from utils import create_gemini_model

class CitationVerifierAgent:
    def __init__(self, firecrawl_api_key=None):
        self.model = create_gemini_model(agent_role="citation_verifier")
        self.content_verifier = create_gemini_model(agent_role="content_verifier")

    def extract_dois(self, text):
        dois = re.findall(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', text, re.IGNORECASE)
        return list(set(dois))

    def extract_all_citations(self, text):
        """Extract all types of citations from text, not just DOIs"""
        citations = []
        
        # Extract DOI citations
        dois = self.extract_dois(text)
        for doi in dois:
            citations.append({'type': 'doi', 'identifier': doi})
        
        # Extract inline citations like (Author, Year)
        inline_pattern = r'\(([^(),]+),\s*(\d{4}|n\.d\.)\)'
        inline_matches = re.findall(inline_pattern, text)
        for author, year in inline_matches:
            citations.append({'type': 'inline', 'author': author.strip(), 'year': year})
        
        # Extract [Source X] references
        source_pattern = r'\[Source\s+(\d+)\]'
        source_matches = re.findall(source_pattern, text)
        for source_num in source_matches:
            citations.append({'type': 'source_ref', 'source_number': int(source_num)})
        
        return citations
    
    def validate_content_accuracy(self, report_content, sources):
        """Validate that the report content is factually supported by sources"""
        if not sources:
            return {'accurate': False, 'reason': 'No sources provided for validation'}
        
        # Create a summary of all available source content
        sources_summary = []
        for i, source in enumerate(sources[:10]):  # Limit to avoid context overflow
            title = source.get('title', 'No title')
            abstract = source.get('abstract', 'No abstract')[:300]  # Truncate
            authors = ', '.join(source.get('authors', [])[:3])  # Max 3 authors
            year = source.get('year', 'n.d.')
            sources_summary.append(f"Source {i+1}: {title} ({authors}, {year})\nAbstract: {abstract}")
        
        sources_text = "\n\n---\n\n".join(sources_summary)
        
        prompt = f"""
        You are a fact-checking expert. Evaluate whether the report content is factually accurate and properly supported by the provided sources.
        
        REPORT CONTENT TO VERIFY:
        {report_content[:2000]}  # Truncate to avoid context overflow
        
        AVAILABLE SOURCES:
        {sources_text}
        
        Evaluation criteria:
        1. Are the factual claims in the report supported by the sources?
        2. Are there any contradictions between the report and sources?
        3. Does the report make claims that go beyond what the sources support?
        4. Are the citations used appropriately?
        
        Respond with a JSON object:
        {{
            "accurate": true/false,
            "confidence": 0.0-1.0,
            "issues": ["list of specific issues found"],
            "unsupported_claims": ["claims not supported by sources"],
            "contradictions": ["contradictions found"]
        }}
        """
        
        try:
            response = self.content_verifier.invoke(prompt)
            result_text = response.content.strip()
            
            # Extract JSON from response
            import json
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                # Fallback parsing
                accurate = 'true' in result_text.lower() or 'accurate' in result_text.lower()
                return {
                    'accurate': accurate,
                    'confidence': 0.5,
                    'issues': ['Could not parse detailed response'],
                    'unsupported_claims': [],
                    'contradictions': []
                }
        except Exception as e:
            print(f"Error validating content accuracy: {e}")
            return {
                'accurate': False,
                'confidence': 0.0,
                'issues': [f'Validation error: {str(e)}'],
                'unsupported_claims': [],
                'contradictions': []
            }
    
    def verify_citations(self, report, cached_sources=None):
        """Comprehensive citation and content verification"""
        if not cached_sources:
            print("Warning: No cached sources provided for citation verification.")
            return {"status": "error", "needs_revision": True, "message": "No sources to verify against"}
        
        # Extract all types of citations
        citations = self.extract_all_citations(report)
        print(f"Found {len(citations)} citations to verify")
        
        flags = []
        
        # Verify each citation
        for citation in citations:
            if citation['type'] == 'doi':
                flag = self._verify_doi_citation(citation, cached_sources, report)
            elif citation['type'] == 'inline':
                flag = self._verify_inline_citation(citation, cached_sources, report)
            elif citation['type'] == 'source_ref':
                flag = self._verify_source_reference(citation, cached_sources, report)
            
            if flag:
                flags.append(flag)
        
        # Perform content accuracy validation
        content_validation = self.validate_content_accuracy(report, cached_sources)
        
        # Check for unused sources (sources that weren't cited)
        cited_sources = set()
        for citation in citations:
            if citation['type'] == 'source_ref':
                cited_sources.add(citation['source_number'])
        
        unused_sources = []
        for i in range(len(cached_sources)):
            if (i + 1) not in cited_sources:
                unused_sources.append(i + 1)
        
        # Determine if revision is needed
        citation_issues = any(flag["label"] not in ["supported", "verified"] for flag in flags)
        content_issues = not content_validation['accurate']
        unused_source_issues = len(unused_sources) > len(cached_sources) * 0.3  # More than 30% unused
        
        needs_revision = citation_issues or content_issues or unused_source_issues
        
        return {
            "status": "completed",
            "needs_revision": needs_revision,
            "citation_flags": flags,
            "content_validation": content_validation,
            "unused_sources": unused_sources,
            "summary": {
                "total_citations": len(citations),
                "verified_citations": len([f for f in flags if f["label"] in ["supported", "verified"]]),
                "content_accurate": content_validation['accurate'],
                "unused_sources_count": len(unused_sources)
            }
        }

    def _verify_doi_citation(self, citation, sources, report):
        """Verify DOI-based citations"""
        doi = citation['identifier']
        matching_source = None
        
        for source in sources:
            if source and source.get('doi') == doi:
                matching_source = source
                break
        
        if not matching_source:
            return {"type": "doi", "identifier": doi, "label": "source_not_found", "message": "DOI not found in sources"}
        
        return self._verify_content_support(matching_source, report, citation)
    
    def _verify_inline_citation(self, citation, sources, report):
        """Verify inline citations like (Author, Year)"""
        author = citation['author']
        year = citation['year']
        
        # Find matching source by author and year
        matching_source = None
        for source in sources:
            source_authors = source.get('authors', [])
            source_year = str(source.get('year', ''))
            
            # Check if author matches any source author
            author_match = any(author.lower() in str(src_author).lower() for src_author in source_authors)
            year_match = year == source_year or (year == 'n.d.' and not source_year)
            
            if author_match and year_match:
                matching_source = source
                break
        
        if not matching_source:
            return {"type": "inline", "citation": f"({author}, {year})", "label": "source_not_found", "message": "No matching source found"}
        
        return self._verify_content_support(matching_source, report, citation)
    
    def _verify_source_reference(self, citation, sources, report):
        """Verify [Source X] references"""
        source_num = citation['source_number']
        
        if source_num <= 0 or source_num > len(sources):
            return {"type": "source_ref", "source_number": source_num, "label": "invalid_reference", "message": "Source number out of range"}
        
        source = sources[source_num - 1]  # Convert to 0-based index
        return self._verify_content_support(source, report, citation)
    
    def _verify_content_support(self, source, report, citation):
        """Verify that source actually supports the content where it's cited"""
        source_title = source.get('title', 'No title')
        source_abstract = source.get('abstract', 'No abstract')
        
        prompt = f"""
        Verify if this source supports the claims made in the report.
        
        Source: {source_title}
        Abstract: {source_abstract[:500]}
        
        Report content: {report[:1000]}
        
        Citation context: {citation}
        
        Does the source provide evidence for claims in the report?
        - 'supported': Source clearly supports the claims
        - 'mentioned': Source discusses the topic but doesn't directly support specific claims
        - 'disputed': Source contradicts the claims
        - 'irrelevant': Source is not relevant to the claims
        
        Respond with only one of these labels:
        """
        
        try:
            response = self.model.invoke(prompt)
            label = response.content.strip().lower()
            
            if 'supported' in label:
                result_label = 'supported'
            elif 'mentioned' in label:
                result_label = 'mentioned'
            elif 'disputed' in label:
                result_label = 'disputed'
            else:
                result_label = 'irrelevant'
                
            return {
                "type": citation.get('type', 'unknown'),
                "citation": str(citation),
                "label": result_label,
                "source_title": source_title
            }
            
        except Exception as e:
            return {
                "type": citation.get('type', 'unknown'),
                "citation": str(citation),
                "label": "error",
                "message": str(e)
            }
