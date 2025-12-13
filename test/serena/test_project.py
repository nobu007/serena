"""Comprehensive tests for the Project class in src/serena/project.py"""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import yaml

from serena.project import Project, MemoriesManager
from serena.config.project_config import ProjectConfig, Language
from serena.util.exception import ProjectNotFoundError


class TestProject:
    """Test cases for the Project class."""

    def setup_method(self):
        """Set up a temporary project directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        self.project_name = "test_project"
        
        # Create a basic project configuration
        self.project_config = Mock(spec=ProjectConfig)
        self.project_config.project_name = self.project_name
        self.project_config.languages = [Language.PYTHON]
        self.project_config.encoding = "utf-8"
        self.project_config.ignored_paths = []
        self.project_config.ignore_all_files_in_gitignore = False
        self.project_config.initial_prompt = ""
        self.project_config.rel_path_to_project_yml.return_value = ".serena/project.yml"

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_project_initialization_basic(self):
        """Test basic project initialization."""
        project = Project(self.project_root, self.project_config)
        
        assert project.project_root == self.project_root
        assert project.project_name == self.project_name
        assert project.project_config == self.project_config
        assert isinstance(project.memories_manager, MemoriesManager)
        assert project.language_server_manager is None

    def test_project_initialization_creates_gitignore(self):
        """Test that project initialization creates .gitignore in serena data folder."""
        project = Project(self.project_root, self.project_config)
        
        serena_data_path = project.path_to_serena_data_folder()
        gitignore_path = os.path.join(serena_data_path, ".gitignore")
        
        assert os.path.exists(gitignore_path)
        with open(gitignore_path, "r") as f:
            content = f.read()
            assert "/.serena_cache" in content

    def test_project_initialization_with_ignored_paths(self):
        """Test project initialization with ignored paths configuration."""
        self.project_config.ignored_paths = ["*.log", "temp/"]
        
        project = Project(self.project_root, self.project_config)
        
        assert len(project._ignored_patterns) == 2
        assert "*.log" in project._ignored_patterns
        assert "temp/" in project._ignored_patterns

    @patch('serena.project.GitignoreParser')
    def test_project_initialization_with_gitignore_integration(self, mock_gitignore_parser):
        """Test project initialization with gitignore file processing."""
        self.project_config.ignore_all_files_in_gitignore = True
        
        mock_parser_instance = Mock()
        mock_parser_instance.get_ignore_specs.return_value = [
            Mock(patterns=["*.pyc", "__pycache__/"])
        ]
        mock_gitignore_parser.return_value = mock_parser_instance
        
        project = Project(self.project_root, self.project_config)
        
        mock_gitignore_parser.assert_called_once_with(self.project_root)
        assert "*.pyc" in project._ignored_patterns
        assert "__pycache__/" in project._ignored_patterns

    def test_project_name_property(self):
        """Test the project_name property."""
        project = Project(self.project_root, self.project_config)
        assert project.project_name == self.project_name

    def test_load_existing_project(self):
        """Test loading an existing project."""
        # Create the necessary project files
        serena_dir = os.path.join(self.project_root, ".serena")
        os.makedirs(serena_dir)
        
        project_config_data = {
            'project_name': self.project_name,
            'languages': ['PYTHON'],
            'encoding': 'utf-8',
            'ignored_paths': [],
            'ignore_all_files_in_gitignore': False
        }
        
        config_path = os.path.join(serena_dir, "project.yml")
        with open(config_path, "w") as f:
            yaml.dump(project_config_data, f)
        
        # Mock ProjectConfig.load to return our mock
        with patch('serena.project.ProjectConfig.load') as mock_load:
            mock_load.return_value = self.project_config
            
            project = Project.load(self.project_root)
            
            assert project.project_root == self.project_root
            assert project.project_config == self.project_config
            mock_load.assert_called_once_with(Path(self.project_root).resolve(), autogenerate=True)

    def test_load_nonexistent_project(self):
        """Test loading a project that doesn't exist."""
        nonexistent_path = "/path/that/does/not/exist"
        
        with pytest.raises(FileNotFoundError, match="Project root not found"):
            Project.load(nonexistent_path)

    @patch('serena.project.save_yaml')
    @patch('serena.project.ProjectConfig.load_commented_map')
    def test_save_config(self, mock_load_commented, mock_save_yaml):
        """Test saving project configuration."""
        mock_commented_map = {}
        mock_load_commented.return_value = mock_commented_map
        
        project = Project(self.project_root, self.project_config)
        self.project_config.to_yaml_dict.return_value = {"test": "data"}
        
        project.save_config()
        
        config_path = os.path.join(self.project_root, ".serena", "project.yml")
        mock_load_commented.assert_called_once_with(config_path)
        mock_save_yaml.assert_called_once_with(
            config_path, 
            mock_commented_map, 
            preserve_comments=True
        )

    def test_path_to_serena_data_folder(self):
        """Test getting the path to the serena data folder."""
        project = Project(self.project_root, self.project_config)
        expected_path = os.path.join(self.project_root, ".serena")
        assert project.path_to_serena_data_folder() == expected_path

    def test_path_to_project_yml(self):
        """Test getting the path to the project.yml file."""
        project = Project(self.project_root, self.project_config)
        expected_path = os.path.join(self.project_root, ".serena", "project.yml")
        assert project.path_to_project_yml() == expected_path

    def test_get_activation_message_new_project(self):
        """Test getting activation message for a newly created project."""
        project = Project(self.project_root, self.project_config, is_newly_created=True)
        
        # Mock memories
        project.memories_manager.list_memories.return_value = ["memory1.md", "memory2.md"]
        
        message = project.get_activation_message()
        
        assert f"Created and activated a new project with name '{self.project_name}'" in message
        assert "Programming languages: PYTHON" in message
        assert "Available project memories" in message

    def test_get_activation_message_existing_project(self):
        """Test getting activation message for an existing project."""
        project = Project(self.project_root, self.project_config, is_newly_created=False)
        
        # Mock memories
        project.memories_manager.list_memories.return_value = []
        
        message = project.get_activation_message()
        
        assert f"The project with name '{self.project_name}' at {self.project_root} is activated" in message
        assert "Programming languages: PYTHON" in message
        assert "Available project memories" not in message

    def test_get_activation_message_with_initial_prompt(self):
        """Test getting activation message with initial prompt."""
        self.project_config.initial_prompt = "This is a custom instruction"
        project = Project(self.project_root, self.project_config)
        
        project.memories_manager.list_memories.return_value = []
        
        message = project.get_activation_message()
        
        assert "Additional project-specific instructions:" in message
        assert "This is a custom instruction" in message

    @patch('serena.project.FileUtils.read_file')
    def test_read_file(self, mock_read_file):
        """Test reading a file relative to the project root."""
        project = Project(self.project_root, self.project_config)
        mock_read_file.return_value = "file content"
        
        content = project.read_file("src/main.py")
        
        expected_path = os.path.join(self.project_root, "src", "main.py")
        mock_read_file.assert_called_once_with(expected_path, "utf-8")
        assert content == "file content"

    def test_is_ignored_relative_path_project_root(self):
        """Test that project root and empty string are never ignored."""
        project = Project(self.project_root, self.project_config)
        
        assert not project._is_ignored_relative_path(".")
        assert not project._is_ignored_relative_path("")

    def test_is_ignored_relative_path_nonexistent_file(self):
        """Test that checking a nonexistent file raises FileNotFoundError."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="not found"):
            project._is_ignored_relative_path("nonexistent.txt")

    def test_is_ignored_relative_path_git_directory(self):
        """Test that .git directory is always ignored."""
        project = Project(self.project_root, self.project_config)
        
        # Create .git directory
        git_dir = os.path.join(self.project_root, ".git")
        os.makedirs(git_dir)
        
        assert project._is_ignored_relative_path(".git")
        assert project._is_ignored_relative_path(".git/objects")

    @patch('serena.project.match_path')
    def test_is_ignored_relative_path_with_match(self, mock_match_path):
        """Test ignored path with pattern matching."""
        mock_match_path.return_value = True
        project = Project(self.project_root, self.project_config)
        self.project_config.ignored_paths = ["*.log"]
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.log")
        with open(test_file, "w") as f:
            f.write("log content")
        
        result = project._is_ignored_relative_path("test.log")
        
        assert result is True

    def test_is_ignored_path_absolute_path_outside_project(self):
        """Test that absolute paths outside the project are ignored."""
        project = Project(self.project_root, self.project_config)
        
        outside_path = "/some/other/directory/file.txt"
        
        with patch('serena.project.log') as mock_log:
            result = project.is_ignored_path(outside_path)
            
            assert result is True
            mock_log.warning.assert_called_once()

    def test_is_ignored_path_absolute_path_inside_project(self):
        """Test absolute paths inside the project are processed normally."""
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        with patch.object(project, '_is_ignored_relative_path', return_value=False) as mock_check:
            result = project.is_ignored_path(test_file)
            
            assert result is False
            mock_check.assert_called_once_with("test.txt", ignore_non_source_files=False)

    def test_is_path_in_project_relative_path(self):
        """Test checking if a relative path is in the project."""
        project = Project(self.project_root, self.project_config)
        
        assert project.is_path_in_project("src/main.py")
        assert project.is_path_in_project(".")
        assert not project.is_path_in_project("../outside.txt")

    def test_is_path_in_project_absolute_path(self):
        """Test checking if an absolute path is in the project."""
        project = Project(self.project_root, self.project_config)
        
        inside_path = os.path.join(self.project_root, "src", "main.py")
        outside_path = os.path.join(os.path.dirname(self.project_root), "outside.txt")
        
        assert project.is_path_in_project(inside_path)
        assert not project.is_path_in_project(outside_path)

    def test_relative_path_exists_true(self):
        """Test checking if a relative path exists (true case)."""
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        assert project.relative_path_exists("test.txt") is True

    def test_relative_path_exists_false(self):
        """Test checking if a relative path exists (false case)."""
        project = Project(self.project_root, self.project_config)
        
        assert project.relative_path_exists("nonexistent.txt") is False

    def test_validate_relative_path_success(self):
        """Test successful path validation."""
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        # Should not raise any exception
        project.validate_relative_path("test.txt")

    def test_validate_relative_path_outside_project(self):
        """Test validation fails for path outside project."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(ValueError, match="points to path outside of the repository root"):
            project.validate_relative_path("../outside.txt")

    @patch.object(Project, 'is_ignored_path')
    def test_validate_relative_path_ignored_path(self, mock_is_ignored):
        """Test validation fails for ignored path when required."""
        mock_is_ignored.return_value = True
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(ValueError, match="is ignored; cannot access for safety reasons"):
            project.validate_relative_path("test.txt", require_not_ignored=True)

    @patch('serena.project.os.walk')
    @patch.object(Project, 'is_ignored_path')
    def test_gather_source_files_file_path(self, mock_is_ignored, mock_walk):
        """Test gathering source files when path is a file."""
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        result = project.gather_source_files("test.txt")
        
        assert result == ["test.txt"]
        mock_walk.assert_not_called()

    @patch('serena.project.os.walk')
    @patch.object(Project, 'is_ignored_path')
    def test_gather_source_files_directory(self, mock_is_ignored, mock_walk):
        """Test gathering source files from a directory."""
        project = Project(self.project_root, self.project_config)
        
        # Mock directory walk
        mock_walk.return_value = [
            (self.project_root, ["src"], ["main.py", "README.md"]),
            (os.path.join(self.project_root, "src"), [], ["utils.py"])
        ]
        
        # Mock is_ignored_path to return False for source files, True for README
        def mock_is_ignored_func(path, ignore_non_source_files=False):
            if "README.md" in path and ignore_non_source_files:
                return True
            return False
        
        mock_is_ignored.side_effect = mock_is_ignored_func
        
        # Mock language file matcher
        mock_language = Mock()
        mock_matcher = Mock()
        mock_matcher.is_relevant_filename.return_value = True
        mock_language.get_source_fn_matcher.return_value = mock_matcher
        
        self.project_config.languages = [mock_language]
        
        result = project.gather_source_files()
        
        # Should include .py files but not README.md when ignore_non_source_files=True
        assert any("main.py" in path for path in result)
        assert any("utils.py" in path for path in result)

    def test_gather_source_files_nonexistent_path(self):
        """Test gathering source files from nonexistent path."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="Relative path .* not found"):
            project.gather_source_files("nonexistent")

    @patch.object(Project, 'gather_source_files')
    @patch('serena.project.search_files')
    def test_search_source_files_for_pattern(self, mock_search_files, mock_gather):
        """Test searching source files for a pattern."""
        project = Project(self.project_root, self.project_config)
        
        mock_gather.return_value = ["file1.py", "file2.py"]
        mock_search_files.return_value = ["match1", "match2"]
        
        result = project.search_source_files_for_pattern(
            pattern="test_pattern",
            context_lines_before=2,
            context_lines_after=3
        )
        
        assert result == ["match1", "match2"]
        mock_gather.assert_called_once_with(relative_path="")
        mock_search_files.assert_called_once()

    @patch.object(Project, 'read_file')
    @patch('serena.project.MatchedConsecutiveLines')
    def test_retrieve_content_around_line(self, mock_matched_lines, mock_read_file):
        """Test retrieving content around a specific line."""
        project = Project(self.project_root, self.project_config)
        
        mock_read_file.return_value = "file content"
        mock_instance = Mock()
        mock_matched_lines.from_file_contents.return_value = mock_instance
        
        result = project.retrieve_content_around_line(
            "test.py",
            line=10,
            context_lines_before=5,
            context_lines_after=5
        )
        
        assert result == mock_instance
        mock_read_file.assert_called_once_with("test.py")
        mock_matched_lines.from_file_contents.assert_called_once_with(
            "file content",
            line=10,
            context_lines_before=5,
            context_lines_after=5,
            source_file_path="test.py"
        )

    def test_shutdown_with_language_server_manager(self):
        """Test project shutdown with active language server manager."""
        project = Project(self.project_root, self.project_config)
        
        mock_ls_manager = Mock()
        project.language_server_manager = mock_ls_manager
        
        project.shutdown()
        
        mock_ls_manager.stop_all.assert_called_once_with(save_cache=True)
        assert project.language_server_manager is None

    def test_shutdown_without_language_server_manager(self):
        """Test project shutdown without active language server manager."""
        project = Project(self.project_root, self.project_config)
        
        # Should not raise any exception
        project.shutdown()
        assert project.language_server_manager is None


class TestProjectIntegration:
    """Integration tests for Project class."""

    def setup_method(self):
        """Set up a complete project structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = self.temp_dir
        
        # Create .serena directory and project.yml
        serena_dir = os.path.join(self.project_root, ".serena")
        os.makedirs(serena_dir)
        
        project_config = {
            'project_name': 'integration_test_project',
            'languages': ['PYTHON'],
            'encoding': 'utf-8',
            'ignored_paths': ['*.log', '__pycache__/'],
            'ignore_all_files_in_gitignore': False,
            'initial_prompt': 'Test project for integration testing'
        }
        
        config_path = os.path.join(serena_dir, "project.yml")
        with open(config_path, "w") as f:
            yaml.dump(project_config, f)

    def teardown_method(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_full_project_workflow(self):
        """Test a complete project workflow."""
        # Load the project
        with patch('serena.project.ProjectConfig.load') as mock_load:
            mock_config = Mock()
            mock_config.project_name = 'integration_test_project'
            mock_config.languages = [Language.PYTHON]
            mock_config.encoding = 'utf-8'
            mock_config.ignored_paths = ['*.log', '__pycache__/']
            mock_config.ignore_all_files_in_gitignore = False
            mock_config.initial_prompt = 'Test project for integration testing'
            mock_config.rel_path_to_project_yml.return_value = '.serena/project.yml'
            mock_config.to_yaml_dict.return_value = project_config
            
            mock_load.return_value = mock_config
            
            project = Project.load(self.project_root)
            
            # Test basic properties
            assert project.project_name == 'integration_test_project'
            assert project.project_root == self.project_root
            
            # Create some source files
            src_dir = os.path.join(self.project_root, "src")
            os.makedirs(src_dir)
            
            main_file = os.path.join(src_dir, "main.py")
            with open(main_file, "w") as f:
                f.write("print('Hello, World!')")
            
            utils_file = os.path.join(src_dir, "utils.py")
            with open(utils_file, "w") as f:
                f.write("def helper():\n    return True")
            
            # Test path validation
            assert project.is_path_in_project("src/main.py")
            assert project.relative_path_exists("src/main.py")
            project.validate_relative_path("src/main.py")
            
            # Test ignoring non-source files
            log_file = os.path.join(self.project_root, "debug.log")
            with open(log_file, "w") as f:
                f.write("log message")
            
            # Test file reading
            content = project.read_file("src/main.py")
            assert "print('Hello, World!')" in content
            
            # Test activation message
            message = project.get_activation_message()
            assert "integration_test_project" in message
            assert "Test project for integration testing" in message