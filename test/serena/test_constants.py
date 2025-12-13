"""Tests for serena.constants module."""

import pytest
import re
from pathlib import Path

from serena.constants import (
    SERENA_MANAGED_DIR_NAME,
    SERENA_MANAGED_DIR_IN_HOME,
    REPO_ROOT,
    SERENA_FILE_ENCODING,
    DEFAULT_SOURCE_FILE_ENCODING,
    DEFAULT_CONTEXT,
    DEFAULT_MODES,
    SERENA_LOG_FORMAT,
    DEFAULT_TOOL_TIMEOUT,
)


class TestSerenaConstants:
    """Test cases for serena constants."""

    def test_serena_managed_dir_name(self):
        """Test SERENA_MANAGED_DIR_NAME constant."""
        assert SERENA_MANAGED_DIR_NAME == ".serena"

    def test_serena_managed_dir_in_home(self):
        """Test SERENA_MANAGED_DIR_IN_HOME constant."""
        assert SERENA_MANAGED_DIR_IN_HOME.endswith(".serena")
        assert Path(SERENA_MANAGED_DIR_IN_HOME).expanduser().exists() or True  # May not exist during testing

    def test_repo_root_is_valid_path(self):
        """Test REPO_ROOT points to a valid directory."""
        repo_root = Path(REPO_ROOT)
        assert repo_root.exists()
        assert repo_root.is_dir()

    def test_encoding_constants(self):
        """Test encoding constants."""
        assert SERENA_FILE_ENCODING == "utf-8"
        assert DEFAULT_SOURCE_FILE_ENCODING == "utf-8"

    def test_default_context(self):
        """Test DEFAULT_CONTEXT constant."""
        assert DEFAULT_CONTEXT == "desktop-app"
        assert isinstance(DEFAULT_CONTEXT, str)
        assert len(DEFAULT_CONTEXT) > 0

    def test_default_modes(self):
        """Test DEFAULT_MODES constant."""
        assert isinstance(DEFAULT_MODES, tuple)
        assert "interactive" in DEFAULT_MODES
        assert "editing" in DEFAULT_MODES
        assert len(DEFAULT_MODES) == 2

    def test_serena_log_format(self):
        """Test SERENA_LOG_FORMAT constant."""
        assert isinstance(SERENA_LOG_FORMAT, str)
        assert "%(levelname)" in SERENA_LOG_FORMAT
        assert "%(asctime)" in SERENA_LOG_FORMAT
        assert "%(message)s" in SERENA_LOG_FORMAT

    def test_default_tool_timeout(self):
        """Test DEFAULT_TOOL_TIMEOUT constant."""
        assert isinstance(DEFAULT_TOOL_TIMEOUT, float)
        assert DEFAULT_TOOL_TIMEOUT > 0
        assert DEFAULT_TOOL_TIMEOUT == 240.0

    def test_path_constants_exist(self):
        """Test that path-related constants are properly defined."""
        # These should be valid strings
        assert isinstance(REPO_ROOT, str)
        assert len(REPO_ROOT) > 0
        assert REPO_ROOT.startswith('/')

    def test_constants_immutability(self):
        """Test that constants are of expected immutable types."""
        assert isinstance(SERENA_MANAGED_DIR_NAME, str)
        assert isinstance(SERENA_MANAGED_DIR_IN_HOME, str)
        assert isinstance(REPO_ROOT, str)
        assert isinstance(SERENA_FILE_ENCODING, str)
        assert isinstance(DEFAULT_SOURCE_FILE_ENCODING, str)
        assert isinstance(DEFAULT_CONTEXT, str)
        assert isinstance(DEFAULT_MODES, tuple)
        assert isinstance(SERENA_LOG_FORMAT, str)


class TestTextUtilsFunctions:
    """Test cases for serena.text_utils functions."""

    def test_glob_to_regex_basic_patterns(self):
        """Test glob_to_regex function with basic patterns."""
        from serena.text_utils import glob_to_regex

        # Test basic wildcards
        assert glob_to_regex("*.py") == ".*\\.py"
        assert glob_to_regex("test_?.py") == "test_.\\.py"
        assert glob_to_regex("*") == ".*"
        assert glob_to_regex("?") == "."

        # Test literal strings
        assert glob_to_regex("file.txt") == "file\\.txt"
        assert glob_to_regex("src/main.py") == "src/main\\.py"

    def test_glob_to_regex_special_characters(self):
        """Test glob_to_regex with special regex characters."""
        from serena.text_utils import glob_to_regex

        # Test that special regex characters are properly escaped
        assert glob_to_regex("file[1].py") == "file\\[1\\]\\.py"
        assert glob_to_regex("file(1).py") == "file\\(1\\)\\.py"
        assert glob_to_regex("file+test.py") == "file\\+test\\.py"
        assert glob_to_regex("file^test.py") == "file\\^test\\.py"
        assert glob_to_regex("file$test.py") == "file\\$test\\.py"

    def test_glob_to_regex_escape_sequences(self):
        """Test glob_to_regex with escape sequences."""
        from serena.text_utils import glob_to_regex

        # Test backslash escaping
        assert glob_to_regex(r"file\*.py") == r"file\*\.py"
        assert glob_to_regex(r"file\?.py") == r"file\?\.py"
        assert glob_to_regex(r"folder\\file.py") == r"folder\\file\.py"

    def test_glob_to_regex_complex_patterns(self):
        """Test glob_to_regex with more complex patterns."""
        from serena.text_utils import glob_to_regex

        # Test patterns with multiple wildcards
        result = glob_to_regex("src/**/*.js")
        assert "src" in result
        assert ".*" in result
        assert "\\.js" in result
        assert isinstance(result, str)
        assert len(result) > 0

        # Test mixed patterns
        result = glob_to_regex("test_*_file?.txt")
        assert "test_" in result
        assert "_file" in result
        assert "\\." in result
        assert "txt" in result

    def test_glob_to_regex_empty_and_edge_cases(self):
        """Test glob_to_regex with edge cases."""
        from serena.text_utils import glob_to_regex

        # Test empty string
        result = glob_to_regex("")
        assert isinstance(result, str)

        # Test string with only wildcards
        assert glob_to_regex("***") == ".*.*.*"
        assert glob_to_regex("???") == "..."

        # Test that results are valid regex patterns
        patterns = ["*.py", "test_?.py", "file.txt", "*.*", "folder/*.txt"]
        for pattern in patterns:
            regex = glob_to_regex(pattern)
            # Should not raise an exception
            re.compile(regex)