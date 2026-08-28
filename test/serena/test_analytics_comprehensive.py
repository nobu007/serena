"""Comprehensive tests for the analytics module to achieve 90%+ coverage."""

import sys
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from serena.analytics import (
    AnthropicTokenCount,
    CharCountEstimator,
    RegisteredTokenCountEstimator,
    TiktokenCountEstimator,
    TokenCountEstimator,
    ToolUsageStats,
    _registered_token_estimator_instances_cache,
)


class TestTokenCountEstimator:
    """Test the abstract base class for token estimators."""

    def test_abstract_methods(self):
        """Test that TokenCountEstimator is indeed abstract."""
        with pytest.raises(TypeError):
            TokenCountEstimator()


class TestCharCountEstimator:
    """Test CharCountEstimator implementation."""

    @pytest.mark.parametrize(
        "text,chars_per_token,expected",
        [
            ("", 4, 0),
            ("hello", 4, 1),  # floor(5 / 4) = 1
            ("abcdefghij", 2, 5),  # floor(10 / 2) = 5
            ("😀😁😂", 4, 0),  # floor(3 / 4) = 0
        ],
    )
    def test_estimate_token_count(self, text, chars_per_token, expected):
        estimator = CharCountEstimator(chars_per_token)
        result = estimator.estimate_token_count(text)
        assert result == expected

    def test_default_chars_per_token(self):
        """Test default value."""
        estimator = CharCountEstimator()
        assert estimator._avg_chars_per_token == 4


class TestTiktokenCountEstimator:
    """Test TiktokenCountEstimator implementation."""

    def test_initialization_default_model(self):
        mock_tiktoken = MagicMock()
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1, 2, 3]
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        with patch.dict(sys.modules, {"tiktoken": mock_tiktoken}):
            estimator = TiktokenCountEstimator()

        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4o")
        assert estimator._encoding == mock_encoding

    def test_initialization_custom_model(self):
        mock_tiktoken = MagicMock()
        mock_encoding = Mock()
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        with patch.dict(sys.modules, {"tiktoken": mock_tiktoken}):
            estimator = TiktokenCountEstimator("gpt-3.5-turbo")

        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-3.5-turbo")
        assert estimator._encoding == mock_encoding

    def test_estimate_token_count(self):
        mock_tiktoken = MagicMock()
        mock_encoding = Mock()
        mock_encoding.encode.return_value = [1, 2, 3, 4]
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        with patch.dict(sys.modules, {"tiktoken": mock_tiktoken}):
            estimator = TiktokenCountEstimator()

        result = estimator.estimate_token_count("test text")

        assert result == 4
        mock_encoding.encode.assert_called_once_with("test text")


class TestAnthropicTokenCount:
    """Test AnthropicTokenCount implementation."""

    @patch("anthropic.Anthropic")
    def test_initialization_default_values(self, mock_anthropic):
        estimator = AnthropicTokenCount()

        mock_anthropic.assert_called_once_with(api_key=None)
        assert estimator._model_name == "claude-sonnet-4-20250514"

    @patch("anthropic.Anthropic")
    def test_initialization_with_custom_values(self, mock_anthropic):
        estimator = AnthropicTokenCount(
            model_name="claude-3-haiku-20240307",
            api_key="test-key",
        )

        mock_anthropic.assert_called_once_with(api_key="test-key")
        assert estimator._model_name == "claude-3-haiku-20240307"

    @patch("anthropic.Anthropic")
    def test_estimate_token_count(self, mock_anthropic):
        mock_client = Mock()
        mock_tokens_count = Mock()
        mock_tokens_count.input_tokens = 42
        mock_client.messages.count_tokens.return_value = mock_tokens_count
        mock_anthropic.return_value = mock_client

        estimator = AnthropicTokenCount(api_key="test-key")
        result = estimator.estimate_token_count("test text")

        assert result == 42
        mock_client.messages.count_tokens.assert_called_once()


@pytest.fixture(autouse=True)
def _reset_estimator_cache():
    """Keep estimator-cache tests independent of each other and of execution order."""
    _registered_token_estimator_instances_cache.clear()
    yield
    _registered_token_estimator_instances_cache.clear()


class TestRegisteredTokenCountEstimator:
    """Test the enum and its methods."""

    def test_get_valid_names(self):
        names = RegisteredTokenCountEstimator.get_valid_names()
        expected_names = [
            "TIKTOKEN_GPT4O",
            "ANTHROPIC_CLAUDE_SONNET_4",
            "CHAR_COUNT",
        ]
        assert set(names) == set(expected_names)

    def test_load_estimator_caching(self):
        """Test that estimator instances are cached."""
        estimator1 = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()
        estimator2 = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()

        assert estimator1 is estimator2
        assert isinstance(estimator1, CharCountEstimator)

    @patch("serena.analytics.TiktokenCountEstimator")
    def test_load_tiktoken_estimator(self, mock_tiktoken_class):
        mock_estimator = Mock()
        mock_tiktoken_class.return_value = mock_estimator

        estimator = RegisteredTokenCountEstimator.TIKTOKEN_GPT4O.load_estimator()

        assert estimator is mock_estimator
        mock_tiktoken_class.assert_called_once_with(model_name="gpt-4o")

    @patch("serena.analytics.CharCountEstimator")
    def test_load_char_count_estimator(self, mock_char_class):
        mock_estimator = Mock()
        mock_char_class.return_value = mock_estimator

        estimator = RegisteredTokenCountEstimator.CHAR_COUNT.load_estimator()

        assert estimator is mock_estimator
        mock_char_class.assert_called_once_with(avg_chars_per_token=4)

    @patch("serena.analytics.AnthropicTokenCount")
    def test_load_anthropic_estimator(self, mock_anthropic_class):
        mock_estimator = Mock()
        mock_anthropic_class.return_value = mock_estimator

        estimator = RegisteredTokenCountEstimator.ANTHROPIC_CLAUDE_SONNET_4.load_estimator()

        assert estimator is mock_estimator
        mock_anthropic_class.assert_called_once_with(model_name="claude-sonnet-4-20250514")

    def test_unknown_estimator_name_rejected(self):
        """Only registered names can construct the enum."""
        with pytest.raises(ValueError):
            RegisteredTokenCountEstimator("UNKNOWN")


