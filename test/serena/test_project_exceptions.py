"""Exception handling tests for the Project class in src/serena/project.py"""

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


class TestProjectExceptions:
    """Test cases specifically for exception handling in Project class."""

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

    def test_load_nonexistent_project_raises_file_not_found(self):
        """Test that loading a nonexistent project raises FileNotFoundError."""
        nonexistent_path = "/path/that/does/not/exist"
        
        with pytest.raises(FileNotFoundError, match="Project root not found"):
            Project.load(nonexistent_path)

    def test_load_with_autogenerate_false_raises_file_not_found(self):
        """Test that loading with autogenerate=False raises FileNotFoundError for missing config."""
        # Create project root but no config file
        serena_dir = os.path.join(self.project_root, ".serena")
        os.makedirs(serena_dir)
        
        with patch('serena.project.ProjectConfig.load') as mock_load:
            mock_load.side_effect = FileNotFoundError("Config file not found")
            
            with pytest.raises(FileNotFoundError):
                Project.load(self.project_root, autogenerate=False)

    def test_is_ignored_relative_path_nonexistent_file(self):
        """Test that checking a nonexistent file raises FileNotFoundError."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="File .* not found"):
            project._is_ignored_relative_path("nonexistent.txt")

    def test_is_ignored_relative_path_nonexistent_directory(self):
        """Test that checking a nonexistent directory raises FileNotFoundError."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="File .* not found"):
            project._is_ignored_relative_path("nonexistent_dir/file.txt")

    def test_validate_relative_path_outside_project(self):
        """Test validation fails for path outside project."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(ValueError, match="points to path outside of the repository root"):
            project.validate_relative_path("../outside.txt")

    def test_validate_relative_path_outside_project_absolute(self):
        """Test validation fails for absolute path outside project."""
        project = Project(self.project_root, self.project_config)
        
        outside_path = "/some/other/directory/file.txt"
        
        with pytest.raises(ValueError, match="points to path outside of the repository root"):
            project.validate_relative_path(outside_path)

    @patch.object(Project, 'is_ignored_path')
    def test_validate_relative_path_ignored_path_raises(self, mock_is_ignored):
        """Test validation fails for ignored path when required."""
        mock_is_ignored.return_value = True
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(ValueError, match="is ignored; cannot access for safety reasons"):
            project.validate_relative_path("test.txt", require_not_ignored=True)

    @patch.object(Project, 'is_ignored_path')
    def test_validate_relative_path_ignored_path_not_required(self, mock_is_ignored):
        """Test validation succeeds for ignored path when not required."""
        mock_is_ignored.return_value = True
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        # Should not raise any exception when require_not_ignored=False
        project.validate_relative_path("test.txt", require_not_ignored=False)

    def test_gather_source_files_nonexistent_path(self):
        """Test gathering source files from nonexistent path raises FileNotFoundError."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="Relative path .* not found"):
            project.gather_source_files("nonexistent")

    def test_gather_source_files_nonexistent_file(self):
        """Test gathering source files from nonexistent file raises FileNotFoundError."""
        project = Project(self.project_root, self.project_config)
        
        with pytest.raises(FileNotFoundError, match="Relative path .* not found"):
            project.gather_source_files("nonexistent.py")

    @patch('serena.project.os.walk')
    @patch.object(Project, 'is_ignored_path')
    def test_gather_source_files_file_permission_error(self, mock_is_ignored, mock_walk):
        """Test gathering source files handles permission errors gracefully."""
        project = Project(self.project_root, self.project_config)
        mock_is_ignored.return_value = False
        
        # Mock os.walk to raise PermissionError on a directory
        def mock_walk_side_effect(path, followlinks=True):
            if "restricted" in path:
                raise PermissionError(f"Permission denied: {path}")
            return [(self.project_root, [], ["allowed.py"])]
        
        mock_walk.side_effect = mock_walk_side_effect
        
        # Should not raise PermissionError, but log and continue
        with patch('serena.project.log') as mock_log:
            result = project.gather_source_files()
            
            # Should have logged a warning about the permission error
            mock_log.warning.assert_called()

    @patch.object(Project, 'gather_source_files')
    @patch('serena.project.search_files')
    def test_search_source_files_for_pattern_gather_failure(self, mock_search, mock_gather):
        """Test search_source_files_for_pattern handles gather_source_files failure."""
        project = Project(self.project_root, self.project_config)
        mock_gather.side_effect = FileNotFoundError("Directory not found")
        
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            project.search_source_files_for_pattern("test_pattern")

    @patch.object(Project, 'read_file')
    def test_retrieve_content_around_line_file_not_found(self, mock_read_file):
        """Test retrieve_content_around_line handles file not found."""
        project = Project(self.project_root, self.project_config)
        mock_read_file.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            project.retrieve_content_around_line("nonexistent.py", line=10)

    def test_read_file_nonexistent_file(self):
        """Test read_file raises FileNotFoundError for nonexistent file."""
        project = Project(self.project_root, self.project_config)
        
        with patch('serena.project.FileUtils.read_file') as mock_read:
            mock_read.side_effect = FileNotFoundError("File not found")
            
            with pytest.raises(FileNotFoundError, match="File not found"):
                project.read_file("nonexistent.py")

    @patch('serena.project.save_yaml')
    @patch('serena.project.ProjectConfig.load_commented_map')
    def test_save_config_commented_map_load_failure(self, mock_load_commented, mock_save):
        """Test save_config handles failure to load commented map."""
        project = Project(self.project_root, self.project_config)
        mock_load_commented.side_effect = FileNotFoundError("Config file not found")
        
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            project.save_config()

    @patch('serena.project.save_yaml')
    @patch('serena.project.ProjectConfig.load_commented_map')
    def test_save_config_save_failure(self, mock_load_commented, mock_save):
        """Test save_config handles save failure."""
        project = Project(self.project_root, self.project_config)
        mock_load_commented.return_value = {}
        mock_save.side_effect = OSError("Permission denied")
        
        with pytest.raises(OSError, match="Permission denied"):
            project.save_config()

    @patch('serena.project.GitignoreParser')
    def test_initialization_gitignore_parser_failure(self, mock_gitignore_parser):
        """Test project initialization handles GitignoreParser failure gracefully."""
        self.project_config.ignore_all_files_in_gitignore = True
        
        mock_gitignore_parser.side_effect = Exception("Gitignore parsing failed")
        
        # Should still create project successfully even if gitignore parsing fails
        project = Project(self.project_root, self.project_config)
        
        assert project.project_root == self.project_root
        assert project.project_config == self.project_config

    def test_create_language_server_manager_timeout(self):
        """Test create_language_server_manager handles timeout scenarios."""
        project = Project(self.project_root, self.project_config)
        
        with patch('serena.project.LanguageServerFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_factory_class.return_value = mock_factory
            
            with patch('serena.project.LanguageServerManager') as mock_manager_class:
                mock_manager_class.from_languages.side_effect = Exception("Language server startup timeout")
                
                with pytest.raises(Exception, match="Language server startup timeout"):
                    project.create_language_server_manager()

    def test_add_language_no_language_server_manager(self):
        """Test add_language when no language server manager is active."""
        project = Project(self.project_root, self.project_config)
        
        # Mock languages list
        self.project_config.languages = [Language.PYTHON]
        
        # Should not raise exception, just log a message
        with patch('serena.project.log') as mock_log:
            project.add_language(Language.JAVASCRIPT)
            
            # Should have logged info message about inactive LS manager
            mock_log.info.assert_called_with("Language server manager is not active; skipping language server startup for the new language.")

    def test_remove_language_no_language_server_manager(self):
        """Test remove_language when no language server manager is active."""
        project = Project(self.project_root, self.project_config)
        
        # Mock languages list
        self.project_config.languages = [Language.PYTHON, Language.JAVASCRIPT]
        
        with patch.object(project, 'save_config') as mock_save:
            project.remove_language(Language.JAVASCRIPT)
            
            # Should have saved config
            mock_save.assert_called_once()

    def test_path_validation_edge_cases(self):
        """Test edge cases in path validation."""
        project = Project(self.project_root, self.project_config)
        
        # Test empty path
        assert project.is_path_in_project("") is True
        
        # Test current directory
        assert project.is_path_in_project(".") is True
        
        # Test path with .. that goes outside project
        with patch('serena.project.Path.is_absolute') as mock_is_abs:
            mock_is_abs.return_value = False
            
            # Mock the resolution to go outside project
            with patch('serena.project.Path.resolve') as mock_resolve:
                mock_resolve.return_value = Path("/outside/project")
                
                # Create a path that would resolve outside
                outside_path = Path("../outside")
                
                # This should be False (not in project)
                assert project.is_path_in_project(outside_path) is False

    def test_memory_manager_initialization_failure(self):
        """Test project initialization handles memory manager creation failure."""
        with patch('serena.project.MemoriesManager') as mock_memories:
            mock_memories.side_effect = Exception("Memory manager creation failed")
            
            # Should still create project successfully even if memory manager fails
            project = Project(self.project_root, self.project_config)
            
            assert project.project_root == self.project_root
            assert project.project_config == self.project_config

    def test_path_operations_with_symlinks(self):
        """Test path operations handle symlinks appropriately."""
        project = Project(self.project_root, self.project_config)
        
        # Create a test file
        test_file = os.path.join(self.project_root, "test.txt")
        with open(test_file, "w") as f:
            f.write("content")
        
        # Create a symlink inside the project (if supported)
        try:
            symlink_path = os.path.join(self.project_root, "symlink.txt")
            if not os.path.exists(symlink_path):
                os.symlink(test_file, symlink_path)
            
            # Test that symlinks inside project are handled correctly
            assert project.is_path_in_project("symlink.txt") is True
            assert project.relative_path_exists("symlink.txt") is True
            
        except (OSError, NotImplementedError):
            # Skip symlink tests if not supported on this platform
            pytest.skip("Symlinks not supported on this platform")

    def test_gitignore_path_creation_permission_error(self):
        """Test gitignore creation handles permission errors."""
        # Create a read-only .serena directory to cause permission error
        serena_dir = os.path.join(self.project_root, ".serena")
        os.makedirs(serena_dir, mode=0o444)
        
        try:
            with patch('serena.project.log') as mock_log:
                # Should handle permission error gracefully
                project = Project(self.project_root, self.project_config)
                
                # Should have logged an error or warning about the permission issue
                mock_log.assert_called()
                
        finally:
            # Restore permissions for cleanup
            os.chmod(serena_dir, 0o755)

    def test_concurrent_access_thread_safety(self):
        """Test that project operations are thread-safe."""
        import threading
        import time
        
        project = Project(self.project_root, self.project_config)
        
        # Create some test files
        for i in range(5):
            test_file = os.path.join(self.project_root, f"test_{i}.py")
            with open(test_file, "w") as f:
                f.write(f"print('test {i}')")
        
        results = []
        errors = []
        
        def access_project_files():
            try:
                for i in range(10):
                    file_path = f"test_{i % 5}.py"
                    if project.relative_path_exists(file_path):
                        content = project.read_file(file_path)
                        results.append(content)
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads accessing the project concurrently
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_project_files)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no race conditions occurred
        assert len(errors) == 0, f"Errors occurred during concurrent access: {errors}"
        assert len(results) > 0, "No results were collected"