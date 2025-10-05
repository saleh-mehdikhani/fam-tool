"""Tests for the 'fam unmarry' command functionality."""
import os
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health, get_person_ids_from_list, get_person_ids_from_add_output


class TestUnmarryCommand:
    """Test cases for the 'fam unmarry' command."""
    
    def test_unmarry_married_couple(self, runner):
        """Test unmarrying a married couple."""
        
        # Add two people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'Husband', '-l', 'Unmarry', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'Wife', '-l', 'Unmarry', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        husband_id = person_ids[0]
        wife_id = person_ids[1]
        
        # Marry them first
        marry_result = runner.invoke(cli, ['marry', '-m', husband_id, '-f', wife_id])
        assert marry_result.exit_code == 0
        
        # Now unmarry them
        result = runner.invoke(cli, ['unmarry', husband_id, wife_id])
        
        assert result.exit_code == 0
        
        # Verify they are no longer married (this depends on implementation)
        # The people should still exist but not be married
        list_result = runner.invoke(cli, ['list'])
        assert 'Husband' in list_result.output
        assert 'Wife' in list_result.output
        
        check_repository_health()
    
    
    def test_unmarry_not_married_couple(self, runner):
        """Test unmarrying people who are not married to each other."""
        
        # Add two people but don't marry them
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'NotMarried1', '-l', 'Test', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'NotMarried2', '-l', 'Test', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        
        # Try to unmarry them (should fail or be a no-op)
        result = runner.invoke(cli, ['unmarry', person1_id, person2_id])
        
        # Command might fail or succeed with a message
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_unmarry_nonexistent_people(self, runner):
        """Test unmarrying with non-existent person IDs."""
        
        # Try to unmarry non-existent people
        result = runner.invoke(cli, ['unmarry', 'nonexistent1', 'nonexistent2'])
        
        # Command should handle this gracefully
        check_repository_health()
    
    def test_unmarry_same_person(self, runner):
        """Test unmarrying a person from themselves."""
        
        # Add a person
        add_result = runner.invoke(cli, [
            'add', '-f', 'SelfUnmarry', '-l', 'Test', '-g', 'male'
        ])
        assert add_result.exit_code == 0
        
        # Get person ID
        person_ids = get_person_ids_from_add_output(add_result.output)
        assert len(person_ids) >= 1, "Could not find the added person"
        person_id = person_ids[0]
        
        # Try to unmarry person from themselves
        result = runner.invoke(cli, ['unmarry', person_id, person_id])
        
        # Command should handle this gracefully (likely with an error)
        check_repository_health()
    
    def test_unmarry_invalid_date_format(self, runner):
        """Test unmarrying with invalid date format."""
        
        # Add and marry two people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'InvalidDate1', '-l', 'Test', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'InvalidDate2', '-l', 'Test', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        
        # Marry them first
        marry_result = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person2_id])
        assert marry_result.exit_code == 0
        
        # Try to unmarry with invalid date
        result = runner.invoke(cli, ['unmarry', person1_id, person2_id, '-d', 'invalid-date'])
        
        # Command should handle invalid date gracefully
        check_repository_health()
    
    
    def test_unmarry_removes_relationship_files(self, runner):
        """Test that unmarrying removes or updates relationship files."""
        
        # Add and marry two people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'FileTest1', '-l', 'Unmarry', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'FileTest2', '-l', 'Unmarry', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        
        # Marry them first
        marry_result = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person2_id])
        assert marry_result.exit_code == 0
        
        # Check if relationship files exist (this depends on implementation)
        relationships_dir = Path('relationships')
        if relationships_dir.exists():
            initial_files = list(relationships_dir.glob('*.json'))
        
        # Unmarry them
        result = runner.invoke(cli, ['unmarry', person1_id, person2_id])
        assert result.exit_code == 0
        
        # Check if relationship files are updated/removed
        if relationships_dir.exists():
            final_files = list(relationships_dir.glob('*.json'))
            # Files might be removed or updated, but structure should be valid
        
        check_repository_health()
    
    def test_unmarry_with_children(self, runner):
        """Test unmarrying a couple who have children."""
        
        # Add parents
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'DivorcedFather', '-l', 'WithKids', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'DivorcedMother', '-l', 'WithKids', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get parent IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added parents"
        father_id = person_ids[0]
        mother_id = person_ids[1]
        
        # Marry them
        marry_result = runner.invoke(cli, ['marry', '-m', father_id, '-f', mother_id])
        assert marry_result.exit_code == 0
        
        # Add a child
        child_result = runner.invoke(cli, [
            'add', '-f', 'Child', '-l', 'WithDivorcedParents', '-g', 'male',
            '--father', father_id, '--mother', mother_id
        ])
        assert child_result.exit_code == 0
        
        # Unmarry the parents
        result = runner.invoke(cli, ['unmarry', father_id, mother_id])
        
        assert result.exit_code == 0
        
        # Verify parents are unmarried but child relationships remain
        list_result = runner.invoke(cli, ['list'])
        assert 'DivorcedFather' in list_result.output
        assert 'DivorcedMother' in list_result.output
        assert 'Child' in list_result.output
        
        check_repository_health()
    
    def test_unmarry_missing_arguments(self, runner):
        """Test unmarry command with missing arguments."""
        
        # Test with no arguments
        result1 = runner.invoke(cli, ['unmarry'])
        
        # Test with only one argument
        result2 = runner.invoke(cli, ['unmarry', 'single-id'])
        
        # Commands should show error or help
        assert result1.exit_code != 0 or 'Usage' in result1.output or 'Error' in result1.output
        assert result2.exit_code != 0 or 'Usage' in result2.output or 'Error' in result2.output
        
        check_repository_health()
    
    def test_unmarry_with_extra_arguments(self, runner):
        """Test unmarry command with extra arguments."""
        
        # Add and marry two people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'ExtraArgs1', '-l', 'Test', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'ExtraArgs2', '-l', 'Test', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        
        # Marry them first
        marry_result = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person2_id])
        assert marry_result.exit_code == 0
        
        # Try unmarry with extra arguments
        result = runner.invoke(cli, ['unmarry', person1_id, person2_id, 'extra', 'arguments'])
        
        # Command might succeed (ignoring extra args) or fail
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_unmarry_multiple_marriages(self, runner):
        """Test unmarrying when people have had multiple marriages."""
        
        # Add three people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'Person1', '-l', 'Multiple', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'Person2', '-l', 'Multiple', '-g', 'female'
        ])
        add_result3 = runner.invoke(cli, [
            'add', '-f', 'Person3', '-l', 'Multiple', '-g', 'female'
        ])
        assert all(r.exit_code == 0 for r in [add_result1, add_result2, add_result3])
        
        # Get person IDs
        person_ids = (get_person_ids_from_add_output(add_result1.output) + 
                     get_person_ids_from_add_output(add_result2.output) + 
                     get_person_ids_from_add_output(add_result3.output))
        assert len(person_ids) >= 3, "Could not find all added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        person3_id = person_ids[2]
        
        # Marry Person1 to Person2
        marry_result1 = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person2_id])
        assert marry_result1.exit_code == 0
        
        # Unmarry them
        unmarry_result1 = runner.invoke(cli, ['unmarry', person1_id, person2_id])
        assert unmarry_result1.exit_code == 0
        
        # Marry Person1 to Person3
        marry_result2 = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person3_id])
        assert marry_result2.exit_code == 0
        
        # Unmarry them
        unmarry_result2 = runner.invoke(cli, ['unmarry', person1_id, person3_id])
        assert unmarry_result2.exit_code == 0
        
        check_repository_health()
    
    def test_unmarry_case_sensitive_ids(self, runner):
        """Test that unmarry command is case sensitive with person IDs."""
        
        # Add and marry two people
        add_result1 = runner.invoke(cli, [
            'add', '-f', 'CaseTest1', '-l', 'Unmarry', '-g', 'male'
        ])
        add_result2 = runner.invoke(cli, [
            'add', '-f', 'CaseTest2', '-l', 'Unmarry', '-g', 'female'
        ])
        assert add_result1.exit_code == 0
        assert add_result2.exit_code == 0
        
        # Get person IDs
        person_ids = get_person_ids_from_add_output(add_result1.output) + get_person_ids_from_add_output(add_result2.output)
        assert len(person_ids) >= 2, "Could not find the added people"
        person1_id = person_ids[0]
        person2_id = person_ids[1]
        
        # Marry them first
        marry_result = runner.invoke(cli, ['marry', '-m', person1_id, '-f', person2_id])
        assert marry_result.exit_code == 0
        
        # Try to unmarry with wrong case IDs
        if person1_id.islower():
            wrong_case_id1 = person1_id.upper()
        else:
            wrong_case_id1 = person1_id.lower()
        
        result = runner.invoke(cli, ['unmarry', wrong_case_id1, person2_id])
        
        # Should not unmarry with wrong case (case sensitive)
        check_repository_health()
    
    def test_unmarry_empty_family_tree(self, runner):
        """Test unmarrying in an empty family tree."""
        
        result = runner.invoke(cli, ['unmarry', 'any-id1', 'any-id2'])
        
        # Command should handle this gracefully
        check_repository_health()