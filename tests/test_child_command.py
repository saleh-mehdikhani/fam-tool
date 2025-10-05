"""Tests for the 'fam child' command functionality."""
import os
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health, get_person_ids_from_list


class TestChildCommand:
    """Test cases for the 'fam child' command."""
    
    def test_add_child_with_both_parents(self, runner):
        """Test adding a child with both father and mother specified."""
        
        # Use unique names to avoid ID conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add parents with unique names
        runner.invoke(cli, [
            'add', '-f', f'TestFather{unique_suffix}', '-l', 'TestFamily', '-g', 'male', '-b', '1970-01-01'
        ])
        runner.invoke(cli, [
            'add', '-f', f'TestMother{unique_suffix}', '-l', 'TestFamily', '-g', 'female', '-b', '1972-05-15'
        ])
        
        # Marry the parents using correct syntax
        marry_result = runner.invoke(cli, [
            'marry', '--male', f'TestFather{unique_suffix}', '--female', f'TestMother{unique_suffix}'
        ])
        assert marry_result.exit_code == 0
        
        # Create child person first
        add_child_result = runner.invoke(cli, [
            'add',
            '-f', f'TestChild{unique_suffix}',
            '-l', 'TestFamily',
            '-g', 'male',
            '-b', '2000-03-10'
        ])
        assert add_child_result.exit_code == 0
        
        # Link child to both parents using names
        result = runner.invoke(cli, [
            'child',
            f'TestChild{unique_suffix}',
            '--father', f'TestFather{unique_suffix}',
            '--mother', f'TestMother{unique_suffix}'
        ])
        
        # Note: The command may fail due to missing git filter-repo dependency
        # but the test structure is correct
        if result.exit_code != 0:
            print(f"Child command output: {result.output}")
        
        assert result.exit_code == 0
        
        # Verify child file was created
        people_dir = Path('people')
        child_files = list(people_dir.glob(f'*testchild{unique_suffix.lower()}_testfamily.yml'))
        assert len(child_files) == 1
        
        check_repository_health()
    
    def test_add_child_with_father_only(self, runner):
        """Test adding a child with only father specified."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add father
        runner.invoke(cli, [
            'add', '-f', f'TestFather{unique_suffix}', '-l', 'TestFamily', '-g', 'male'
        ])
        
        # Create child person first
        add_child_result = runner.invoke(cli, [
            'add',
            '-f', f'ChildName{unique_suffix}',
            '-l', 'TestFamily',
            '-g', 'male'
        ])
        assert add_child_result.exit_code == 0
        
        # Try to link child to father only - this should fail since both parents are required
        result = runner.invoke(cli, [
            'child',
            f'ChildName{unique_suffix}',
            '--father', f'TestFather{unique_suffix}'
        ])
        
        # The command should fail because both father and mother are required
        assert result.exit_code != 0
        assert "Missing option" in result.output and "mother" in result.output
        
        check_repository_health()
    
    def test_add_child_with_mother_only(self, runner):
        """Test adding a child with only mother specified."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add mother
        runner.invoke(cli, [
            'add', '-f', f'TestMother{unique_suffix}', '-l', 'TestFamily', '-g', 'female'
        ])
        
        # Create child person first
        add_child_result = runner.invoke(cli, [
            'add',
            '-f', f'ChildName{unique_suffix}',
            '-l', 'TestFamily',
            '-g', 'female'
        ])
        assert add_child_result.exit_code == 0
        
        # Try to link child to mother only - this should fail since both parents are required
        result = runner.invoke(cli, [
            'child',
            f'ChildName{unique_suffix}',
            '--mother', f'TestMother{unique_suffix}'
        ])
        
        # The command should fail because both father and mother are required
        assert result.exit_code != 0
        assert "Missing option" in result.output and "father" in result.output
        
        check_repository_health()
    
    def test_add_multiple_children_same_parents(self, runner):
        """Test adding multiple children with the same parents."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add parents
        runner.invoke(cli, [
            'add', '-f', f'TestDad{unique_suffix}', '-l', 'TestFamily', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', f'TestMom{unique_suffix}', '-l', 'TestFamily', '-g', 'female'
        ])
        
        # Marry the parents first using correct syntax
        marry_result = runner.invoke(cli, [
            'marry', '--male', f'TestDad{unique_suffix}', '--female', f'TestMom{unique_suffix}'
        ])
        assert marry_result.exit_code == 0
        
        # Add first child
        add_result1 = runner.invoke(cli, [
            'add',
            '-f', f'FirstChild{unique_suffix}',
            '-l', 'TestFamily',
            '-g', 'male'
        ])
        assert add_result1.exit_code == 0
        
        # Link first child to parents using names
        result1 = runner.invoke(cli, [
            'child',
            f'FirstChild{unique_suffix}',
            '--father', f'TestDad{unique_suffix}',
            '--mother', f'TestMom{unique_suffix}'
        ])
        assert result1.exit_code == 0
        
        # Add second child
        add_result2 = runner.invoke(cli, [
            'add',
            '-f', f'SecondChild{unique_suffix}',
            '-l', 'TestFamily',
            '-g', 'female'
        ])
        assert add_result2.exit_code == 0
        
        # Link second child to parents using names
        result2 = runner.invoke(cli, [
            'child',
            f'SecondChild{unique_suffix}',
            '--father', f'TestDad{unique_suffix}',
            '--mother', f'TestMom{unique_suffix}'
        ])
        assert result2.exit_code == 0
        
        # Verify both children were created
        people_dir = Path('people')
        first_child_files = list(people_dir.glob(f'*firstchild{unique_suffix.lower()}_testfamily.yml'))
        second_child_files = list(people_dir.glob(f'*secondchild{unique_suffix.lower()}_testfamily.yml'))
        
        assert len(first_child_files) == 1
        assert len(second_child_files) == 1
        
        check_repository_health()
    
    def test_add_child_nonexistent_parent(self, runner):
        """Test adding a child with non-existent parent ID."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add child person first
        runner.invoke(cli, [
            'add', '-f', f'OrphanChild{unique_suffix}', '-l', 'NoParent', '-g', 'male'
        ])
        
        fake_parent_name = f'NonExistentParent{unique_suffix}'
        fake_mother_name = f'NonExistentMother{unique_suffix}'
        
        result = runner.invoke(cli, [
            'child',
            f'OrphanChild{unique_suffix}',
            '--father', fake_parent_name,
            '--mother', fake_mother_name
        ])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "not found" in result.output.lower()
        
        check_repository_health()
    
    def test_add_child_missing_required_fields(self, runner):
        """Test adding a child with missing required fields."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add parents
        runner.invoke(cli, [
            'add', '-f', f'Parent{unique_suffix}', '-l', 'Test', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', f'ParentMom{unique_suffix}', '-l', 'Test', '-g', 'female'
        ])
        
        # Try to add child without specifying child name (missing argument)
        result = runner.invoke(cli, [
            'child',
            '--father', f'Parent{unique_suffix}',
            '--mother', f'ParentMom{unique_suffix}'
        ])
        
        assert result.exit_code != 0
        assert "Error" in result.output or "required" in result.output.lower() or "Missing argument" in result.output
        
        check_repository_health()
    
    def test_add_child_with_birth_date(self, runner):
        """Test adding a child with a specific birth date."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add parents
        runner.invoke(cli, [
            'add', '-f', f'BirthParent{unique_suffix}', '-l', 'WithDate', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', f'BirthMom{unique_suffix}', '-l', 'WithDate', '-g', 'female'
        ])
        
        # Marry the parents first using correct syntax
        marry_result = runner.invoke(cli, [
            'marry', '--male', f'BirthParent{unique_suffix}', '--female', f'BirthMom{unique_suffix}'
        ])
        assert marry_result.exit_code == 0
        
        # Add child person first with birth date
        runner.invoke(cli, [
            'add', '-f', f'DateChild{unique_suffix}', '-l', 'WithDate', '-g', 'male', '-b', '2010-12-25'
        ])
        
        # Link child to parents
        result = runner.invoke(cli, [
            'child',
            f'DateChild{unique_suffix}',
            '--father', f'BirthParent{unique_suffix}',
            '--mother', f'BirthMom{unique_suffix}'
        ])
        
        assert result.exit_code == 0
        
        # Verify birth date in file
        people_dir = Path('people')
        # Find the child file by searching for the unique suffix in the filename
        child_files = list(people_dir.glob(f'*datechild{unique_suffix.lower()}*.yml'))
        assert len(child_files) == 1
        
        with open(child_files[0], 'r') as f:
            content = f.read()
            assert '2010-12-25' in content
        
        check_repository_health()
    

    def test_add_child_invalid_birth_date(self, runner):
        """Test adding a child with invalid birth date format."""
        
        # Add parent
        runner.invoke(cli, [
            'add', '-f', 'Parent', '-l', 'InvalidDate', '-g', 'male'
        ])
        
        person_ids = get_person_ids_from_list(runner)
        assert len(person_ids) >= 1
        
        parent_id = person_ids[-1]
        
        # Try to add child with invalid date
        result = runner.invoke(cli, [
            'child',
            '-f', 'InvalidDateChild',
            '-l', 'InvalidDate',
            '-g', 'female',
            '-b', 'not-a-date',
            '--father', parent_id
        ])
        
        # Command might succeed with warning or fail
        check_repository_health()
    
    def test_repository_commits_after_child_add(self, runner):
        """Test that adding a child creates proper Git commits."""
        
        # Use unique names to avoid conflicts
        import uuid
        unique_suffix = str(uuid.uuid4())[:8]
        
        # Add parents
        runner.invoke(cli, [
            'add', '-f', f'CommitParent{unique_suffix}', '-l', 'Test', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', f'CommitMom{unique_suffix}', '-l', 'Test', '-g', 'female'
        ])
        
        # Marry the parents using correct syntax
        runner.invoke(cli, [
            'marry', '--male', f'CommitParent{unique_suffix}', '--female', f'CommitMom{unique_suffix}'
        ])
        
        # Add child person first
        runner.invoke(cli, [
            'add', '-f', f'CommitChild{unique_suffix}', '-l', 'Test', '-g', 'female'
        ])
        
        # Get initial commit counts
        data_repo = Repo(Path('.'))
        graph_repo = Repo(Path('family_graph'))
        
        initial_data_commits = len(list(data_repo.iter_commits()))
        initial_graph_commits = len(list(graph_repo.iter_commits()))
        
        # Link child to parents
        result = runner.invoke(cli, [
            'child',
            f'CommitChild{unique_suffix}',
            '--father', f'CommitParent{unique_suffix}',
            '--mother', f'CommitMom{unique_suffix}'
        ])
        
        assert result.exit_code == 0
        
        # Check that commits were created
        final_data_commits = len(list(data_repo.iter_commits()))
        final_graph_commits = len(list(graph_repo.iter_commits()))
        
        assert final_data_commits > initial_data_commits, "Data repository should have new commits"
        assert final_graph_commits > initial_graph_commits, "Graph repository should have new commits"
        
        check_repository_health()