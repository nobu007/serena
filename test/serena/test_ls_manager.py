"""Comprehensive tests for LanguageServerManager in src/serena/ls_manager.py"""

import threading
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

from serena.ls_manager import LanguageServerManager, LanguageServerFactory
from serena.config.project_config import Language
from serena.util.exception import ProjectNotFoundError


class MockLanguageServer:
    """Mock language server for testing."""
    
    def __init__(self, language: Language, root_path: str = "/test/root"):
        self.language = language
        self.repository_root_path = root_path
        self._is_running = True
        self._is_ignored_path_result = False
        
    def start(self):
        """Mock start method."""
        self._is_running = True
        
    def stop(self):
        """Mock stop method."""
        self._is_running = False
        
    def is_running(self) -> bool:
        """Mock is_running method."""
        return self._is_running
        
    def is_ignored_path(self, relative_path: str, ignore_unsupported_files: bool = False) -> bool:
        """Mock is_ignored_path method."""
        return self._is_ignored_path_result
        
    def save_cache(self):
        """Mock save_cache method."""
        pass


class MockLanguageServerFactory:
    """Mock language server factory for testing."""
    
    def __init__(self, root_path: str = "/test/root"):
        self.root_path = root_path
        self.created_servers = {}
        
    def create_language_server(self, language: Language) -> MockLanguageServer:
        """Create a mock language server."""
        server = MockLanguageServer(language, self.root_path)
        self.created_servers[language] = server
        return server


