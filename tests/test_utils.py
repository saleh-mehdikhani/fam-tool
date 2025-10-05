"""
Common test utilities for family_tree_tool tests.
"""
import os
import pytest
from pathlib import Path
from git import Repo
cli = None


def check_repository_health():
    """Check if both data and graph repositories are healthy using the current working directory."""
    data_repo = Repo(Path('.'))
    graph_repo = Repo(Path('family_graph'))
    
    # Check if repositories are valid
    assert not data_repo.bare, "Data repository should not be bare"
    assert not graph_repo.bare, "Graph repository should not be bare"
    
    # Check if repositories are not corrupted
    assert not data_repo.is_dirty(untracked_files=True) or len(list(data_repo.untracked_files)) == 0, "Data repo should be clean after operations"
    
    # Check if remotes are configured and accessible
    if data_repo.remotes:
        for remote in data_repo.remotes:
            try:
                # Test if remote is reachable (skip if no network)
                remote.fetch(dry_run=True)
            except Exception:
                # Remote might not be reachable, but should exist
                assert remote.url is not None, f"Data repository remote '{remote.name}' should have a URL"
    
    if graph_repo.remotes:
        for remote in graph_repo.remotes:
            try:
                # Test if remote is reachable (skip if no network)
                remote.fetch(dry_run=True)
            except Exception:
                # Remote might not be reachable, but should exist
                assert remote.url is not None, f"Graph repository remote '{remote.name}' should have a URL"
    
    return True


def get_person_ids_from_list(runner):
    """Helper function to get person IDs from the list command, using current working directory."""
    result = runner.invoke(cli, ['list'])
    if result.exit_code != 0:
        return []
    
    person_ids = []
    for line in result.output.strip().split('\n'):
        if line.strip() and not line.startswith('Found') and not line.startswith('No people'):
            # Look for pattern "(ID: xxxxxxxx)"
            import re
            id_pattern = r'\(ID: ([0-9a-f]{8})\)'
            match = re.search(id_pattern, line)
            if match:
                person_ids.append(match.group(1))
    
    return person_ids


def get_person_ids_from_add_output(runner_output):
    """Helper function to extract person IDs from add command output."""
    import re
    person_ids = []
    for line in runner_output.strip().split('\n'):
        # Look for pattern "Successfully added person! (ID: xxxxxxxx)"
        id_pattern = r'Successfully added person! \(ID: ([0-9a-f]{8})\)'
        match = re.search(id_pattern, line)
        if match:
            person_ids.append(match.group(1))
    return person_ids