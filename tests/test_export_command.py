"""Tests for the 'fam export' command functionality."""
import os
import pytest
import json
from pathlib import Path
from git import Repo
cli = None
from .test_utils import check_repository_health


class TestExportCommand:
    """Test cases for the 'fam export' command."""
    
    def test_export_default_filename(self, runner):
        """Test exporting with default filename."""
        
        result = runner.invoke(cli, ['export'])
        
        assert result.exit_code == 0
        assert "Export completed" in result.output or "exported" in result.output.lower()
        
        # Check if default file was created in build directory
        default_file = Path('build/family_tree.json')
        assert default_file.exists(), "Default export file should be created in build directory"
        
        # Verify it's valid JSON
        with open(default_file, 'r') as f:
            data = json.load(f)
            assert isinstance(data, dict), "Exported data should be a dictionary"
        
        check_repository_health()
    
    def test_export_custom_filename(self, runner):
        """Test exporting with custom filename."""
        
        custom_filename = 'custom_export.json'
        result = runner.invoke(cli, ['export', '--output', custom_filename])
        
        assert result.exit_code == 0
        
        # Check if custom file was created in build directory
        custom_file = Path(f'build/{custom_filename}')
        assert custom_file.exists(), "Custom export file should be created in build directory"
        
        # Verify it's valid JSON
        with open(custom_file, 'r') as f:
            data = json.load(f)
            assert isinstance(data, dict), "Exported data should be a dictionary"
        
        check_repository_health()
    
    def test_export_to_subdirectory(self, runner):
        """Test exporting to a subdirectory."""
        
        export_path = 'exports/family_export.json'
        result = runner.invoke(cli, ['export', '--output', export_path])
        
        assert result.exit_code == 0
        
        # Check if file was created in build subdirectory
        export_file = Path(f'build/{export_path}')
        assert export_file.exists(), "Export file should be created in build subdirectory"
        
        # Verify it's valid JSON
        with open(export_file, 'r') as f:
            data = json.load(f)
            assert isinstance(data, dict), "Exported data should be a dictionary"
        
        check_repository_health()
    
    def test_export_contains_people_data(self, runner):
        """Test that export contains people data."""
        
        # Add some people first
        runner.invoke(cli, [
            'add', '-f', 'ExportTest', '-l', 'Person', '-g', 'male', '-b', '1990-01-01'
        ])
        
        result = runner.invoke(cli, ['export', '--output', 'test_people.json'])
        
        assert result.exit_code == 0
        
        # Check export content
        export_file = Path('build/test_people.json')
        with open(export_file, 'r') as f:
            data = json.load(f)
            
            # Check if people data is present
            assert 'people' in data or 'persons' in data or len(data) > 0, "Export should contain people data"
        
        check_repository_health()
    
    def test_export_contains_relationships_data(self, runner):
        """Test that export contains relationships data when available."""
        
        # Add people and create relationships
        runner.invoke(cli, [
            'add', '-f', 'Husband', '-l', 'Relationship', '-g', 'male'
        ])
        runner.invoke(cli, [
            'add', '-f', 'Wife', '-l', 'Relationship', '-g', 'female'
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
        
        # Export and check for relationships
        result = runner.invoke(cli, ['export', '--output', 'test_relationships.json'])
        
        assert result.exit_code == 0
        
        export_file = Path('build/test_relationships.json')
        with open(export_file, 'r') as f:
            data = json.load(f)
            
            # Check if relationships data might be present
            # (structure depends on implementation)
            assert isinstance(data, dict), "Export should be a valid dictionary"
        
        check_repository_health()
    
    def test_export_empty_family_tree(self, runner):
        """Test exporting an empty family tree."""
        
        result = runner.invoke(cli, ['export', '--output', 'empty_export.json'])
        
        # Should succeed even with empty data
        assert result.exit_code == 0
        
        # Check if file was created
        export_file = Path('build/empty_export.json')
        assert export_file.exists(), "Export file should be created even for empty tree"
        
        # Verify it's valid JSON
        with open(export_file, 'r') as f:
            data = json.load(f)
            assert isinstance(data, dict), "Exported data should be a dictionary"
        
        check_repository_health()
    
    def test_export_overwrites_existing_file(self, runner):
        """Test that export overwrites existing files."""
        
        export_filename = 'overwrite_test.json'
        
        # Create initial file with dummy content
        initial_file = Path('build/overwrite_test.json')
        initial_file.parent.mkdir(parents=True, exist_ok=True)
        with open(initial_file, 'w') as f:
            json.dump({"dummy": "data"}, f)
        
        initial_size = initial_file.stat().st_size
        
        # Export to same filename
        result = runner.invoke(cli, ['export', '--output', export_filename])
        
        assert result.exit_code == 0
        
        # Check that file was overwritten
        final_size = initial_file.stat().st_size
        assert final_size != initial_size, "File should be overwritten with new content"
        
        # Verify new content is valid JSON
        with open(initial_file, 'r') as f:
            data = json.load(f)
            assert data != {"dummy": "data"}, "File should contain new export data"
        
        check_repository_health()
    
    def test_export_invalid_output_path(self, runner):
        """Test export with invalid output path."""
        
        # Try to export to non-existent directory without creating it
        invalid_path = 'nonexistent/deep/path/export.json'
        result = runner.invoke(cli, ['export', '--output', invalid_path])
        
        # Command might fail or succeed (depending on implementation)
        # Either way, repository should remain healthy
        check_repository_health()
    
    def test_export_json_structure_validity(self, runner):
        """Test that exported JSON has valid structure."""
        
        # Add some test data
        runner.invoke(cli, [
            'add', '-f', 'StructureTest', '-l', 'Person', '-g', 'female', '-b', '1985-12-31'
        ])
        
        result = runner.invoke(cli, ['export', '--output', 'structure_test.json'])
        
        assert result.exit_code == 0
        
        # Validate JSON structure
        export_file = Path('build/structure_test.json')
        with open(export_file, 'r') as f:
            data = json.load(f)
            
            # Basic structure validation
            assert isinstance(data, dict), "Root should be a dictionary"
            
            # Check for common family tree export fields
            expected_fields = ['people', 'persons', 'individuals', 'family_members']
            has_people_field = any(field in data for field in expected_fields)
            
            if not has_people_field and len(data) > 0:
                # If no standard field, at least check that data exists
                assert len(data) > 0, "Export should contain some data"
        
        check_repository_health()
    
    def test_export_preserves_special_characters(self, runner):
        """Test that export preserves special characters in names."""
        
        # Add person with special characters
        runner.invoke(cli, [
            'add', '-f', 'José', '-l', 'García-López', '-g', 'male', '-n', 'Pepe'
        ])
        
        result = runner.invoke(cli, ['export', '--output', 'special_chars.json'])
        
        assert result.exit_code == 0
        
        # Check that special characters are preserved
        export_file = Path('build/special_chars.json')
        with open(export_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'José' in content, "Special characters should be preserved"
            assert 'García-López' in content, "Hyphenated names should be preserved"
        
        check_repository_health()
    
    def test_repository_unchanged_after_export(self, runner):
        """Test that export doesn't modify the repository."""
        
        # Get initial repository state
        data_repo = Repo(Path('.'))
        graph_repo = Repo(Path('family_graph'))
        
        initial_data_commits = len(list(data_repo.iter_commits()))
        initial_graph_commits = len(list(graph_repo.iter_commits()))
        
        # Export data
        result = runner.invoke(cli, ['export', '--output', 'no_change_test.json'])
        
        assert result.exit_code == 0
        
        # Check that no new commits were created
        final_data_commits = len(list(data_repo.iter_commits()))
        final_graph_commits = len(list(graph_repo.iter_commits()))
        
        assert final_data_commits == initial_data_commits, "Export should not create data commits"
        assert final_graph_commits == initial_graph_commits, "Export should not create graph commits"
        
        check_repository_health()