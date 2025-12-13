"""Comprehensive tests for analytics module in src/serena/analytics.py"""

import threading
import time
from unittest.mock import Mock, patch, MagicMock
import pytest
from dataclasses import asdict
from copy import copy

from serena.analytics import (
    TokenCountEstimator,
    TiktokenCountEstimator,
    AnthropicTokenCount,
    CharCountEstimator,
    RegisteredTokenCountEstimator,
    ToolUsageStats
)


class MockTokenCountEstimator(TokenCountEstimator):
    """Mock token count estimator for testing."""
    
    def __init__(self, tokens_per_char: float = 0.25):
        self.tokens_per_char = tokens_per_char
    
    def estimate_token_count(self, text: str) -> int:
        """Estimate tokens based on character count."""
        return int(len(text) * self.tokens_per_char)


class TestTokenCountEstimator:
    """Test cases for TokenCountEstimator abstract base class."""

    def test_token_count_estimator_is_abstract(self):
        """Test that TokenCountEstimator cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TokenCountEstimator()

    def test_mock_token_count_estimator(self):
        """Test that mock implementation works correctly."""
        estimator = MockTokenCountEstimator(tokens_per_char=0.5)
        
        assert estimator.estimate_token_count("hello") == 2  # 5 chars * 0.5
        assert estimator.estimate_token_count("") == 0
        assert estimator.estimate_token_count("a" * 10) == 5


class TestTiktokenCountEstimator:
    """Test cases for TiktokenCountEstimator."""

    @patch('serena.analytics.tiktoken')
    def test_tiktoken_estimator_initialization(self, mock_tiktoken):
        """Test TiktokenCountEstimator initialization."""
        mock_encoder = Mock()
        mock_encoder.encode = Mock(return_value=[1, 2, 3, 4, 5])
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = TiktokenCountEstimator("cl100k_base")
        
        mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        assert estimator._encoding == mock_encoder

    @patch('serena.analytics.tiktoken')
    def test_estimate_token_count(self, mock_tiktoken):
        """Test token counting with TiktokenCountEstimator."""
        mock_encoder = Mock()
        mock_encoder.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = TiktokenCountEstimator("cl100k_base")
        
        result = estimator.estimate_token_count("Hello, world!")
        
        assert result == 5
        mock_encoder.encode.assert_called_once_with("Hello, world!")

    @patch('serena.analytics.tiktoken')
    def test_estimate_token_count_empty_string(self, mock_tiktoken):
        """Test token counting with empty string."""
        mock_encoder = Mock()
        mock_encoder.encode.return_value = []  # 0 tokens
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = TiktokenCountEstimator("cl100k_base")
        
        result = estimator.estimate_token_count("")
        
        assert result == 0
        mock_encoder.encode.assert_called_once_with("")

    @patch('serena.analytics.tiktoken')
    def test_estimate_token_count_unicode(self, mock_tiktoken):
        """Test token counting with Unicode characters."""
        mock_encoder = Mock()
        mock_encoder.encode.return_value = [1, 2, 3]  # 3 tokens for Unicode
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = TiktokenCountEstimator("cl100k_base")
        
        unicode_text = "Hello 🌍 world! 🚀"
        result = estimator.estimate_token_count(unicode_text)
        
        assert result == 3
        mock_encoder.encode.assert_called_once_with(unicode_text)


class TestAnthropicTokenCount:
    """Test cases for AnthropicTokenCount."""

    @patch('serena.analytics.tiktoken')
    def test_anthropic_token_count_initialization(self, mock_tiktoken):
        """Test AnthropicTokenCount initialization."""
        mock_encoder = Mock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoder
        
        estimator = AnthropicTokenCount("claude-3-sonnet-20240229")
        
        mock_tiktoken.encoding_for_model.assert_called_once_with("claude-3-sonnet-20240229")
        assert estimator._encoding == mock_encoder

    @patch('serena.analytics.tiktoken')
    def test_anthropic_estimate_token_count(self, mock_tiktoken):
        """Test token counting with AnthropicTokenCount."""
        mock_encoder = Mock()
        mock_encoder.encode.return_value = [1, 2, 3, 4, 5, 6, 7]  # 7 tokens
        mock_tiktoken.encoding_for_model.return_value = mock_encoder
        
        estimator = AnthropicTokenCount("claude-3-sonnet-20240229")
        
        result = estimator.estimate_token_count("This is a test string for Anthropic token counting.")
        
        assert result == 7
        mock_encoder.encode.assert_called_once_with("This is a test string for Anthropic token counting.")


class TestCharCountEstimator:
    """Test cases for CharCountEstimator."""

    def test_char_count_estimator_initialization(self):
        """Test CharCountEstimator initialization."""
        estimator = CharCountEstimator()
        assert estimator._chars_per_token == 4.0

    def test_char_count_estimator_custom_chars_per_token(self):
        """Test CharCountEstimator with custom chars_per_token."""
        estimator = CharCountEstimator(chars_per_token=5.0)
        assert estimator._chars_per_token == 5.0

    def test_estimate_token_count_basic(self):
        """Test basic token counting with CharCountEstimator."""
        estimator = CharCountEstimator(chars_per_token=4.0)
        
        # 16 characters / 4 = 4 tokens
        result = estimator.estimate_token_count("This is a test!")
        assert result == 4

    def test_estimate_token_count_empty_string(self):
        """Test token counting with empty string."""
        estimator = CharCountEstimator()
        
        result = estimator.estimate_token_count("")
        assert result == 0

    def test_estimate_token_count_rounding(self):
        """Test token counting with rounding."""
        estimator = CharCountEstimator(chars_per_token=3.0)
        
        # 10 characters / 3 = 3.33, should round up to 4
        result = estimator.estimate_token_count("1234567890")
        assert result == 4

    def test_estimate_token_count_exact_division(self):
        """Test token counting with exact division."""
        estimator = CharCountEstimator(chars_per_token=5.0)
        
        # 15 characters / 5 = 3 exactly
        result = estimator.estimate_token_count("123456789012345")
        assert result == 3

    def test_estimate_token_count_unicode(self):
        """Test token counting with Unicode characters."""
        estimator = CharCountEstimator(chars_per_token=4.0)
        
        # "Hello 🌍" has 8 characters (including the space and emoji)
        unicode_text = "Hello 🌍"
        result = estimator.estimate_token_count(unicode_text)
        assert result == 2  # 8 chars / 4 = 2 tokens


class TestRegisteredTokenCountEstimator:
    """Test cases for RegisteredTokenCountEstimator enum."""

    @patch('serena.analytics.tiktoken')
    def test_load_estimator_tiktoken_gpt4o(self, mock_tiktoken):
        """Test loading TIKTOKEN_GPT4O estimator."""
        mock_encoder = Mock()
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = RegisteredTokenCountEstimator.TIKTOKEN_GPT4O.load_estimator()
        
        mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        assert isinstance(estimator, TiktokenCountEstimator)

    @patch('serena.analytics.tiktoken')
    def test_load_estimator_tiktoken_gpt4(self, mock_tiktoken):
        """Test loading TIKTOKEN_GPT4 estimator."""
        mock_encoder = Mock()
        mock_tiktoken.get_encoding.return_value = mock_encoder
        
        estimator = RegisteredTokenCountEstimator.TIKTOKEN_GPT4.load_estimator()
        
        mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")
        assert isinstance(estimator, TiktokenCountEstimator)

    @patch('serena.analytics.tiktoken')
    def test_load_estimator_anthropic_claude3_sonnet(self, mock_tiktoken):
        """Test loading ANTHROPIC_CLAUDE3_SONNET estimator."""
        mock_encoder = Mock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoder
        
        estimator = RegisteredTokenCountEstimator.ANTHROPIC_CLAUDE3_SONNET.load_estimator()
        
        mock_tiktoken.encoding_for_model.assert_called_once_with("claude-3-sonnet-20240229")
        assert isinstance(estimator, AnthropicTokenCount)

    @patch('serena.analytics.tiktoken')
    def test_load_estimator_anthropic_claude3_haiku(self, mock_tiktoken):
        """Test loading ANTHROPIC_CLAUDE3_HAIKU estimator."""
        mock_encoder = Mock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoder
        
        estimator = RegisteredTokenCountEstimator.ANTHROPIC_CLAUDE3_HAIKU.load_estimator()
        
        mock_tiktoken.encoding_for_model.assert_called_once_with("claude-3-haiku-20240307")
        assert isinstance(estimator, AnthropicTokenCount)

    def test_load_estimator_char_count(self):
        """Test loading CHAR_COUNT estimator."""
        estimator = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()
        
        assert isinstance(estimator, CharCountEstimator)


class TestToolUsageStats:
    """Test cases for ToolUsageStats."""

    def test_init_default_estimator(self):
        """Test ToolUsageStats initialization with default estimator."""
        with patch('serena.analytics.tiktoken') as mock_tiktoken:
            mock_encoder = Mock()
            mock_encoder.encode.return_value = [1, 2, 3]
            mock_tiktoken.get_encoding.return_value = mock_encoder
            
            stats = ToolUsageStats()
            
            assert stats.token_estimator_name == "TIKTOKEN_GPT4O"
            assert isinstance(stats._token_count_estimator, TiktokenCountEstimator)
            assert len(stats._tool_stats) == 0

    def test_init_custom_estimator(self):
        """Test ToolUsageStats initialization with custom estimator."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        mock_estimator.estimate_token_count.return_value = 5
        
        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)
        
        assert stats.token_estimator_name == "CHAR_COUNT"
        assert stats._token_count_estimator == mock_estimator

    def test_entry_initialization(self):
        """Test Entry dataclass initialization."""
        entry = ToolUsageStats.Entry()
        
        assert entry.num_times_called == 0
        assert entry.input_tokens == 0
        assert entry.output_tokens == 0

    def test_entry_initialization_with_values(self):
        """Test Entry dataclass initialization with values."""
        entry = ToolUsageStats.Entry(
            num_times_called=5,
            input_tokens=100,
            output_tokens=200
        )
        
        assert entry.num_times_called == 5
        assert entry.input_tokens == 100
        assert entry.output_tokens == 200

    def test_entry_update_on_call(self):
        """Test Entry.update_on_call method."""
        entry = ToolUsageStats.Entry()
        
        entry.update_on_call(input_tokens=10, output_tokens=20)
        
        assert entry.num_times_called == 1
        assert entry.input_tokens == 10
        assert entry.output_tokens == 20

    def test_entry_multiple_updates(self):
        """Test multiple calls to Entry.update_on_call."""
        entry = ToolUsageStats.Entry()
        
        entry.update_on_call(input_tokens=10, output_tokens=20)
        entry.update_on_call(input_tokens=15, output_tokens=25)
        entry.update_on_call(input_tokens=5, output_tokens=10)
        
        assert entry.num_times_called == 3
        assert entry.input_tokens == 30  # 10 + 15 + 5
        assert entry.output_tokens == 55  # 20 + 25 + 10

    def test_get_stats_empty(self):
        """Test getting stats for a tool that hasn't been used."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        result = stats.get_stats("unused_tool")
        
        assert result.num_times_called == 0
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_get_stats_existing_tool(self):
        """Test getting stats for a tool that has been used."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        # Record some usage
        mock_estimator.estimate_token_count.side_effect = [10, 20]
        stats.record_tool_usage("test_tool", "input", "output")
        
        result = stats.get_stats("test_tool")
        
        assert result.num_times_called == 1
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy, not the original."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        # Record usage
        mock_estimator.estimate_token_count.side_effect = [10, 20]
        stats.record_tool_usage("test_tool", "input", "output")
        
        # Get stats and modify
        result = stats.get_stats("test_tool")
        result.num_times_called = 999
        
        # Original should be unchanged
        original = stats.get_stats("test_tool")
        assert original.num_times_called == 1

    @patch.object(ToolUsageStats, '_estimate_token_count')
    def test_record_tool_usage(self, mock_estimate):
        """Test recording tool usage."""
        mock_estimate.side_effect = [15, 25]  # input_tokens, output_tokens
        
        stats = ToolUsageStats()
        stats.record_tool_usage("test_tool", "input string", "output string")
        
        mock_estimate.assert_any_call("input string")
        mock_estimate.assert_any_call("output string")
        
        entry = stats.get_stats("test_tool")
        assert entry.num_times_called == 1
        assert entry.input_tokens == 15
        assert entry.output_tokens == 25

    @patch.object(ToolUsageStats, '_estimate_token_count')
    def test_record_multiple_tool_usage(self, mock_estimate):
        """Test recording multiple tool usage events."""
        # Simulate different token counts for each call
        mock_estimate.side_effect = [10, 20, 15, 25]  # input1, output1, input2, output2
        
        stats = ToolUsageStats()
        stats.record_tool_usage("test_tool", "input1", "output1")
        stats.record_tool_usage("test_tool", "input2", "output2")
        
        entry = stats.get_stats("test_tool")
        assert entry.num_times_called == 2
        assert entry.input_tokens == 25  # 10 + 15
        assert entry.output_tokens == 45  # 20 + 25

    @patch.object(ToolUsageStats, '_estimate_token_count')
    def test_record_different_tools(self, mock_estimate):
        """Test recording usage for different tools."""
        mock_estimate.side_effect = [10, 20, 5, 15]  # tool1 input/output, tool2 input/output
        
        stats = ToolUsageStats()
        stats.record_tool_usage("tool1", "input1", "output1")
        stats.record_tool_usage("tool2", "input2", "output2")
        
        tool1_stats = stats.get_stats("tool1")
        tool2_stats = stats.get_stats("tool2")
        
        assert tool1_stats.num_times_called == 1
        assert tool1_stats.input_tokens == 10
        assert tool1_stats.output_tokens == 20
        
        assert tool2_stats.num_times_called == 1
        assert tool2_stats.input_tokens == 5
        assert tool2_stats.output_tokens == 15

    def test_estimate_token_count(self):
        """Test internal token estimation method."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        mock_estimator.estimate_token_count.return_value = 42
        
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        result = stats._estimate_token_count("test text")
        
        assert result == 42
        mock_estimator.estimate_token_count.assert_called_once_with("test text")

    def test_get_tool_stats_dict_empty(self):
        """Test getting tool stats dict when no tools have been used."""
        stats = ToolUsageStats()
        
        result = stats.get_tool_stats_dict()
        
        assert result == {}

    @patch.object(ToolUsageStats, '_estimate_token_count')
    def test_get_tool_stats_dict_with_data(self, mock_estimate):
        """Test getting tool stats dict with tool usage data."""
        mock_estimate.side_effect = [10, 20, 15, 25]
        
        stats = ToolUsageStats()
        stats.record_tool_usage("tool1", "input1", "output1")
        stats.record_tool_usage("tool2", "input2", "output2")
        
        result = stats.get_tool_stats_dict()
        
        expected = {
            "tool1": {
                "num_times_called": 1,
                "input_tokens": 10,
                "output_tokens": 20
            },
            "tool2": {
                "num_times_called": 1,
                "input_tokens": 15,
                "output_tokens": 25
            }
        }
        
        assert result == expected

    def test_clear_empty_stats(self):
        """Test clearing stats when no tools have been used."""
        stats = ToolUsageStats()
        
        # Should not raise any exception
        stats.clear()
        assert len(stats._tool_stats) == 0

    @patch.object(ToolUsageStats, '_estimate_token_count')
    def test_clear_with_data(self, mock_estimate):
        """Test clearing stats with existing tool usage data."""
        mock_estimate.side_effect = [10, 20]
        
        stats = ToolUsageStats()
        stats.record_tool_usage("test_tool", "input", "output")
        
        # Verify data exists
        assert len(stats._tool_stats) == 1
        
        # Clear and verify
        stats.clear()
        assert len(stats._tool_stats) == 0

    def test_thread_safety_concurrent_recording(self):
        """Test that concurrent recording is thread-safe."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        mock_estimator.estimate_token_count.return_value = 5
        
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        def record_usage():
            for i in range(10):
                stats.record_tool_usage("concurrent_tool", f"input_{i}", f"output_{i}")
        
        # Create multiple threads recording usage concurrently
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_usage)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all recordings were captured
        entry = stats.get_stats("concurrent_tool")
        assert entry.num_times_called == 50  # 5 threads * 10 recordings each
        assert entry.input_tokens == 250  # 50 * 5 tokens
        assert entry.output_tokens == 250  # 50 * 5 tokens

    def test_thread_safety_concurrent_reads(self):
        """Test that concurrent reads are thread-safe."""
        mock_estimator = Mock(spec=TokenCountEstimator)
        mock_estimator.estimate_token_count.return_value = 10
        
        stats = ToolUsageStats()
        stats._token_count_estimator = mock_estimator
        
        # Record initial data
        stats.record_tool_usage("test_tool", "input", "output")
        
        results = []
        errors = []
        
        def read_stats():
            try:
                for _ in range(100):
                    entry = stats.get_stats("test_tool")
                    results.append((entry.num_times_called, entry.input_tokens, entry.output_tokens))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads reading stats concurrently
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=read_stats)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred and all reads returned consistent data
        assert len(errors) == 0
        assert len(results) == 1000  # 10 threads * 100 reads each
        assert all(call_count == 1 and input_tokens == 10 and output_tokens == 10 
                  for call_count, input_tokens, output_tokens in results)