"""
Tests for the 'fam find' command functionality.
"""
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health


class TestFindCommand:
    """Test cases for the 'fam find' command."""
    
    def test_find_by_first_name(self, runner):
        """Test finding people by first name."""
        
        # Add people with different first names
        runner.invoke(cli, [
            'add', '-f', 'FindableJohn', '-l', 'Smith', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Jane', '-l', 'Doe', '-g', 'female'
        ])
        
        result = runner.invoke(cli, ['find', 'FindableJohn'])
        
        assert result.exit_code == 0
        assert 'FindableJohn' in result.output
        assert 'Smith' in result.output
        # Should not find Jane
        assert 'Jane' not in result.output or 'Doe' not in result.output
        
        check_repository_health()
    
    def test_find_by_last_name(self, runner):
        """Test finding people by last name."""
        
        # Add people with different last names
        runner.invoke(cli, [
            'add', '-f', 'Alice', '-l', 'FindableJohnson', '-g', 'female'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Bob', '-l', 'Williams', '-g', 'male'
        ])
        
        result = runner.invoke(cli, ['find', 'FindableJohnson'])
        
        assert result.exit_code == 0
        assert 'Alice' in result.output
        assert 'FindableJohnson' in result.output
        # Should not find Bob Williams
        assert 'Williams' not in result.output or 'Bob' not in result.output
        
        check_repository_health()
    
    def test_find_by_name(self, runner):
        """Test finding people by name."""
        
        # Add people with different names
        runner.invoke(cli, [
            'add', '-f', 'MaleTest', '-l', 'Person', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'FemaleTest', '-l', 'Person', '-g', 'female'
        ])
        
        result = runner.invoke(cli, ['find', 'MaleTest'])
        
        assert result.exit_code == 0
        assert 'MaleTest' in result.output
        # Should not find female person (or should be clearly separated)
        
        check_repository_health()
    
    
    def test_find_by_name_multiple_matches(self, runner):
        """Test finding people using name search with multiple matches."""
        
        # Add people with overlapping names
        runner.invoke(cli, [
            'add', '-f', 'MultiTest', '-l', 'Criteria', '-g', 'male', '-b', '1980-05-15'
        ])
        runner.invoke(cli, [
            'add', '-f', 'MultiTest', '-l', 'Different', '-g', 'female', '-b', '1980-05-15'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Other', '-l', 'Criteria', '-g', 'male', '-b', '1990-01-01'
        ])
        
        # Find by first name
        result = runner.invoke(cli, ['find', 'MultiTest'])
        
        assert result.exit_code == 0
        assert 'MultiTest' in result.output
        # Should find both MultiTest people
        
        check_repository_health()
    
    def test_find_partial_name_match(self, runner):
        """Test finding people with partial name matches."""
        
        # Add people with names that can be partially matched
        runner.invoke(cli, [
            'add', '-f', 'UnchangedFind', '-l', 'Test', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Different', '-l', 'Name', '-g', 'female'
        ])
        
        # Search for partial match
        result = runner.invoke(cli, ['find', 'Unchanged'])
        
        assert result.exit_code == 0
        assert 'UnchangedFind' in result.output
        # Should not find the other person
        assert 'Different' not in result.output or 'Name' not in result.output
        
        check_repository_health()
    
    def test_find_case_insensitive(self, runner):
        """Test that find is case insensitive."""
        
        # Add person with mixed case name
        runner.invoke(cli, [
            'add', '-f', 'CaseTest', '-l', 'Person', '-g', 'male'
        ])
        
        # Search with different case
        result = runner.invoke(cli, ['find', 'casetest'])
        
        assert result.exit_code == 0
        assert 'CaseTest' in result.output
        
        check_repository_health()
    
    def test_find_with_special_characters(self, runner):
        """Test finding people with special characters in names."""
        
        # Add person with special characters
        runner.invoke(cli, [
            'add', '-f', 'José', '-l', 'García-López', '-g', 'male'
        ])
        
        # Search for the person
        result = runner.invoke(cli, ['find', 'José'])
        
        assert result.exit_code == 0
        assert 'José' in result.output
        
        check_repository_health()
    
    def test_find_multiple_results(self, runner):
        """Test find command with multiple matching results."""
        
        # Add multiple people with similar names
        runner.invoke(cli, [
            'add', '-f', 'John', '-l', 'CommonName', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Jane', '-l', 'CommonName', '-g', 'female'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Bob', '-l', 'CommonName', '-g', 'male'
        ])
        
        # Search for common last name
        result = runner.invoke(cli, ['find', 'CommonName'])
        
        assert result.exit_code == 0
        # Should find all three people
        assert 'John' in result.output
        assert 'Jane' in result.output
        assert 'Bob' in result.output
        assert 'CommonName' in result.output
        
        check_repository_health()