class TestToolUsageStats:
    """Test ToolUsageStats class."""

    def test_initialization_default(self):
        mock_estimator = Mock()
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.TIKTOKEN_GPT4O] = mock_estimator

        stats = ToolUsageStats()

        assert stats._token_count_estimator == mock_estimator
        assert stats.token_estimator_name == "TIKTOKEN_GPT4O"
        assert len(stats._tool_stats) == 0

    def test_record_tool_usage(self):
        """Test recording tool usage statistics."""
        mock_estimator = Mock()
        mock_estimator.estimate_token_count.side_effect = [10, 5, 12, 6]  # 2 calls per record
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.CHAR_COUNT] = mock_estimator

        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)
        stats.record_tool_usage("test_tool", "input text", "output text")
        stats.record_tool_usage("test_tool", "input text 2", "output text 2")

        tool_stats = stats.get_stats("test_tool")
        assert tool_stats.num_times_called == 2
        assert tool_stats.input_tokens == 22  # 10 + 12
        assert tool_stats.output_tokens == 11  # 5 + 6

    def test_get_tool_stats_dict(self):
        """Test getting all tool stats as dictionary."""
        mock_estimator = Mock()
        mock_estimator.estimate_token_count.side_effect = [5, 3, 5, 3]
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.CHAR_COUNT] = mock_estimator

        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)
        stats.record_tool_usage("tool1", "input1", "output1")
        stats.record_tool_usage("tool2", "input2", "output2")

        stats_dict = stats.get_tool_stats_dict()

        expected = {
            "tool1": {"num_times_called": 1, "input_tokens": 5, "output_tokens": 3},
            "tool2": {"num_times_called": 1, "input_tokens": 5, "output_tokens": 3},
        }
        assert stats_dict == expected

    def test_clear(self):
        """Test clearing all stats."""
        mock_estimator = Mock()
        mock_estimator.estimate_token_count.return_value = 1
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.CHAR_COUNT] = mock_estimator

        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)
        stats.record_tool_usage("tool1", "input", "output")

        assert len(stats._tool_stats) > 0

        stats.clear()

        assert len(stats._tool_stats) == 0

    def test_thread_safety(self):
        """Test that the stats are thread-safe."""
        mock_estimator = Mock()
        mock_estimator.estimate_token_count.return_value = 1
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.CHAR_COUNT] = mock_estimator

        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)

        def record_usage(tool_name, iterations):
            for i in range(iterations):
                stats.record_tool_usage(tool_name, f"input_{i}", f"output_{i}")

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=record_usage, args=(f"tool_{i}", 10))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all tool usage was recorded
        stats_dict = stats.get_tool_stats_dict()
        assert len(stats_dict) == 5

        for tool_stats in stats_dict.values():
            assert tool_stats["num_times_called"] == 10
            assert tool_stats["input_tokens"] == 10
            assert tool_stats["output_tokens"] == 10

    def test_get_stats_returns_copy(self):
        """Test that get_stats returns a copy, not the original."""
        mock_estimator = Mock()
        mock_estimator.estimate_token_count.return_value = 5
        _registered_token_estimator_instances_cache[RegisteredTokenCountEstimator.CHAR_COUNT] = mock_estimator

        stats = ToolUsageStats(RegisteredTokenCountEstimator.CHAR_COUNT)
        stats.record_tool_usage("test_tool", "input", "output")

        stats1 = stats.get_stats("test_tool")
        stats2 = stats.get_stats("test_tool")

        # Modifying one shouldn't affect the other
        stats1.num_times_called = 999

        assert stats2.num_times_called == 1
        assert stats.get_stats("test_tool").num_times_called == 1


class TestToolUsageStatsEntry:
    """Test the Entry nested class."""

    def test_update_on_call(self):
        entry = ToolUsageStats.Entry()

        assert entry.num_times_called == 0
        assert entry.input_tokens == 0
        assert entry.output_tokens == 0

        entry.update_on_call(10, 5)

        assert entry.num_times_called == 1
        assert entry.input_tokens == 10
        assert entry.output_tokens == 5

        entry.update_on_call(20, 15)

        assert entry.num_times_called == 2
        assert entry.input_tokens == 30
        assert entry.output_tokens == 20
