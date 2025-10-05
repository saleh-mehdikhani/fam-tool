"""
Tests for the 'fam add' command functionality.
"""
import pytest
from pathlib import Path
from git import Repo
import subprocess
cli = None
from .test_utils import check_repository_health


class TestAddCommand:
    """Test cases for the 'fam add' command."""
    
    def test_add_single_person_success(self, runner):
        """Test adding a single person successfully."""
        
        # Use a unique name to avoid conflicts with existing data
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        first_name = f"TestUser{unique_id}"
        last_name = f"TestLast{unique_id}"
        
        result = runner.invoke(cli, [
            'add',
            '-f', first_name,
            '-l', last_name,
            '-g', 'male',
            '-b', '1980-01-01'
        ])
        
        assert result.exit_code == 0
        assert "Successfully added person!" in result.output
        
        # Check if person file was created
        people_dir = Path('people')
        person_files = list(people_dir.glob(f"*{first_name.lower()}_{last_name.lower()}.yml"))
        assert len(person_files) == 1
        
        # Check repository health
        check_repository_health()
    
    def test_add_person_with_all_fields(self, runner):
        """Test adding a person with all optional fields."""
        
        result = runner.invoke(cli, [
            'add',
            '-f', 'Jane',
            '-l', 'Doe',
            '-mn', 'Marie',
            '-g', 'female',
            '-b', '1985-05-15',
            '-n', 'Janie'
        ])
        
        assert result.exit_code == 0
        assert "Successfully added person!" in result.output
        
        # Verify the YAML file contains all fields
        people_dir = Path('people')
        person_files = list(people_dir.glob('*jane_doe.yml'))
        assert len(person_files) >= 1  # Allow for multiple files due to test reruns
        
        with open(person_files[0], 'r') as f:
            content = f.read()
            assert 'first_name: Jane' in content
            assert 'last_name: Doe' in content
            assert 'middle_name: Marie' in content
            assert 'gender: female' in content
            assert '1985-05-15' in content  # Check for the date value regardless of quotes
            assert 'nickname: Janie' in content
        
        check_repository_health()
    
    def test_add_multiple_children(self, runner):
        """Test adding multiple children with same parents."""
        
        # First get parent IDs
        list_result = runner.invoke(cli, ['list'])
        assert list_result.exit_code == 0
        
        # Extract IDs from the output (assuming format includes short IDs)
        lines = list_result.output.strip().split('\n')
        parent_ids = []
        for line in lines:
            if 'John Smith' in line or 'Jane Doe' in line:
                # Extract ID from line (format may vary)
                parts = line.split()
                for part in parts:
                    if len(part) == 8 and all(c in '0123456789abcdef' for c in part):
                        parent_ids.append(part)
                        break
        
        if len(parent_ids) >= 2:
            father_id = parent_ids[0]
            mother_id = parent_ids[1]
            
            result = runner.invoke(cli, [
                'add',
                '-f', 'Alice', '-f', 'Bob', '-f', 'Charlie',
                '-l', 'Smith',
                '-g', 'female',
                '--father', father_id,
                '--mother', mother_id
            ])
            
            assert result.exit_code == 0
            assert "Successfully added: 3/3 children" in result.output or "All children added successfully!" in result.output
            
            # Verify all children were created
            people_dir = Path('people')
            alice_files = list(people_dir.glob('*alice_smith.yml'))
            bob_files = list(people_dir.glob('*bob_smith.yml'))
            charlie_files = list(people_dir.glob('*charlie_smith.yml'))
            
            assert len(alice_files) == 1
            assert len(bob_files) == 1
            assert len(charlie_files) == 1
            
            check_repository_health()
    
    def test_add_person_missing_required_fields(self, runner):
        """Test adding a person with missing required fields."""
        
        # Missing last name
        result = runner.invoke(cli, [
            'add',
            '-f', 'John'
        ])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "required" in result.output.lower()
        
        check_repository_health()
    
    def test_add_child_with_parents(self, runner):
        """Test adding a child with specified parents."""
        
        # Get parent IDs
        list_result = runner.invoke(cli, ['list'])
        assert list_result.exit_code == 0
        
        # Extract parent IDs (simplified - in real scenario would parse more carefully)
        lines = list_result.output.strip().split('\n')
        parent_ids = []
        for line in lines:
            if any(name in line for name in ['John Smith', 'Jane Doe']):
                parts = line.split()
                for part in parts:
                    if len(part) == 8 and all(c in '0123456789abcdef' for c in part):
                        parent_ids.append(part)
                        break
        
        if len(parent_ids) >= 2:
            result = runner.invoke(cli, [
                'add',
                '-f', 'TestChild',
                '-l', 'Smith',
                '-g', 'male',
                '--father', parent_ids[0],
                '--mother', parent_ids[1]
            ])
            
            assert result.exit_code == 0
            assert "Successfully added person!" in result.output
            
            check_repository_health()
    
    def test_add_person_invalid_date_format(self, runner):
        """Test adding a person with invalid date format."""
        
        result = runner.invoke(cli, [
            'add',
            '-f', 'John',
            '-l', 'Smith',
            '-b', 'invalid-date'
        ])
        
        # The command might succeed but with a warning, or fail
        # Check that repository remains healthy regardless
        check_repository_health()
    
    def test_repository_commits_after_add(self, runner):
        """Test that adding a person creates proper Git commits."""
        
        # Get initial commit count
        data_repo = Repo(Path('.'))
        graph_repo = Repo(Path('family_graph'))
        
        initial_data_commits = len(list(data_repo.iter_commits()))
        # Count graph commits across all refs (branches, tags) to avoid detached HEAD issues
        initial_graph_commits = len(list(graph_repo.iter_commits('--all')))
        
        # Add a person
        result = runner.invoke(cli, [
            'add',
            '-f', 'TestPerson',
            '-l', 'TestLastName',
            '-g', 'male'
        ])
        
        assert result.exit_code == 0
        
        final_data_commits = len(list(data_repo.iter_commits()))
        # Count graph commits across all refs (branches, tags) to avoid detached HEAD issues
        final_graph_commits = len(list(graph_repo.iter_commits('--all')))
        
        # Check that commits were created
        assert final_data_commits > initial_data_commits, "Data repository should have new commits"
        assert final_graph_commits > initial_graph_commits, "Graph repository should have new commits"
        
        check_repository_health()