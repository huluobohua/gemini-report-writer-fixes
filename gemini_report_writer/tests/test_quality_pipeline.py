"""
Basic tests for QualityValidationPipeline
"""
import unittest
import tempfile
import yaml
from unittest.mock import Mock, patch
from agents.quality_pipeline import QualityValidationPipeline, QualityMetric, StageQualityReport

class TestQualityValidationPipeline(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock model to avoid actual LLM calls
        with patch('agents.quality_pipeline.create_gemini_model') as mock_create:
            mock_create.return_value = Mock()
            self.pipeline = QualityValidationPipeline()
    
    def test_pipeline_initialization(self):
        """Test basic pipeline initialization"""
        self.assertIsNotNone(self.pipeline.config)
        self.assertIn('quality_thresholds', self.pipeline.config)
        self.assertIn('pipeline_settings', self.pipeline.config)
        self.assertIn('stage_weights', self.pipeline.config)
    
    def test_config_loading_with_custom_file(self):
        """Test loading configuration from custom YAML file"""
        # Create temporary config file
        test_config = {
            'quality_thresholds': {
                'outline_quality_threshold': 0.9,
                'research_quality_threshold': 0.85
            },
            'pipeline_settings': {
                'enable_early_termination': False,
                'max_revision_cycles': 5
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_config_path = f.name
        
        try:
            with patch('agents.quality_pipeline.create_gemini_model') as mock_create:
                mock_create.return_value = Mock()
                pipeline = QualityValidationPipeline(config_path=temp_config_path)
            
            # Verify custom config was loaded
            self.assertEqual(pipeline.get_threshold('outline_quality_threshold'), 0.9)
            self.assertEqual(pipeline.get_setting('pipeline_settings.max_revision_cycles'), 5)
            self.assertFalse(pipeline.get_setting('pipeline_settings.enable_early_termination'))
        finally:
            import os
            os.unlink(temp_config_path)
    
    def test_config_validation_valid(self):
        """Test config validation with valid configuration"""
        valid_config = {
            'quality_thresholds': {
                'outline_quality_threshold': 0.7,
                'research_quality_threshold': 0.8
            },
            'stage_weights': {
                'outline_quality': 0.3,
                'research_quality': 0.7
            },
            'pipeline_settings': {
                'max_revision_cycles': 3
            }
        }
        
        with patch('agents.quality_pipeline.create_gemini_model') as mock_create:
            mock_create.return_value = Mock()
            # Should not raise any exceptions
            pipeline = QualityValidationPipeline(quality_config=valid_config)
            self.assertIsNotNone(pipeline.config)
    
    def test_config_validation_invalid_threshold(self):
        """Test config validation with invalid threshold values"""
        invalid_config = {
            'quality_thresholds': {
                'outline_quality_threshold': 1.5,  # Invalid: > 1.0
                'research_quality_threshold': -0.1  # Invalid: < 0.0
            }
        }
        
        with patch('agents.quality_pipeline.create_gemini_model') as mock_create:
            mock_create.return_value = Mock()
            with self.assertRaises(ValueError):
                QualityValidationPipeline(quality_config=invalid_config)
    
    def test_config_validation_invalid_weights(self):
        """Test config validation with stage weights that don't sum to 1.0"""
        invalid_config = {
            'stage_weights': {
                'outline_quality': 0.3,
                'research_quality': 0.8  # Total = 1.1, invalid
            }
        }
        
        with patch('agents.quality_pipeline.create_gemini_model') as mock_create:
            mock_create.return_value = Mock()
            with self.assertRaises(ValueError):
                QualityValidationPipeline(quality_config=invalid_config)
    
    def test_get_threshold(self):
        """Test threshold retrieval"""
        threshold = self.pipeline.get_threshold('outline_quality_threshold')
        self.assertIsInstance(threshold, float)
        self.assertGreaterEqual(threshold, 0.0)
        self.assertLessEqual(threshold, 1.0)
        
        # Test non-existent threshold returns default
        default_threshold = self.pipeline.get_threshold('non_existent_threshold')
        self.assertEqual(default_threshold, 0.7)
    
    def test_get_setting(self):
        """Test setting retrieval with dot notation"""
        setting = self.pipeline.get_setting('pipeline_settings.enable_early_termination')
        self.assertIsInstance(setting, bool)
        
        # Test nested setting that doesn't exist
        default_value = self.pipeline.get_setting('non.existent.setting', 'default')
        self.assertEqual(default_value, 'default')
    
    def test_quality_tracking_lifecycle(self):
        """Test complete quality tracking lifecycle"""
        # Start quality tracking
        report = self.pipeline.start_quality_tracking('Test Topic')
        self.assertIsNotNone(report)
        self.assertEqual(report.topic, 'Test Topic')
        self.assertEqual(len(report.stage_reports), 0)
        
        # Create a mock stage report
        mock_metric = QualityMetric(
            name='test_metric',
            score=0.8,
            threshold=0.7,
            passed=True
        )
        
        stage_report = StageQualityReport(
            stage_name='test_stage',
            metrics=[mock_metric],
            overall_score=0.8,
            passed=True
        )
        
        # Add stage report
        report.add_stage_report(stage_report)
        self.assertEqual(len(report.stage_reports), 1)
        self.assertEqual(report.quality_gates_passed, 1)
        self.assertEqual(report.quality_gates_total, 1)
        
        # Finalize report
        final_report = self.pipeline.finalize_quality_report()
        self.assertIsNotNone(final_report.end_time)
        self.assertGreater(final_report.overall_score, 0)
    
    def test_early_termination_logic(self):
        """Test early termination decision logic"""
        # Start tracking
        self.pipeline.start_quality_tracking('Test Topic')
        
        # No failing stages - should not terminate
        self.assertFalse(self.pipeline.should_terminate_early())
        
        # Add one failing stage
        failing_metric = QualityMetric('test', 0.5, 0.7, False)
        failing_report = StageQualityReport('test_stage', [failing_metric], 0.5, False)
        self.pipeline.current_report.add_stage_report(failing_report)
        
        # One failing stage - should not terminate by default
        self.assertFalse(self.pipeline.should_terminate_early())
        
        # Add second failing stage
        failing_report2 = StageQualityReport('test_stage2', [failing_metric], 0.5, False)
        self.pipeline.current_report.add_stage_report(failing_report2)
        
        # Two failing stages - should terminate
        self.assertTrue(self.pipeline.should_terminate_early())
    
    @patch('agents.quality_pipeline.create_gemini_model')
    def test_outline_quality_validation_structure(self, mock_create):
        """Test outline quality validation structure (without LLM calls)"""
        mock_model = Mock()
        mock_create.return_value = mock_model
        
        pipeline = QualityValidationPipeline()
        
        test_outline = [
            'Introduction',
            'Background Research', 
            'Methodology',
            'Results',
            'Discussion',
            'Conclusion'
        ]
        
        # Mock the LLM call to return a valid score
        mock_model.invoke.return_value.content.strip.return_value = "0.8"
        
        # Test validation
        report = pipeline.validate_outline_quality(test_outline, 'Test Topic')
        
        self.assertIsInstance(report, StageQualityReport)
        self.assertEqual(report.stage_name, 'outline_quality')
        self.assertGreater(len(report.metrics), 0)
        self.assertIsInstance(report.overall_score, float)
        self.assertIsInstance(report.passed, bool)
    
    def test_heuristic_scoring_methods(self):
        """Test heuristic-based scoring methods that don't require LLM calls"""
        # Test outline structure assessment
        good_outline = ['Introduction', 'Background', 'Analysis', 'Conclusion']
        score = self.pipeline._assess_outline_structure(good_outline)
        self.assertGreaterEqual(score, 0.5)  # Should get reasonable score
        
        # Test with too few sections
        short_outline = ['Introduction']
        score = self.pipeline._assess_outline_structure(short_outline)
        self.assertEqual(score, 0.3)  # Should get low score
        
        # Test keyword overlap calculation
        outline = ['Machine Learning', 'Neural Networks', 'Deep Learning']
        topic = 'Machine Learning Applications'
        overlap = self.pipeline._calculate_keyword_overlap(outline, topic)
        self.assertGreater(overlap, 0)  # Should find some overlap

if __name__ == '__main__':
    unittest.main()