class TestLanguageServerManager:
    """Test cases for LanguageServerManager."""

    def test_init_basic(self):
        """Test basic LanguageServerManager initialization."""
        # Create mock language servers
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        language_servers = {
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        }
        
        manager = LanguageServerManager(language_servers)
        
        assert manager._language_servers == language_servers
        assert manager._default_language_server == python_server
        assert manager._root_path == "/test/root"
        assert manager._language_server_factory is None

    def test_init_with_factory(self):
        """Test LanguageServerManager initialization with factory."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        factory = MockLanguageServerFactory()
        
        language_servers = {Language.PYTHON: python_server}
        
        manager = LanguageServerManager(language_servers, factory)
        
        assert manager._language_server_factory == factory

    def test_get_root_path(self):
        """Test getting root path."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        manager = LanguageServerManager({Language.PYTHON: python_server})
        
        assert manager.get_root_path() == "/test/root"

    @patch('serena.ls_manager.threading.Thread')
    @patch('serena.ls_manager.LogTime')
    def test_from_languages_success(self, mock_log_time, mock_thread):
        """Test successful creation from languages."""
        factory = MockLanguageServerFactory()
        languages = [Language.PYTHON, Language.JAVASCRIPT]
        
        # Mock thread behavior
        mock_threads = []
        def create_thread(target, args, name):
            mock_thread = Mock()
            mock_threads.append(mock_thread)
            # Execute the target function immediately for testing
            target(*args)
            return mock_thread
        
        mock_thread.side_effect = create_thread
        
        manager = LanguageServerManager.from_languages(languages, factory)
        
        # Verify all threads were created and joined
        assert len(mock_threads) == 2
        for mock_thread in mock_threads:
            mock_thread.join.assert_called_once()
        
        # Verify language servers were created
        assert len(manager._language_servers) == 2
        assert Language.PYTHON in manager._language_servers
        assert Language.JAVASCRIPT in manager._language_servers

    @patch('serena.ls_manager.threading.Thread')
    def test_from_languages_with_failure(self, mock_thread):
        """Test from_languages with server startup failure."""
        factory = Mock(spec=LanguageServerFactory)
        
        def create_language_server(language):
            raise RuntimeError(f"Failed to start {language.value}")
        
        factory.create_language_server.side_effect = create_language_server
        
        # Mock thread that executes immediately
        def create_thread(target, args, name):
            # Execute the target function immediately
            target(*args)
            mock_thread_obj = Mock()
            mock_thread_obj.join = Mock()
            return mock_thread_obj
        
        mock_thread.side_effect = create_thread
        
        languages = [Language.PYTHON, Language.JAVASCRIPT]
        
        with pytest.raises(Exception, match="Failed to start language servers"):
            LanguageServerManager.from_languages(languages, factory)

    @patch('serena.ls_manager.threading.Thread')
    def test_from_languages_partial_failure_cleanup(self, mock_thread):
        """Test cleanup when some language servers fail to start."""
        factory = Mock(spec=LanguageServerFactory)
        
        call_count = 0
        def create_language_server(language):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First server succeeds
                server = MockLanguageServer(language)
                server.start = Mock()
                server.is_running = Mock(return_value=True)
                return server
            else:
                # Second server fails
                raise RuntimeError("Failed to start")
        
        factory.create_language_server.side_effect = create_language_server
        
        # Mock thread that executes immediately
        def create_thread(target, args, name):
            target(*args)
            mock_thread_obj = Mock()
            mock_thread_obj.join = Mock()
            return mock_thread_obj
        
        mock_thread.side_effect = create_thread
        
        languages = [Language.PYTHON, Language.JAVASCRIPT]
        
        with pytest.raises(Exception):
            LanguageServerManager.from_languages(languages, factory)

    def test_get_language_server_single_server(self):
        """Test getting language server when only one server exists."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        manager = LanguageServerManager({Language.PYTHON: python_server})
        
        result = manager.get_language_server("src/main.py")
        
        assert result == python_server

    def test_get_language_server_multiple_servers_none_match(self):
        """Test getting language server when multiple servers exist but none match the path."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        # Both servers return True for is_ignored_path (meaning they ignore the file)
        python_server._is_ignored_path_result = True
        js_server._is_ignored_path_result = True
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        result = manager.get_language_server("unknown.xyz")
        
        # Should return the default server (first one)
        assert result == python_server

    def test_get_language_server_multiple_servers_with_match(self):
        """Test getting language server when multiple servers exist and one matches."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        # JS server doesn't ignore the file, Python server does
        python_server._is_ignored_path_result = True
        js_server._is_ignored_path_result = False
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        result = manager.get_language_server("script.js")
        
        # Should return the JS server that doesn't ignore the file
        assert result == js_server

    def test_ensure_functional_ls_running_server(self):
        """Test _ensure_functional_ls with a running server."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        manager = LanguageServerManager({Language.PYTHON: python_server})
        
        result = manager._ensure_functional_ls(python_server)
        
        assert result == python_server
        # restart_language_server should not be called
        python_server.restart.assert_not_called()

    @patch.object(LanguageServerManager, 'restart_language_server')
    def test_ensure_functional_ls_not_running_server(self, mock_restart):
        """Test _ensure_functional_ls with a non-running server."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        python_server._is_running = False
        restarted_server = MockLanguageServer(Language.PYTHON, "/test/root")
        mock_restart.return_value = restarted_server
        
        manager = LanguageServerManager({Language.PYTHON: python_server})
        
        result = manager._ensure_functional_ls(python_server)
        
        assert result == restarted_server
        mock_restart.assert_called_once_with(Language.PYTHON)

    def test_create_and_start_language_server_with_factory(self):
        """Test _create_and_start_language_server with factory available."""
        factory = MockLanguageServerFactory()
        manager = LanguageServerManager({}, factory)
        
        server = manager._create_and_start_language_server(Language.PYTHON)
        
        assert isinstance(server, MockLanguageServer)
        assert server.language == Language.PYTHON
        assert server._is_running is True
        assert Language.PYTHON in manager._language_servers

    def test_create_and_start_language_server_without_factory(self):
        """Test _create_and_start_language_server without factory."""
        manager = LanguageServerManager({}, None)
        
        with pytest.raises(ValueError, match="No language server factory available"):
            manager._create_and_start_language_server(Language.PYTHON)

    def test_restart_language_server_success(self):
        """Test successful language server restart."""
        original_server = MockLanguageServer(Language.PYTHON, "/test/root")
        factory = MockLanguageServerFactory()
        manager = LanguageServerManager({Language.PYTHON: original_server}, factory)
        
        new_server = manager.restart_language_server(Language.PYTHON)
        
        assert isinstance(new_server, MockLanguageServer)
        assert new_server.language == Language.PYTHON
        assert new_server != original_server
        assert manager._language_servers[Language.PYTHON] == new_server

    def test_restart_language_server_not_found(self):
        """Test restarting language server that doesn't exist."""
        factory = MockLanguageServerFactory()
        manager = LanguageServerManager({}, factory)
        
        with pytest.raises(ValueError, match="No language server for language PYTHON present"):
            manager.restart_language_server(Language.PYTHON)

    def test_add_language_server_success(self):
        """Test successfully adding a new language server."""
        factory = MockLanguageServerFactory()
        manager = LanguageServerManager({}, factory)
        
        server = manager.add_language_server(Language.PYTHON)
        
        assert isinstance(server, MockLanguageServer)
        assert server.language == Language.PYTHON
        assert Language.PYTHON in manager._language_servers

    def test_add_language_server_already_exists(self):
        """Test adding language server that already exists."""
        existing_server = MockLanguageServer(Language.PYTHON, "/test/root")
        factory = MockLanguageServerFactory()
        manager = LanguageServerManager({Language.PYTHON: existing_server}, factory)
        
        with pytest.raises(ValueError, match="Language server for language PYTHON already present"):
            manager.add_language_server(Language.PYTHON)

    def test_remove_language_server_success(self):
        """Test successfully removing a language server."""
        server = MockLanguageServer(Language.PYTHON, "/test/root")
        manager = LanguageServerManager({Language.PYTHON: server})
        
        manager.remove_language_server(Language.PYTHON, save_cache=True)
        
        assert Language.PYTHON not in manager._language_servers
        # server.stop should have been called
        assert server._is_running is False

    def test_remove_language_server_not_found(self):
        """Test removing language server that doesn't exist."""
        manager = LanguageServerManager({})
        
        with pytest.raises(ValueError, match="No language server for language PYTHON present"):
            manager.remove_language_server(Language.PYTHON)

    def test_iter_language_servers(self):
        """Test iterating over language servers."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        servers = list(manager.iter_language_servers())
        
        assert len(servers) == 2
        assert python_server in servers
        assert js_server in servers

    def test_stop_all_save_cache(self):
        """Test stopping all language servers with cache save."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        manager.stop_all(save_cache=True)
        
        assert python_server._is_running is False
        assert js_server._is_running is False

    def test_stop_all_no_cache_save(self):
        """Test stopping all language servers without cache save."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        manager.stop_all(save_cache=False)
        
        assert python_server._is_running is False
        assert js_server._is_running is False

    def test_save_all_caches(self):
        """Test saving caches for all language servers."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        manager.save_all_caches()
        
        # Both servers should still be running
        assert python_server._is_running is True
        assert js_server._is_running is True


