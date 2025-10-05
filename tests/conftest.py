"""
Pytest configuration and fixtures for running fam commands via shell.
Works both when pytest is invoked from the repository root or from the sample_data directory.
"""
import os
import subprocess
from pathlib import Path
import pytest
from dataclasses import dataclass


@dataclass
class ShellResult:
    exit_code: int
    output: str


class ShellRunner:
    """Minimal runner that executes the 'fam' CLI in the sample_data directory."""
    def invoke(self, _cli_unused, args, input=None):
        # Ensure args is a list of strings
        cmd = ["fam"] + list(args)
        
        # Determine the correct working directory
        # If we're already in sample_data, use current directory
        # Otherwise, use sample_data subdirectory
        cwd = os.getcwd()
        if not cwd.endswith('sample_data'):
            sample_data_path = os.path.join(cwd, 'sample_data')
            if os.path.exists(sample_data_path):
                cwd = sample_data_path
        
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            input=input,
        )
        # Combine stdout and stderr so tests can assert on messages regardless of stream
        out = (proc.stdout or "") + (proc.stderr or "")
        return ShellResult(exit_code=proc.returncode, output=out)


@pytest.fixture(autouse=True, scope="session")
def configure_git_identity():
    """Ensure Git author/committer identity is set so commits during tests do not fail.
    Applies to the current working directory (expected to be the sample data repo) and the nested
    family_graph repo if present. Also sets environment variables as a fallback.
    """
    # Environment fallbacks for Git
    os.environ.setdefault("GIT_AUTHOR_NAME", "Test User")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", "Test User")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")

    cwd = os.getcwd()
    # Configure local repo at current working directory, if it is a git repo
    try:
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        pass

    # Configure nested family_graph repo, if present
    fg_path = Path(cwd) / "family_graph"
    if (fg_path / ".git").exists():
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(fg_path),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(fg_path),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


@pytest.fixture
def runner():
    """Provides a shell-based runner that calls 'fam' directly in the current working directory."""
    return ShellRunner()

@pytest.fixture
def temp_dir(tmp_path):
    """Provides a temporary directory as a pathlib.Path for tests that need local remotes, etc."""
    return tmp_path