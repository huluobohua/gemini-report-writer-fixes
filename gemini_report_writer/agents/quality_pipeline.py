import json
import time
import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from utils import create_gemini_model

@dataclass
class QualityMetric:
    """Individual quality metric with score and context"""
    name: str
    score: float
    threshold: float
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class StageQualityReport:
    """Quality report for a specific workflow stage"""
    stage_name: str
    metrics: List[QualityMetric]
    overall_score: float
    passed: bool
    recommendations: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def get_metric(self, name: str) -> Optional[QualityMetric]:
        """Get a specific metric by name"""
        return next((m for m in self.metrics if m.name == name), None)

@dataclass
class SystemQualityReport:
    """Comprehensive system-wide quality report"""
    workflow_id: str
    topic: str
    stage_reports: List[StageQualityReport] = field(default_factory=list)
    overall_score: float = 0.0
    quality_gates_passed: int = 0
    quality_gates_total: int = 0
    final_recommendation: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def add_stage_report(self, report: StageQualityReport):
        """Add a stage report and update overall metrics"""
        self.stage_reports.append(report)
        self._update_overall_metrics()
    
    def _update_overall_metrics(self):
        """Update overall quality metrics based on stage reports"""
        if not self.stage_reports:
            return
            
        # Calculate weighted overall score
        total_weighted_score = 0
        total_weight = 0
        
        # Default stage weights (hardcoded in SystemQualityReport for independence)
        stage_weights = {
            'outline_quality': 0.15,
            'research_quality': 0.25,
            'content_quality': 0.25,
            'citation_quality': 0.20,
            'coherence_quality': 0.15
        }
        
        for report in self.stage_reports:
            weight = stage_weights.get(report.stage_name, 0.1)
            total_weighted_score += report.overall_score * weight
            total_weight += weight
            
            if report.passed:
                self.quality_gates_passed += 1
        
        self.quality_gates_total = len(self.stage_reports)
        self.overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Generate final recommendation
        if self.overall_score >= 0.85:
            self.final_recommendation = "EXCELLENT: High-quality report ready for publication"
        elif self.overall_score >= 0.75:
            self.final_recommendation = "GOOD: Report meets quality standards"
        elif self.overall_score >= 0.60:
            self.final_recommendation = "ACCEPTABLE: Minor improvements recommended"
        else:
            self.final_recommendation = "NEEDS_IMPROVEMENT: Significant quality issues require attention"

