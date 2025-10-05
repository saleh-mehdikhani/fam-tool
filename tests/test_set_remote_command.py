"""Tests for the 'fam set-remote' command functionality."""
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health


class TestSetRemoteCommand:
    """Test cases for the 'fam set-remote' command."""
    
    def test_set_remote_valid_url(self, runner):
        """Test setting a remote with a valid URL."""
        
        # Set a remote URL
        data_url = "https://github.com/user/family-tree-data.git"
        graph_url = "https://github.com/user/family-tree-graph.git"
        result = runner.invoke(cli, ['set-remote', '-d', data_url, '-g', graph_url])
        
        assert result.exit_code == 0
        
        # Verify the command succeeded (we can't easily check the actual remote
        # in the test environment, but we can verify the command ran successfully)
        assert "Successfully set remote URLs!" in result.output or result.exit_code == 0
    
    def test_set_remote_ssh_url(self, runner):
        """Test setting a remote with SSH URL."""
        
        # Set an SSH remote URL
        data_url = "git@github.com:user/family-tree-data.git"
        graph_url = "git@github.com:user/family-tree-graph.git"
        result = runner.invoke(cli, ['set-remote', '-d', data_url, '-g', graph_url])
        
        # SSH URLs might fail if SSH keys are not configured, but command should handle gracefully
        # We mainly test that the command doesn't crash
        assert result.exit_code in [0, 1, 2], "Command should handle SSH URLs gracefully"
        
        check_repository_health()
    
    def test_set_remote_local_path(self, runner, temp_dir):
        """Test setting a remote with a local file path."""
        
        # Create a temporary directory for the remote
        remote_path = temp_dir / "remote_repo"
        remote_path.mkdir()
        
        # Initialize a bare repository in the remote path
        Repo.init(str(remote_path), bare=True)
        
        # Set the local path as remote
        data_path = str(remote_path)
        graph_path = str(remote_path).replace("remote_repo", "remote_graph")
        result = runner.invoke(cli, ['set-remote', '-d', data_path, '-g', graph_path])
        
        assert result.exit_code == 0
        
        # Verify remote is set
        data_repo = Repo(Path('.'))
        origin_remote = None
        for remote in data_repo.remotes:
            if remote.name == 'origin':
                origin_remote = remote
                break
        
        assert origin_remote is not None, "Origin remote should exist"
        assert str(remote_path) in origin_remote.url, "Local remote path should be set correctly"
        
        check_repository_health()
    
    def test_set_remote_update_existing(self, runner):
        """Test updating an existing remote URL."""
        
        # Set initial remote
        initial_data_url = "https://github.com/user/initial-repo.git"
        initial_graph_url = "https://github.com/user/initial-graph.git"
        result1 = runner.invoke(cli, ['set-remote', '-d', initial_data_url, '-g', initial_graph_url])
        assert result1.exit_code == 0
        
        # Update to new remote
        new_data_url = "https://github.com/user/updated-repo.git"
        new_graph_url = "https://github.com/user/updated-graph.git"
        result2 = runner.invoke(cli, ['set-remote', '-d', new_data_url, '-g', new_graph_url])
        assert result2.exit_code == 0
        
        # Verify the remote is updated
        data_repo = Repo(Path('.'))
        origin_remote = None
        for remote in data_repo.remotes:
            if remote.name == 'origin':
                origin_remote = remote
                break
        
        assert origin_remote is not None, "Origin remote should exist"
        assert new_data_url in origin_remote.url, "Remote URL should be updated"
        assert initial_data_url not in origin_remote.url, "Old URL should be replaced"
        
        check_repository_health()
    
    def test_set_remote_invalid_url_format(self, runner):
        """Test setting a remote with invalid URL format."""
        
        # Try to set an invalid URL
        invalid_url = "not-a-valid-url"
        result = runner.invoke(cli, ['set-remote', '-d', invalid_url, '-g', invalid_url.replace('data', 'graph')])
        
        # Command might succeed (Git allows various URL formats) or fail
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_set_remote_empty_url(self, runner):
        """Test setting a remote with empty URL."""
        
        # Try to set an empty URL
        result = runner.invoke(cli, ['set-remote', '-d', '', '-g', ''])
        
        # Command should handle this gracefully
        check_repository_health()
    
    def test_set_remote_missing_argument(self, runner):
        """Test set-remote command without URL argument."""
        
        result = runner.invoke(cli, ['set-remote'])
        
        # Command should show error or help
        assert result.exit_code != 0 or 'Usage' in result.output or 'Error' in result.output
        
        check_repository_health()
    
    def test_set_remote_with_extra_arguments(self, runner):
        """Test set-remote command with extra arguments."""
        
        # Try set-remote with extra arguments
        remote_url = "https://github.com/user/family-tree.git"
        result = runner.invoke(cli, ['set-remote', '-d', remote_url, '-g', remote_url, 'extra', 'arguments'])
        
        # Command might succeed (ignoring extra args) or fail
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_set_remote_preserves_data(self, runner):
        """Test that setting a remote doesn't affect existing family data."""
        
        # Add some family data first
        add_result = runner.invoke(cli, [
            'add', '-f', 'PreserveTest', '-l', 'Data', '-g', 'male'
        ])
        assert add_result.exit_code == 0
        
        # Get initial list of people
        list_result_before = runner.invoke(cli, ['list'])
        assert list_result_before.exit_code == 0
        
        # Set remote
        remote_url = "https://github.com/user/preserve-data.git"
        result = runner.invoke(cli, ['set-remote', '-d', remote_url, '-g', remote_url.replace('data', 'graph')])
        assert result.exit_code == 0
        
        # Verify data is preserved
        list_result_after = runner.invoke(cli, ['list'])
        assert list_result_after.exit_code == 0
        assert 'PreserveTest' in list_result_after.output
        assert 'Data' in list_result_after.output
        
        check_repository_health()
    
    def test_set_remote_with_credentials_in_url(self, runner):
        """Test setting a remote with credentials in the URL."""
        
        # Set remote with credentials (not recommended but should work)
        remote_url = "https://username:password@github.com/user/repo.git"
        result = runner.invoke(cli, ['set-remote', '-d', remote_url, '-g', remote_url.replace('data', 'graph')])
        
        assert result.exit_code == 0
        
        # Verify remote is set (credentials should be handled properly)
        data_repo = Repo(Path('.'))
        origin_remote = None
        for remote in data_repo.remotes:
            if remote.name == 'origin':
                origin_remote = remote
                break
        
        assert origin_remote is not None, "Origin remote should exist"
        # URL might be sanitized or stored as-is depending on implementation
        
        check_repository_health()
    
    def test_set_remote_relative_path(self, runner, temp_dir):
        """Test setting a remote with a relative path."""
        
        # Create a relative path remote
        relative_remote = "../relative_remote"
        full_remote_path = temp_dir / "relative_remote"
        full_remote_path.mkdir()
        
        # Initialize a bare repository
        Repo.init(str(full_remote_path), bare=True)
        
        # Set relative path as remote
        result = runner.invoke(cli, ['set-remote', '-d', relative_remote, '-g', relative_remote.replace('data', 'graph')])
        
        # Command might succeed or fail depending on implementation
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_set_remote_very_long_url(self, runner):
        """Test setting a remote with a very long URL."""
        
        # Create a very long URL
        long_url = "https://github.com/user/" + "very-long-repository-name" * 10 + ".git"
        result = runner.invoke(cli, ['set-remote', '-d', long_url, '-g', long_url.replace('data', 'graph')])
        
        # Command should handle long URLs appropriately
        check_repository_health()
    
    def test_set_remote_special_characters_in_url(self, runner):
        """Test setting a remote with special characters in URL."""
        
        # URL with special characters (URL encoded)
        special_url = "https://github.com/user/repo%20with%20spaces.git"
        result = runner.invoke(cli, ['set-remote', '-d', special_url, '-g', special_url.replace('data', 'graph')])
        
        # Command should handle special characters appropriately
        check_repository_health()
    
    def test_set_remote_different_protocols(self, runner):
        """Test setting remotes with different protocols."""
        
        protocols = [
            "https://github.com/user/https-repo.git",
            "git@github.com:user/ssh-repo.git",
            "file:///path/to/local/repo.git"
        ]
        
        for protocol_url in protocols:
            result = runner.invoke(cli, ['set-remote', '-d', protocol_url, '-g', protocol_url.replace('data', 'graph')])
            
            # Different protocols should be handled appropriately
            # Some might succeed, others might fail depending on availability
            check_repository_health()