class TestLanguageServerFactory:
    """Test cases for LanguageServerFactory (integration tests)."""

    def test_factory_integration(self):
        """Test LanguageServerFactory integration with LanguageServerManager."""
        # This is more of an integration test pattern
        # In real scenarios, you would test with actual language server implementations
        factory = MockLanguageServerFactory("/test/project/root")
        
        # Verify factory can create servers for different languages
        python_server = factory.create_language_server(Language.PYTHON)
        js_server = factory.create_language_server(Language.JAVASCRIPT)
        
        assert python_server.language == Language.PYTHON
        assert js_server.language == Language.JAVASCRIPT
        assert python_server.repository_root_path == "/test/project/root"
        assert js_server.repository_root_path == "/test/project/root"


class TestLanguageServerManagerEdgeCases:
    """Edge case tests for LanguageServerManager."""

    def test_empty_language_servers_dict(self):
        """Test manager with no language servers."""
        with pytest.raises(ValueError, match="language_servers dictionary cannot be empty"):
            LanguageServerManager({})

    def test_server_restart_preserves_factory(self):
        """Test that server restart preserves the factory reference."""
        factory = MockLanguageServerFactory()
        original_server = MockLanguageServer(Language.PYTHON, "/test/root")
        manager = LanguageServerManager({Language.PYTHON: original_server}, factory)
        
        # Restart the server
        new_server = manager.restart_language_server(Language.PYTHON)
        
        # Factory should still be available
        assert manager._language_server_factory == factory
        
        # Should be able to add another server using the same factory
        js_server = manager.add_language_server(Language.JAVASCRIPT)
        assert js_server.language == Language.JAVASCRIPT

    def test_concurrent_server_access(self):
        """Test thread-safe access to language servers."""
        python_server = MockLanguageServer(Language.PYTHON, "/test/root")
        js_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        manager = LanguageServerManager({
            Language.PYTHON: python_server,
            Language.JAVASCRIPT: js_server
        })
        
        results = []
        errors = []
        
        def access_server():
            try:
                server = manager.get_language_server("test.py")
                results.append(server)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads accessing servers concurrently
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=access_server)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred and all got valid servers
        assert len(errors) == 0
        assert len(results) == 10
        assert all(server in [python_server, js_server] for server in results)

    def test_language_server_failure_during_iteration(self):
        """Test behavior when language server fails during iteration."""
        failing_server = MockLanguageServer(Language.PYTHON, "/test/root")
        working_server = MockLanguageServer(Language.JAVASCRIPT, "/test/root")
        
        # Mock failing behavior
        def mock_ensure_functional_ls(ls):
            if ls == failing_server:
                raise RuntimeError("Server failed")
            return ls
        
        manager = LanguageServerManager({
            Language.PYTHON: failing_server,
            Language.JAVASCRIPT: working_server
        })
        
        manager._ensure_functional_ls = mock_ensure_functional_ls
        
        with pytest.raises(RuntimeError, match="Server failed"):
            list(manager.iter_language_servers())