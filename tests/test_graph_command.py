"""Tests for the 'fam graph' command functionality."""
import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health, get_person_ids_from_list


class TestGraphCommand:
    """Test cases for the 'fam graph' command."""
    
    def test_graph_empty_family_tree(self, runner):
        """Test generating graph for an empty family tree."""
        result = runner.invoke(cli, ['graph'])
        
        # Command should handle empty tree gracefully
        assert result.exit_code == 0 or 'empty' in result.output.lower() or 'no' in result.output.lower()
        
        check_repository_health()
    
    def test_graph_contains_all_listed_people(self, runner):
        """Test that all people from 'fam list' appear in 'fam graph' output."""
        # Add multiple people to ensure we have data
        people = [
            ('Alice', 'Smith', 'female'),
            ('Bob', 'Johnson', 'male'),
            ('Carol', 'Williams', 'female'),
            ('David', 'Brown', 'male')
        ]
        
        for first, last, gender in people:
            add_result = runner.invoke(cli, [
                'add', '-f', first, '-l', last, '-g', gender
            ])
            assert add_result.exit_code == 0
        
        # Get list of all people
        list_result = runner.invoke(cli, ['list'])
        assert list_result.exit_code == 0
        
        # Generate graph
        graph_result = runner.invoke(cli, ['graph'])
        assert graph_result.exit_code == 0
        
        # Extract person names from list output
        list_lines = list_result.output.strip().split('\n')
        listed_people = []
        
        for line in list_lines:
            # Skip empty lines and headers
            if line.strip() and not line.startswith('ID') and '---' not in line:
                # Extract names from the line (assuming format includes first and last names)
                for first, last, _ in people:
                    if first in line and last in line:
                        listed_people.append((first, last))
                        break
        
        # Verify all listed people appear in graph output
        for first, last in listed_people:
            assert first in graph_result.output or last in graph_result.output, \
                f"Person {first} {last} from list should appear in graph output"
        
        # Ensure we actually found people in the list
        assert len(listed_people) > 0, "Should have found people in the list output"
        
        check_repository_health()
    
    def test_graph_single_person(self, runner):
        """Test generating graph with a single person."""
        # Add a single person
        add_result = runner.invoke(cli, [
            'add', '-f', 'GraphTest', '-l', 'Single', '-g', 'female'
        ])
        assert add_result.exit_code == 0
        
        # Generate graph
        result = runner.invoke(cli, ['graph'])
        assert result.exit_code == 0
        
        # Should contain the person's information
        assert 'GraphTest' in result.output or 'Single' in result.output
        
        check_repository_health()
    
    def test_graph_multiple_people(self, runner):
        """Test generating graph with multiple people."""
        # Add multiple people
        people = [
            ('Alice', 'Smith', 'female'),
            ('Bob', 'Smith', 'male'),
            ('Charlie', 'Jones', 'male')
        ]
        
        for first, last, gender in people:
            add_result = runner.invoke(cli, [
                'add', '-f', first, '-l', last, '-g', gender
            ])
            assert add_result.exit_code == 0
        
        # Generate graph
        result = runner.invoke(cli, ['graph'])
        assert result.exit_code == 0
        
        # Should contain all people
        for first, last, _ in people:
            assert first in result.output or last in result.output
        
        check_repository_health()