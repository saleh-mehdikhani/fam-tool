"""
Tests for the 'fam marry' command functionality.
"""
import os
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health, get_person_ids_from_list, get_person_ids_from_add_output


class TestMarryCommand:
    """Test cases for the 'fam marry' command."""
    
    def test_marry_two_people_success(self, runner):
        """Test marrying two people successfully."""
        
        # Add two people first
        result1 = runner.invoke(cli, [
            'add', '-f', 'Michael', '-l', 'Johnson', '-g', 'male', '-b', '1975-03-10'
        ])
        result2 = runner.invoke(cli, [
            'add', '-f', 'Sarah', '-l', 'Williams', '-g', 'female', '-b', '1978-07-22'
        ])
        
        # Get their IDs from the add command output
        person_ids = []
        person_ids.extend(get_person_ids_from_add_output(result1.output))
        person_ids.extend(get_person_ids_from_add_output(result2.output))
        assert len(person_ids) >= 2
        
        # Marry them
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[0], '-f', person_ids[1]
        ])
        
        assert result.exit_code == 0
        assert "Successfully created marriage event!" in result.output
        
        check_repository_health()

    def test_marry_same_person_twice_error(self, runner):
        """Test that marrying the same person to themselves fails."""
        
        # Add a person
        runner.invoke(cli, [
            'add', '-f', 'TestPerson', '-l', 'TestLast', '-g', 'male'
        ])
        
        person_ids = get_person_ids_from_list(runner)
        assert len(person_ids) >= 1
        
        # Try to marry person to themselves
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[-1], '-f', person_ids[-1]
        ])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "cannot marry" in result.output.lower()
        
        check_repository_health()
    
    def test_marry_nonexistent_person(self, runner):
        """Test marrying with a non-existent person ID."""
        
        # Add one person
        runner.invoke(cli, [
            'add', '-f', 'RealPerson', '-l', 'RealLast', '-g', 'female'
        ])
        
        person_ids = get_person_ids_from_list(runner)
        assert len(person_ids) >= 1
        
        # Try to marry with fake ID
        fake_id = 'ffffffff'
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[-1], '-f', fake_id
        ])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "not found" in result.output.lower()
        
        check_repository_health()
    
    def test_marry_already_married_people(self, runner):
        """Test that marrying the same pair twice fails gracefully."""
        
        # Add two people first
        result1 = runner.invoke(cli, [
            'add', '-f', 'AlreadyMarried1', '-l', 'Test', '-g', 'male'
        ])
        result2 = runner.invoke(cli, [
            'add', '-f', 'AlreadyMarried2', '-l', 'Test', '-g', 'female'
        ])
        
        # Get their IDs from the add command output
        person_ids = []
        person_ids.extend(get_person_ids_from_add_output(result1.output))
        person_ids.extend(get_person_ids_from_add_output(result2.output))
        assert len(person_ids) >= 2
        
        # Marry the two people
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[0], '-f', person_ids[1]
        ])
        assert result.exit_code == 0
        
        # Try to marry the same pair again - should fail
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[0], '-f', person_ids[1]
        ])
        assert result.exit_code == 1
        assert "Marriage already registered" in result.output
        
        check_repository_health()
    
     
    def test_repository_commits_after_marry(self, runner):
        """Test that marrying creates proper Git commits."""
        
        # Add two people first
        result1 = runner.invoke(cli, [
            'add', '-f', 'CommitTest1', '-l', 'Marriage', '-g', 'male'
        ])
        result2 = runner.invoke(cli, [
            'add', '-f', 'CommitTest2', '-l', 'Marriage', '-g', 'female'
        ])
        
        # Get their IDs from the add command output
        person_ids = []
        person_ids.extend(get_person_ids_from_add_output(result1.output))
        person_ids.extend(get_person_ids_from_add_output(result2.output))
        assert len(person_ids) >= 2
        
        # Get initial commit counts
        data_repo = Repo(Path('.'))
        graph_repo = Repo(Path('family_graph'))
        
        initial_data_commits = len(list(data_repo.iter_commits()))
        initial_graph_commits = len(list(graph_repo.iter_commits()))
        
        # Marry them
        result = runner.invoke(cli, [
            'marry', '-m', person_ids[0], '-f', person_ids[1]
        ])
        
        assert result.exit_code == 0
        
        # Check that commits were created
        final_data_commits = len(list(data_repo.iter_commits()))
        final_graph_commits = len(list(graph_repo.iter_commits()))
        
        assert final_data_commits > initial_data_commits, "Data repository should have new commits"
        assert final_graph_commits > initial_graph_commits, "Graph repository should have new commits"
        
        check_repository_health()
    
    def test_marry_missing_arguments(self, runner):
        """Test marry command with missing arguments."""
        
        # Try marry with no arguments
        result = runner.invoke(cli, ['marry'])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "required" in result.output.lower()
        
        # Try marry with only one person
        person_ids = get_person_ids_from_list(runner)
        if person_ids:
            result = runner.invoke(cli, ['marry', person_ids[0]])
            assert result.exit_code != 0
        
        check_repository_health()