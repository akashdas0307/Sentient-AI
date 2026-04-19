"""Unit tests for guard_critical_files.sh pre-commit hook."""
import subprocess
import os
from pathlib import Path

import pytest


def run_hook(hook_path: str, cwd: str) -> tuple[int, str, str]:
    """Run a hook script and return exit code, stdout, stderr."""
    result = subprocess.run(
        ["bash", hook_path],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestGuardCriticalFiles:
    """Tests for the critical file protection pre-commit hook."""

    @pytest.fixture
    def temp_git_repo(self, tmp_path):
        """Create a temporary git repo for testing."""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    def test_no_violation_when_no_deletions(self, temp_git_repo, tmp_path):
        """Hook passes when no protected files are staged for deletion."""
        hook_path = tmp_path / "guard_critical_files.sh"
        hook_path.write_text("""#!/usr/bin/env bash
exit 0
""")
        os.chmod(hook_path, 0o755)

        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 0

    def test_protected_config_file_cannot_be_deleted(self, temp_git_repo, tmp_path):
        """Deleting a config/ file is blocked by the hook."""
        # Copy guard script to temp location
        guard_path = Path(__file__).parent.parent.parent / "scripts" / "guard_critical_files.sh"
        hook_path = tmp_path / "pre-commit"
        hook_path.write_text(guard_path.read_text())
        os.chmod(hook_path, 0o755)

        # Create and commit a protected file
        protected_file = temp_git_repo / "config" / "system.yaml"
        protected_file.parent.mkdir(exist_ok=True)
        protected_file.write_text("key: value\n")

        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Stage the deletion
        subprocess.run(["git", "rm", "config/system.yaml"], cwd=temp_git_repo, check=True, capture_output=True)

        # Run hook
        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 1, f"Hook should reject deletion of config/system.yaml, got: {stderr}"
        assert "config/system.yaml" in stderr

    def test_protected_source_file_cannot_be_deleted(self, temp_git_repo, tmp_path):
        """Deleting a src/sentient/ file is blocked by the hook."""
        guard_path = Path(__file__).parent.parent.parent / "scripts" / "guard_critical_files.sh"
        hook_path = tmp_path / "pre-commit"
        hook_path.write_text(guard_path.read_text())
        os.chmod(hook_path, 0o755)

        # Create and commit a protected file
        protected_file = temp_git_repo / "src" / "sentient" / "core.py"
        protected_file.parent.mkdir(parents=True, exist_ok=True)
        protected_file.write_text("# source code\n")

        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Stage the deletion
        subprocess.run(["git", "rm", "src/sentient/core.py"], cwd=temp_git_repo, check=True, capture_output=True)

        # Run hook
        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 1, "Hook should reject deletion of src/sentient/core.py"
        assert "src/sentient/core.py" in stderr

    def test_unprotected_file_can_be_deleted(self, temp_git_repo, tmp_path):
        """Deleting a non-protected file is allowed."""
        guard_path = Path(__file__).parent.parent.parent / "scripts" / "guard_critical_files.sh"
        hook_path = tmp_path / "pre-commit"
        hook_path.write_text(guard_path.read_text())
        os.chmod(hook_path, 0o755)

        # Create and commit a non-protected file
        temp_file = temp_git_repo / "temp_log.txt"
        temp_file.write_text("temporary log\n")

        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Stage the deletion of non-protected file
        subprocess.run(["git", "rm", "temp_log.txt"], cwd=temp_git_repo, check=True, capture_output=True)

        # Run hook
        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 0, "Hook should allow deletion of temp_log.txt"

    def test_pyproject_toml_cannot_be_deleted(self, temp_git_repo, tmp_path):
        """Deleting pyproject.toml is blocked."""
        guard_path = Path(__file__).parent.parent.parent / "scripts" / "guard_critical_files.sh"
        hook_path = tmp_path / "pre-commit"
        hook_path.write_text(guard_path.read_text())
        os.chmod(hook_path, 0o755)

        # Create and commit pyproject.toml
        pyproject = temp_git_repo / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Stage the deletion
        subprocess.run(["git", "rm", "pyproject.toml"], cwd=temp_git_repo, check=True, capture_output=True)

        # Run hook
        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 1, "Hook should reject deletion of pyproject.toml"
        assert "pyproject.toml" in stderr

    def test_readme_cannot_be_deleted(self, temp_git_repo, tmp_path):
        """Deleting README.md is blocked."""
        guard_path = Path(__file__).parent.parent.parent / "scripts" / "guard_critical_files.sh"
        hook_path = tmp_path / "pre-commit"
        hook_path.write_text(guard_path.read_text())
        os.chmod(hook_path, 0o755)

        # Create and commit README.md
        readme = temp_git_repo / "README.md"
        readme.write_text("# Test Project\n")

        subprocess.run(["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Stage the deletion
        subprocess.run(["git", "rm", "README.md"], cwd=temp_git_repo, check=True, capture_output=True)

        # Run hook
        exit_code, stdout, stderr = run_hook(str(hook_path), str(temp_git_repo))
        assert exit_code == 1, "Hook should reject deletion of README.md"
        assert "README.md" in stderr