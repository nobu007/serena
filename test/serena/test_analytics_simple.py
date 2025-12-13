"""Simple and effective tests for the analytics module."""

import pytest

from serena.analytics import (
    TokenCountEstimator,
    CharCountEstimator,
    RegisteredTokenCountEstimator,
    ToolUsageStats,
    _registered_token_estimator_instances_cache
)


class TestTokenCountEstimator:
    """Test the abstract base class for token estimators."""
    
    def test_abstract_methods(self):
        """Test that TokenCountEstimator is indeed abstract."""
        with pytest.raises(TypeError):
            TokenCountEstimator()


class TestCharCountEstimator:
    """Test CharCountEstimator implementation."""
    
    def test_estimate_token_count_various_lengths(self):
        """Test token estimation with various text lengths."""
        estimator = CharCountEstimator(avg_chars_per_token=4)
        
        # Test cases: text, expected tokens
        test_cases = [
            ("", 0),           # Empty string
            ("abcd", 1),       # Exactly one token (4//4 = 1)
            ("abcde", 1),      # Just over one token (5//4 = 1)
            ("hello world", 2), # Normal text, 11 chars / 4 = 2 (integer division)
        ]
        
        for text, expected in test_cases:
            result = estimator.estimate_token_count(text)
            assert result == expected, f"Expected {expected} tokens for '{text}', got {result}"
    
    def test_different_chars_per_token(self):
        """Test with different characters per token values."""
        test_cases = [
            (1.0, "hello", 5),  # 1 char per token: 5//1 = 5
            (2.0, "hello", 2),  # 2 chars per token: 5//2 = 2 (integer division)
            (5.0, "hello", 1),  # 5 chars per token: 5//5 = 1
        ]
        
        for avg_chars_per_token, text, expected in test_cases:
            estimator = CharCountEstimator(avg_chars_per_token=avg_chars_per_token)
            result = estimator.estimate_token_count(text)
            assert result == expected
    
    def test_default_chars_per_token(self):
        """Test default value."""
        estimator = CharCountEstimator()
        assert estimator._avg_chars_per_token == 4


class TestRegisteredTokenCountEstimator:
    """Test the enum and its methods."""
    
    def test_get_valid_names(self):
        """Test getting valid estimator names."""
        names = RegisteredTokenCountEstimator.get_valid_names()
        expected_names = [
            "TIKTOKEN_GPT4O",
            "ANTHROPIC_CLAUDE_SONNET_4", 
            "CHAR_COUNT"
        ]
        assert set(names) == set(expected_names)
    
    def test_load_estimator_caching(self):
        """Test that estimator instances are cached."""
        # Clear cache
        _registered_token_estimator_instances_cache.clear()
        
        estimator1 = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()
        estimator2 = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()
        
        assert estimator1 is estimator2
        assert isinstance(estimator1, CharCountEstimator)
    
    def test_load_char_count_estimator(self):
        """Test loading CHAR_COUNT estimator."""
        estimator = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()
        assert isinstance(estimator, CharCountEstimator)
        assert estimator._avg_chars_per_token == 4


class TestToolUsageStats:
    """Test ToolUsageStats class."""
    
    def test_initialization(self):
        """Test ToolUsageStats initialization."""
        stats = ToolUsageStats()
        assert stats.token_estimator_name == "TIKTOKEN_GPT4O"  # Default is TIKTOKEN_GPT4O
        assert len(stats._tool_stats) == 0
    
    def test_record_and_get_stats(self):
        """Test recording tool usage and getting stats."""
        stats = ToolUsageStats()
        
        # Record usage
        stats.record_tool_usage("test_tool", "input text", "output text")
        
        # Get stats
        tool_stats = stats.get_stats("test_tool")
        assert tool_stats.num_times_called == 1
        assert tool_stats.input_tokens > 0  # Should calculate tokens
        assert tool_stats.output_tokens > 0
    
    def test_multiple_tool_usage(self):
        """Test recording multiple tool usages."""
        stats = ToolUsageStats()
        
        # Record multiple usages
        stats.record_tool_usage("tool1", "input1", "output1")
        stats.record_tool_usage("tool1", "input2", "output2")
        stats.record_tool_usage("tool2", "input3", "output3")
        
        # Check tool1 stats
        tool1_stats = stats.get_stats("tool1")
        assert tool1_stats.num_times_called == 2
        
        # Check tool2 stats
        tool2_stats = stats.get_stats("tool2")
        assert tool2_stats.num_times_called == 1
    
    def test_get_tool_stats_dict(self):
        """Test getting all tool stats as dictionary."""
        stats = ToolUsageStats()
        stats.record_tool_usage("tool1", "input1", "output1")
        stats.record_tool_usage("tool2", "input2", "output2")
        
        stats_dict = stats.get_tool_stats_dict()
        
        assert "tool1" in stats_dict
        assert "tool2" in stats_dict
        assert stats_dict["tool1"]["num_times_called"] == 1
        assert stats_dict["tool2"]["num_times_called"] == 1
    
    def test_clear(self):
        """Test clearing all stats."""
        stats = ToolUsageStats()
        stats.record_tool_usage("tool1", "input", "output")
        
        assert len(stats._tool_stats) > 0
        
        stats.clear()
        
        assert len(stats._tool_stats) == 0


class TestToolUsageStatsEntry:
    """Test the Entry nested class."""
    
    def test_entry_initialization(self):
        """Test Entry default values."""
        from serena.analytics import ToolUsageStats
        
        entry = ToolUsageStats.Entry()
        
        assert entry.num_times_called == 0
        assert entry.input_tokens == 0
        assert entry.output_tokens == 0
    
    def test_update_on_call(self):
        """Test updating entry with new usage data."""
        from serena.analytics import ToolUsageStats
        
        entry = ToolUsageStats.Entry()
        
        entry.update_on_call(10, 5)
        
        assert entry.num_times_called == 1
        assert entry.input_tokens == 10
        assert entry.output_tokens == 5
        
        entry.update_on_call(20, 15)
        
        assert entry.num_times_called == 2
        assert entry.input_tokens == 30
        assert entry.output_tokens == 20