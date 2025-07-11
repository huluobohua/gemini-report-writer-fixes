from utils import create_gemini_model
import re
import json

class QualityControllerAgent:
    def __init__(self):
        self.model = create_gemini_model(agent_role="quality_controller")
        
        # Quality thresholds
        self.minimum_coherence_score = 0.7
        self.minimum_factual_accuracy = 0.8
        self.minimum_source_usage = 0.6
    
    def assess_content_quality(self, report_content, sources, section_research_results=None):
        """Comprehensive content quality assessment"""
        
        assessments = {}
        
        # 1. Coherence Assessment
        assessments['coherence'] = self._assess_coherence(report_content)
        
        # 2. Factual Accuracy Assessment  
        assessments['accuracy'] = self._assess_factual_accuracy(report_content, sources)
        
        # 3. Source Usage Assessment
        assessments['source_usage'] = self._assess_source_usage(report_content, sources)
        
        # 4. Content Completeness Assessment
        assessments['completeness'] = self._assess_completeness(report_content, section_research_results)
        
        # 5. Citation Quality Assessment
        assessments['citations'] = self._assess_citation_quality(report_content, sources)
        
        # Calculate overall quality score
        overall_score = self._calculate_overall_score(assessments)
        
        # Determine if revision is needed
        needs_revision = (
            assessments['coherence']['score'] < self.minimum_coherence_score or
            assessments['accuracy']['score'] < self.minimum_factual_accuracy or
            assessments['source_usage']['score'] < self.minimum_source_usage or
            overall_score < 0.7
        )
        
        return {
            'overall_score': overall_score,
            'needs_revision': needs_revision,
            'assessments': assessments,
            'recommendations': self._generate_recommendations(assessments)
        }
    
    def _assess_coherence(self, content):
        """Assess the logical flow and coherence of the content"""
        prompt = f"""
        Evaluate the coherence and logical flow of this report content.
        
        Content: {content[:2000]}
        
        Assess:
        1. Logical structure and flow between sections
        2. Consistency of arguments and claims
        3. Clear transitions between topics
        4. Overall readability and organization
        
        Rate from 0.0 to 1.0 and provide specific feedback.
        
        Respond with JSON:
        {{
            "score": 0.0-1.0,
            "issues": ["list of coherence issues"],
            "strengths": ["list of coherence strengths"],
            "improvement_suggestions": ["specific suggestions"]
        }}
        """
        
        return self._get_llm_assessment(prompt, 'coherence')
    
    def _assess_factual_accuracy(self, content, sources):
        """Assess factual accuracy against provided sources"""
        # Create source summaries for context
        source_summaries = []
        for i, source in enumerate(sources[:5]):  # Limit to top 5
            title = source.get('title', 'No title')
            abstract = source.get('abstract', 'No abstract')[:200]
            source_summaries.append(f"Source {i+1}: {title}\nAbstract: {abstract}")
        
        sources_text = "\n\n".join(source_summaries)
        
        prompt = f"""
        Evaluate the factual accuracy of this report content against the provided sources.
        
        Content: {content[:1500]}
        
        Sources:
        {sources_text}
        
        Check for:
        1. Claims that are supported by the sources
        2. Claims that contradict the sources
        3. Claims that cannot be verified from the sources
        4. Proper use of source information
        
        Rate from 0.0 to 1.0 and provide specific feedback.
        
        Respond with JSON:
        {{
            "score": 0.0-1.0,
            "unsupported_claims": ["claims not backed by sources"],
            "contradictions": ["claims that contradict sources"],
            "verification_issues": ["other factual concerns"],
            "well_supported": ["well-documented claims"]
        }}
        """
        
        return self._get_llm_assessment(prompt, 'factual_accuracy')
    
    def _assess_source_usage(self, content, sources):
        """Assess how effectively sources are used in the content"""
        
        # Count citations and references
        citation_patterns = [
            r'\(([^(),]+),\s*(\d{4}|n\.d\.)\)',  # (Author, Year)
            r'\[Source\s+(\d+)\]',               # [Source X]
            r'DOI:\s*10\.\d+/[^\s]+'             # DOI references
        ]
        
        total_citations = 0
        for pattern in citation_patterns:
            total_citations += len(re.findall(pattern, content))
        
        source_count = len(sources)
        citation_ratio = total_citations / max(source_count, 1)
        
        prompt = f"""
        Evaluate how effectively the sources are integrated into this report content.
        
        Content: {content[:1500]}
        
        Source count: {source_count}
        Citations found: {total_citations}
        
        Assess:
        1. Are sources properly cited throughout the content?
        2. Is there good balance in source usage (not over-relying on one source)?
        3. Are citations placed appropriately to support claims?
        4. Are there sections that lack source support?
        
        Rate from 0.0 to 1.0 and provide feedback.
        
        Respond with JSON:
        {{
            "score": 0.0-1.0,
            "citation_distribution": "even/uneven/missing",
            "unsupported_sections": ["sections lacking citations"],
            "overused_sources": ["sources used too frequently"],
            "citation_placement": "appropriate/inappropriate"
        }}
        """
        
        assessment = self._get_llm_assessment(prompt, 'source_usage')
        
        # Adjust score based on citation ratio
        if assessment and 'score' in assessment:
            ratio_penalty = max(0, 0.5 - citation_ratio) if citation_ratio < 0.5 else 0
            assessment['score'] = max(0, assessment['score'] - ratio_penalty)
            assessment['citation_ratio'] = citation_ratio
        
        return assessment
    
    def _assess_completeness(self, content, section_research_results):
        """Assess whether the content fully addresses the planned sections"""
        if not section_research_results:
            return {'score': 0.8, 'note': 'No section research data available for completeness assessment'}
        
        planned_sections = list(section_research_results.keys())
        
        prompt = f"""
        Evaluate whether this report content adequately covers the planned sections.
        
        Content: {content[:1500]}
        
        Planned sections: {planned_sections}
        
        Assess:
        1. Are all planned sections represented in the content?
        2. Is each section given appropriate depth and coverage?
        3. Are there missing topics that should be included?
        4. Is the coverage balanced across sections?
        
        Rate from 0.0 to 1.0 and provide feedback.
        
        Respond with JSON:
        {{
            "score": 0.0-1.0,
            "missing_sections": ["sections not adequately covered"],
            "underdeveloped_sections": ["sections needing more depth"],
            "section_balance": "balanced/unbalanced",
            "coverage_gaps": ["important topics missing"]
        }}
        """
        
        return self._get_llm_assessment(prompt, 'completeness')
    
    def _assess_citation_quality(self, content, sources):
        """Assess the quality and appropriateness of citations"""
        prompt = f"""
        Evaluate the quality of citations in this report content.
        
        Content: {content[:1500]}
        
        Number of sources available: {len(sources)}
        
        Assess:
        1. Are citations formatted consistently?
        2. Are citations placed at appropriate locations?
        3. Do citations support the claims they're attached to?
        4. Are there any citation formatting issues?
        
        Rate from 0.0 to 1.0 and provide feedback.
        
        Respond with JSON:
        {{
            "score": 0.0-1.0,
            "formatting_issues": ["citation formatting problems"],
            "placement_issues": ["inappropriate citation placement"],
            "missing_citations": ["claims that need citations"],
            "citation_consistency": "consistent/inconsistent"
        }}
        """
        
        return self._get_llm_assessment(prompt, 'citation_quality')
    
    def _get_llm_assessment(self, prompt, assessment_type):
        """Get LLM assessment with error handling"""
        try:
            response = self.model.invoke(prompt)
            result_text = response.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback for non-JSON responses
                return {
                    'score': 0.5,
                    'note': f'Could not parse {assessment_type} assessment',
                    'raw_response': result_text[:200]
                }
        except Exception as e:
            print(f"Error in {assessment_type} assessment: {e}")
            return {
                'score': 0.0,
                'error': str(e),
                'note': f'Assessment failed for {assessment_type}'
            }
    
    def _calculate_overall_score(self, assessments):
        """Calculate weighted overall quality score"""
        weights = {
            'coherence': 0.25,
            'accuracy': 0.30,
            'source_usage': 0.20,
            'completeness': 0.15,
            'citations': 0.10
        }
        
        total_score = 0
        total_weight = 0
        
        for category, weight in weights.items():
            if category in assessments and 'score' in assessments[category]:
                total_score += assessments[category]['score'] * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _generate_recommendations(self, assessments):
        """Generate specific recommendations for improvement"""
        recommendations = []
        
        for category, assessment in assessments.items():
            if isinstance(assessment, dict) and assessment.get('score', 1.0) < 0.7:
                if category == 'coherence':
                    recommendations.append("Improve logical flow and organization of content")
                elif category == 'accuracy':
                    recommendations.append("Verify factual claims against provided sources")
                elif category == 'source_usage':
                    recommendations.append("Better integrate sources with appropriate citations")
                elif category == 'completeness':
                    recommendations.append("Develop undercovered sections more thoroughly")
                elif category == 'citations':
                    recommendations.append("Improve citation formatting and placement")
                
                # Add specific issues from assessment
                for issue_key in ['issues', 'unsupported_claims', 'missing_sections', 'formatting_issues']:
                    if issue_key in assessment and assessment[issue_key]:
                        recommendations.extend(assessment[issue_key][:2])  # Limit to top 2 issues
        
        return recommendations[:5]  # Limit to top 5 recommendations