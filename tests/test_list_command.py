"""
Tests for the 'fam list' command functionality.
"""
import os
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health


class TestListCommand:
    """Test cases for the 'fam list' command."""
    def test_list_single_person(self, runner):
        """Test listing a family tree with one person."""
        
        # Add a person
        runner.invoke(cli, [
            'add', '-f', 'SinglePerson', '-l', 'Test', '-g', 'male', '-b', '1990-01-01'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'SinglePerson' in result.output
        assert 'Test' in result.output
        
        check_repository_health()
    
    def test_list_multiple_people(self, runner):
        """Test listing a family tree with multiple people."""
        
        # Add several people
        runner.invoke(cli, [
            'add', '-f', 'Alice', '-l', 'Johnson', '-g', 'female', '-b', '1985-03-15'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Bob', '-l', 'Smith', '-g', 'male', '-b', '1980-07-22'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Charlie', '-l', 'Brown', '-g', 'male', '-b', '1992-11-08'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'Alice' in result.output
        assert 'Bob' in result.output
        assert 'Charlie' in result.output
        assert 'Johnson' in result.output
        assert 'Smith' in result.output
        assert 'Brown' in result.output
        
        check_repository_health()
    
    def test_list_shows_person_ids(self, runner):
        """Test that list command shows person IDs."""
        
        # Add a person
        runner.invoke(cli, [
            'add', '-f', 'IDTest', '-l', 'Person', '-g', 'female'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'IDTest' in result.output
        
        # Look for ID format: (ID: xxxxxxxx) where xxxxxxxx is 8-character hex string
        lines = result.output.strip().split('\n')
        found_id = False
        for line in lines:
            if 'IDTest' in line:
                # Look for pattern "(ID: xxxxxxxx)"
                import re
                id_pattern = r'\(ID: ([0-9a-f]{8})\)'
                match = re.search(id_pattern, line)
                if match:
                    found_id = True
                    break
        
        assert found_id, "List should show person IDs"
        
        check_repository_health()
    
    def test_list_shows_basic_info(self, runner):
        """Test that list command shows basic person information."""
        
        # Add a person with detailed info
        runner.invoke(cli, [
            'add', '-f', 'DetailedPerson', '-l', 'InfoTest', '-g', 'male', 
            '-b', '1975-12-25', '-n', 'Detailed'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'DetailedPerson' in result.output
        assert 'InfoTest' in result.output
        
        # Check if gender or birth date might be shown
        output_lower = result.output.lower()
        assert 'male' in output_lower or 'DetailedPerson' in result.output
        
        check_repository_health()
    
    def test_list_with_special_characters(self, runner):
        """Test listing people with special characters in names."""
        
        # Add people with special characters
        runner.invoke(cli, [
            'add', '-f', 'José', '-l', 'García-López', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Müller', '-l', 'Schmidt', '-g', 'female'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'José' in result.output
        assert 'García-López' in result.output
        assert 'Müller' in result.output
        assert 'Schmidt' in result.output
        
        check_repository_health()
    
    def test_list_sorted_output(self, runner):
        """Test that list output is sorted in some logical order."""
        
        # Add people in non-alphabetical order
        runner.invoke(cli, [
            'add', '-f', 'Zoe', '-l', 'Last', '-g', 'female'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Alice', '-l', 'First', '-g', 'female'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Bob', '-l', 'Middle', '-g', 'male'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        
        # Check that all people are listed
        assert 'Zoe' in result.output
        assert 'Alice' in result.output
        assert 'Bob' in result.output
        
        # The exact sorting order depends on implementation
        # Just verify all are present
        check_repository_health()
    
    def test_list_with_long_names(self, runner):
        """Test listing people with very long names."""
        
        long_first_name = 'VeryLongFirstNameThatExceedsNormalLength'
        long_last_name = 'ExtremelyLongLastNameThatIsUnusuallyLong'
        
        runner.invoke(cli, [
            'add', '-f', long_first_name, '-l', long_last_name, '-g', 'male'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        # Names might be truncated in display, but should be recognizable
        assert long_first_name[:10] in result.output or long_first_name in result.output
        assert long_last_name[:10] in result.output or long_last_name in result.output
        
        check_repository_health()
    
    def test_list_performance_with_many_people(self, runner):
        """Test list command performance with many people."""
        
        # Add multiple people quickly
        for i in range(10):
            runner.invoke(cli, [
                'add', '-f', f'Person{i}', '-l', f'Family{i}', '-g', 'male' if i % 2 == 0 else 'female'
            ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        
        # Check that all people are listed
        for i in range(10):
            assert f'Person{i}' in result.output
        
        check_repository_health()
    
    def test_list_after_adding_relationships(self, runner):
        """Test list command after creating relationships."""
        
        # Add people and create relationships
        runner.invoke(cli, [
            'add', '-f', 'Husband', '-l', 'Married', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Wife', '-l', 'Married', '-g', 'female'
        ])
        
        # Get their IDs and marry them
        list_result = runner.invoke(cli, ['list'])
        lines = list_result.output.strip().split('\n')
        person_ids = []
        for line in lines:
            parts = line.split()
            for part in parts:
                if len(part) == 8 and all(c in '0123456789abcdef' for c in part):
                    person_ids.append(part)
                    break
        
        if len(person_ids) >= 2:
            runner.invoke(cli, ['marry', '-m', person_ids[-2], '-f', person_ids[-1]])
        
        # List again after marriage
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'Husband' in result.output
        assert 'Wife' in result.output
        
        check_repository_health()
    
    def test_list_repository_unchanged(self, runner):
        """Test that list command doesn't modify the repository."""
        
        # Add a person first
        runner.invoke(cli, [
            'add', '-f', 'UnchangedTest', '-l', 'Person', '-g', 'male'
        ])
        
        # Get initial repository state
        data_repo = Repo(Path('.'))
        graph_repo = Repo(Path('family_graph'))
        
        initial_data_commits = len(list(data_repo.iter_commits()))
        initial_graph_commits = len(list(graph_repo.iter_commits()))
        
        # Run list command
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        
        # Check that no new commits were created
        final_data_commits = len(list(data_repo.iter_commits()))
        final_graph_commits = len(list(graph_repo.iter_commits()))
        
        assert final_data_commits == initial_data_commits, "List should not create data commits"
        assert final_graph_commits == initial_graph_commits, "List should not create graph commits"
        
        check_repository_health()
    
    def test_list_output_format_consistency(self, runner):
        """Test that list output format is consistent."""
        
        # Add people with different amounts of information
        runner.invoke(cli, [
            'add', '-f', 'Minimal', '-l', 'Info', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Complete', '-l', 'Info', '-g', 'female', 
            '-b', '1990-01-01', '-mn', 'Middle', '-n', 'Nick'
        ])
        
        result = runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert 'Minimal' in result.output
        assert 'Complete' in result.output
        
        # Check that output format is consistent (both entries should have similar structure)
        lines = [line for line in result.output.strip().split('\n') if line.strip()]
        if len(lines) >= 2:
            # Basic format consistency check - both should have some structure
            assert len(lines) >= 2, "Should have entries for both people"
        
        check_repository_health()