"""Tests for the 'fam report' command functionality."""

import pytest
from pathlib import Path
from git import Repo
cli = None
from .test_utils import get_person_ids_from_list


class TestReportCommand:
    """Test cases for the 'fam report' command."""
    
    def test_report_basic(self, runner):
        """Test that the report command runs successfully."""
        result = runner.invoke(cli, ['report'])
        assert result.exit_code == 0