class QualityValidationPipeline:
    """System-wide quality validation pipeline"""
    
    def __init__(self, config_path: Optional[str] = None, quality_config: Optional[Dict] = None):
        self.model = create_gemini_model(agent_role="quality_controller")
        
        # Load configuration from file or use defaults
        self.config = self._load_config(config_path, quality_config)
        
        # Validate configuration
        self._validate_config()
        
        self.current_report: Optional[SystemQualityReport] = None
    
    def _load_config(self, config_path: Optional[str] = None, override_config: Optional[Dict] = None) -> Dict:
        """Load configuration from YAML file with optional overrides"""
        
        # Default configuration (fallback)
        default_config = {
            'quality_thresholds': {
                'outline_quality_threshold': 0.7,
                'research_quality_threshold': 0.75,
                'content_quality_threshold': 0.8,
                'citation_quality_threshold': 0.8,
                'coherence_quality_threshold': 0.75,
                'overall_quality_threshold': 0.7
            },
            'pipeline_settings': {
                'enable_early_termination': True,
                'max_revision_cycles': 3,
                'failing_stages_for_termination': 2
            },
            'stage_weights': {
                'outline_quality': 0.15,
                'research_quality': 0.25,
                'content_quality': 0.25,
                'citation_quality': 0.20,
                'coherence_quality': 0.15
            }
        }
        
        config = default_config.copy()
        
        # Try to load from YAML file
        if config_path is None:
            # Default config file location
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'quality_config.yaml')
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config.update(yaml_config)
                print(f"✓ Quality configuration loaded from {config_path}")
            except Exception as e:
                print(f"⚠️  Warning: Failed to load config from {config_path}: {e}")
                print("   Using default configuration")
        else:
            print(f"ℹ️  Config file not found at {config_path}, using defaults")
        
        # Apply any runtime overrides
        if override_config:
            config.update(override_config)
        
        return config
    
    def _validate_config(self):
        """Validate configuration values are reasonable"""
        thresholds = self.config.get('quality_thresholds', {})
        
        # Validate thresholds are between 0 and 1
        for key, value in thresholds.items():
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ValueError(f"Quality threshold '{key}' must be between 0.0 and 1.0, got {value}")
        
        # Validate stage weights sum to approximately 1.0
        weights = self.config.get('stage_weights', {})
        if weights:
            total_weight = sum(weights.values())
            if not (0.95 <= total_weight <= 1.05):  # Allow small floating point variance
                raise ValueError(f"Stage weights must sum to 1.0, got {total_weight}")
        
        # Validate pipeline settings
        pipeline_settings = self.config.get('pipeline_settings', {})
        max_cycles = pipeline_settings.get('max_revision_cycles', 3)
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError(f"max_revision_cycles must be a positive integer, got {max_cycles}")
    
    def get_threshold(self, threshold_name: str) -> float:
        """Get a quality threshold from configuration"""
        return self.config.get('quality_thresholds', {}).get(threshold_name, 0.7)
    
    def get_setting(self, setting_path: str, default=None):
        """Get a setting value using dot notation (e.g., 'pipeline_settings.enable_early_termination')"""
        keys = setting_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def start_quality_tracking(self, topic: str, workflow_id: str = None) -> SystemQualityReport:
        """Initialize quality tracking for a new workflow"""
        if not workflow_id:
            workflow_id = f"workflow_{int(time.time())}"
            
        self.current_report = SystemQualityReport(
            workflow_id=workflow_id,
            topic=topic
        )
        
        print(f"🎯 Quality tracking started for: {topic}")
        return self.current_report
    
    def validate_outline_quality(self, outline: List[str], topic: str) -> StageQualityReport:
        """Validate outline quality and coherence"""
        metrics = []
        
        # 1. Topic relevance assessment
        relevance_score = self._assess_outline_topic_relevance(outline, topic)
        threshold = self.get_threshold('outline_quality_threshold')
        metrics.append(QualityMetric(
            name="topic_relevance",
            score=relevance_score,
            threshold=threshold,
            passed=relevance_score >= threshold,
            details={'outline_sections': len(outline)}
        ))
        
        # 2. Structural coherence assessment
        coherence_score = self._assess_outline_structure(outline)
        metrics.append(QualityMetric(
            name="structural_coherence", 
            score=coherence_score,
            threshold=threshold,
            passed=coherence_score >= threshold,
            details={'logical_flow': coherence_score > 0.8}
        ))
        
        # 3. Completeness assessment
        completeness_score = self._assess_outline_completeness(outline, topic)
        metrics.append(QualityMetric(
            name="completeness",
            score=completeness_score,
            threshold=threshold,
            passed=completeness_score >= threshold,
            details={'coverage_areas': self._identify_coverage_areas(outline)}
        ))
        
        # Calculate overall stage score
        overall_score = sum(m.score for m in metrics) / len(metrics)
        stage_passed = all(m.passed for m in metrics)
        
        recommendations = []
        if not stage_passed:
            if relevance_score < threshold:
                recommendations.append("Improve topic alignment of outline sections")
            if coherence_score < threshold:
                recommendations.append("Enhance logical flow between sections")
            if completeness_score < threshold:
                recommendations.append("Add missing key topic areas to outline")
        
        report = StageQualityReport(
            stage_name="outline_quality",
            metrics=metrics,
            overall_score=overall_score,
            passed=stage_passed,
            recommendations=recommendations
        )
        
        if self.current_report:
            self.current_report.add_stage_report(report)
        
        print(f"📋 Outline Quality: {overall_score:.2f} ({'✅ PASS' if stage_passed else '❌ FAIL'})")
        return report
    
    def validate_research_quality(self, research_results: Dict, sources: List, skipped_sections: List) -> StageQualityReport:
        """Validate research quality across all sections"""
        metrics = []
        threshold = self.get_threshold('research_quality_threshold')
        
        # 1. Source quality assessment
        source_quality_score = self._assess_source_quality(sources)
        metrics.append(QualityMetric(
            name="source_quality",
            score=source_quality_score,
            threshold=threshold,
            passed=source_quality_score >= threshold,
            details={'source_count': len(sources), 'quality_sources': sum(1 for s in sources if s.get('relevance_score', 0) > 0.7)}
        ))
        
        # 2. Research completeness
        completeness_score = self._assess_research_completeness(research_results, skipped_sections)
        metrics.append(QualityMetric(
            name="research_completeness",
            score=completeness_score, 
            threshold=threshold,
            passed=completeness_score >= threshold,
            details={'completed_sections': len(research_results), 'skipped_sections': len(skipped_sections)}
        ))
        
        # 3. Content depth assessment
        depth_score = self._assess_research_depth(research_results)
        metrics.append(QualityMetric(
            name="content_depth",
            score=depth_score,
            threshold=threshold, 
            passed=depth_score >= threshold,
            details={'average_content_length': self._calculate_avg_content_length(research_results)}
        ))
        
        overall_score = sum(m.score for m in metrics) / len(metrics)
        stage_passed = all(m.passed for m in metrics)
        
        recommendations = []
        if not stage_passed:
            if source_quality_score < threshold:
                recommendations.append("Improve source quality and relevance")
            if completeness_score < threshold:
                recommendations.append("Reduce skipped sections by finding better sources")
            if depth_score < threshold:
                recommendations.append("Conduct more thorough research with deeper analysis")
        
        report = StageQualityReport(
            stage_name="research_quality",
            metrics=metrics,
            overall_score=overall_score,
            passed=stage_passed,
            recommendations=recommendations
        )
        
        if self.current_report:
            self.current_report.add_stage_report(report)
            
        print(f"🔬 Research Quality: {overall_score:.2f} ({'✅ PASS' if stage_passed else '❌ FAIL'})")
        return report
    
    def validate_content_coherence(self, report_content: str, outline: List[str]) -> StageQualityReport:
        """Validate overall content coherence and flow"""
        metrics = []
        threshold = self.get_threshold('coherence_quality_threshold')
        
        # 1. Outline-content alignment
        alignment_score = self._assess_content_outline_alignment(report_content, outline)
        metrics.append(QualityMetric(
            name="outline_alignment",
            score=alignment_score,
            threshold=threshold,
            passed=alignment_score >= threshold,
            details={'section_coverage': self._analyze_section_coverage(report_content, outline)}
        ))
        
        # 2. Narrative flow assessment
        flow_score = self._assess_narrative_flow(report_content)
        metrics.append(QualityMetric(
            name="narrative_flow",
            score=flow_score,
            threshold=threshold,
            passed=flow_score >= threshold,
            details={'transition_quality': flow_score > 0.8}
        ))
        
        # 3. Argument consistency
        consistency_score = self._assess_argument_consistency(report_content)
        metrics.append(QualityMetric(
            name="argument_consistency",
            score=consistency_score,
            threshold=threshold,
            passed=consistency_score >= threshold,
            details={'contradictions_found': consistency_score < 0.7}
        ))
        
        overall_score = sum(m.score for m in metrics) / len(metrics)
        stage_passed = all(m.passed for m in metrics)
        
        recommendations = []
        if not stage_passed:
            if alignment_score < threshold:
                recommendations.append("Better align content with planned outline structure")
            if flow_score < threshold:
                recommendations.append("Improve transitions and narrative flow between sections")
            if consistency_score < threshold:
                recommendations.append("Resolve contradictions and ensure argument consistency")
        
        report = StageQualityReport(
            stage_name="coherence_quality",
            metrics=metrics,
            overall_score=overall_score,
            passed=stage_passed,
            recommendations=recommendations
        )
        
        if self.current_report:
            self.current_report.add_stage_report(report)
            
        print(f"🧩 Coherence Quality: {overall_score:.2f} ({'✅ PASS' if stage_passed else '❌ FAIL'})")
        return report
    
    def finalize_quality_report(self) -> SystemQualityReport:
        """Finalize and return the complete quality report"""
        if not self.current_report:
            raise ValueError("No quality tracking session active")
            
        self.current_report.end_time = time.time()
        
        # Print final summary
        print(f"\n📊 FINAL QUALITY REPORT")
        print(f"Overall Score: {self.current_report.overall_score:.2f}")
        print(f"Quality Gates: {self.current_report.quality_gates_passed}/{self.current_report.quality_gates_total}")
        print(f"Recommendation: {self.current_report.final_recommendation}")
        
        return self.current_report
    
    def should_terminate_early(self) -> bool:
        """Determine if workflow should terminate early due to quality issues"""
        if not self.get_setting('pipeline_settings.enable_early_termination', True) or not self.current_report:
            return False
            
        # Check if we have multiple failing stages
        failing_stages = [r for r in self.current_report.stage_reports if not r.passed]
        failing_threshold = self.get_setting('pipeline_settings.failing_stages_for_termination', 2)
        
        if len(failing_stages) >= failing_threshold:
            print(f"⚠️  Early termination recommended: {len(failing_stages)} quality gates failed")
            return True
            
        return False
    
    # Helper methods for quality assessment
    def _assess_outline_topic_relevance(self, outline: List[str], topic: str) -> float:
        """Assess how well outline sections relate to the main topic"""
        try:
            prompt = f"""
            Evaluate how well this outline relates to the topic "{topic}".
            
            Outline sections:
            {chr(10).join(f"- {section}" for section in outline)}
            
            Rate from 0.0 to 1.0 based on:
            1. Relevance of each section to the main topic
            2. Coverage of key aspects of the topic
            3. Logical organization around the topic
            
            Respond with only a number between 0.0 and 1.0:
            """
            
            response = self.model.invoke(prompt)
            score_text = response.content.strip()
            
            # Extract numeric score
            try:
                score = float(score_text)
                return max(0.0, min(1.0, score))
            except ValueError:
                # Fallback scoring based on keyword overlap
                return self._calculate_keyword_overlap(outline, topic)
                
        except Exception as e:
            print(f"Error assessing outline relevance: {e}")
            return 0.5
    
    def _assess_outline_structure(self, outline: List[str]) -> float:
        """Assess structural coherence of the outline"""
        if len(outline) < 2:
            return 0.3
            
        # Basic structural checks
        score = 0.5  # Base score
        
        # Length appropriateness (3-8 sections ideal)
        if 3 <= len(outline) <= 8:
            score += 0.2
        elif len(outline) > 8:
            score -= 0.1
            
        # Check for logical progression indicators
        progression_words = ['introduction', 'background', 'methods', 'results', 'discussion', 'conclusion']
        has_progression = any(word in ' '.join(outline).lower() for word in progression_words)
        if has_progression:
            score += 0.2
            
        # Check for duplicate/similar sections
        unique_sections = set(section.lower().strip() for section in outline)
        if len(unique_sections) == len(outline):
            score += 0.1
            
        return max(0.0, min(1.0, score))
    
    def _assess_outline_completeness(self, outline: List[str], topic: str) -> float:
        """Assess completeness of outline coverage"""
        # This would ideally use domain-specific knowledge
        # For now, use basic heuristics
        
        score = 0.5  # Base score
        outline_text = ' '.join(outline).lower()
        
        # Check for key academic sections
        key_sections = ['introduction', 'background', 'analysis', 'conclusion']
        covered_sections = sum(1 for section in key_sections if section in outline_text)
        score += (covered_sections / len(key_sections)) * 0.3
        
        # Check for topic-specific terms
        topic_words = topic.lower().split()
        topic_coverage = sum(1 for word in topic_words if word in outline_text) / len(topic_words)
        score += topic_coverage * 0.2
        
        return max(0.0, min(1.0, score))
    
    def _identify_coverage_areas(self, outline: List[str]) -> List[str]:
        """Identify what areas the outline covers"""
        areas = []
        outline_text = ' '.join(outline).lower()
        
        area_keywords = {
            'theoretical': ['theory', 'theoretical', 'framework', 'concept'],
            'empirical': ['data', 'empirical', 'study', 'research', 'analysis'],
            'practical': ['application', 'practical', 'implementation', 'case'],
            'historical': ['history', 'historical', 'evolution', 'development']
        }
        
        for area, keywords in area_keywords.items():
            if any(keyword in outline_text for keyword in keywords):
                areas.append(area)
                
        return areas
    
    def _assess_source_quality(self, sources: List) -> float:
        """Assess overall quality of sources"""
        if not sources:
            return 0.0
            
        quality_scores = []
        for source in sources:
            score = 0.5  # Base score
            
            # Check for academic indicators
            if source.get('doi'):
                score += 0.2
            if 'author' in source and source['author'] != 'Unknown':
                score += 0.1
            if source.get('year') and str(source['year']).isdigit():
                year = int(source['year'])
                if 2010 <= year <= 2024:  # Recent sources get bonus
                    score += 0.1
            if source.get('relevance_score', 0) > 0.7:
                score += 0.1
                
            quality_scores.append(min(1.0, score))
            
        return sum(quality_scores) / len(quality_scores)
    
    def _assess_research_completeness(self, research_results: Dict, skipped_sections: List) -> float:
        """Assess completeness of research coverage"""
        total_planned = len(research_results) + len(skipped_sections)
        if total_planned == 0:
            return 0.0
            
        completion_rate = len(research_results) / total_planned
        
        # Penalty for too many skipped sections
        skip_penalty = min(0.3, len(skipped_sections) * 0.1)
        
        return max(0.0, completion_rate - skip_penalty)
    
    def _assess_research_depth(self, research_results: Dict) -> float:
        """Assess depth and quality of research content"""
        if not research_results:
            return 0.0
            
        depth_scores = []
        for section, content in research_results.items():
            if isinstance(content, dict):
                content_text = content.get('content', '')
            else:
                content_text = str(content)
                
            # Basic depth indicators
            score = 0.5
            
            if len(content_text) > 200:  # Sufficient length
                score += 0.2
            if len(content_text.split('.')) > 3:  # Multiple sentences
                score += 0.1
            if any(word in content_text.lower() for word in ['research', 'study', 'analysis', 'evidence']):
                score += 0.1
            if content_text.count('(') > 0:  # Has citations
                score += 0.1
                
            depth_scores.append(min(1.0, score))
            
        return sum(depth_scores) / len(depth_scores)
    
    def _calculate_avg_content_length(self, research_results: Dict) -> float:
        """Calculate average content length across sections"""
        if not research_results:
            return 0.0
            
        lengths = []
        for content in research_results.values():
            if isinstance(content, dict):
                content_text = content.get('content', '')
            else:
                content_text = str(content)
            lengths.append(len(content_text))
            
        return sum(lengths) / len(lengths)
    
    def _assess_content_outline_alignment(self, content: str, outline: List[str]) -> float:
        """Assess how well content follows the planned outline"""
        if not outline:
            return 0.5
            
        content_lower = content.lower()
        alignment_score = 0.0
        
        for section in outline:
            section_words = section.lower().split()
            # Check if section topics appear in content
            word_matches = sum(1 for word in section_words if word in content_lower)
            section_score = word_matches / len(section_words) if section_words else 0
            alignment_score += section_score
            
        return min(1.0, alignment_score / len(outline))
    
    def _assess_narrative_flow(self, content: str) -> float:
        """Assess narrative flow and transitions"""
        # Simple heuristic-based assessment
        score = 0.5
        
        # Check for transition indicators
        transition_words = ['however', 'furthermore', 'moreover', 'additionally', 'consequently', 'therefore']
        transition_count = sum(content.lower().count(word) for word in transition_words)
        
        paragraphs = content.split('\n\n')
        if len(paragraphs) > 1:
            transition_ratio = transition_count / len(paragraphs)
            score += min(0.3, transition_ratio * 0.5)
            
        # Check for consistent structure
        if len(paragraphs) >= 3:
            score += 0.2
            
        return min(1.0, score)
    
    def _assess_argument_consistency(self, content: str) -> float:
        """Assess consistency of arguments throughout content"""
        # This would require more sophisticated NLP analysis
        # Using basic heuristics for now
        
        score = 0.7  # Assume mostly consistent unless obvious issues
        
        # Check for contradiction indicators
        contradiction_patterns = ['but however', 'although but', 'despite however']
        for pattern in contradiction_patterns:
            if pattern in content.lower():
                score -= 0.2
                
        return max(0.0, score)
    
    def _analyze_section_coverage(self, content: str, outline: List[str]) -> Dict[str, bool]:
        """Analyze which outline sections are covered in content"""
        coverage = {}
        content_lower = content.lower()
        
        for section in outline:
            section_words = section.lower().split()
            covered = any(word in content_lower for word in section_words if len(word) > 3)
            coverage[section] = covered
            
        return coverage
    
    def _calculate_keyword_overlap(self, outline: List[str], topic: str) -> float:
        """Calculate keyword overlap between outline and topic"""
        outline_text = ' '.join(outline).lower()
        topic_words = topic.lower().split()
        
        overlap = sum(1 for word in topic_words if word in outline_text)
        return overlap / len(topic_words) if topic_words else 0.0