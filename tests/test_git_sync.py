"""Tests for agent/tools/git_sync.py."""

import os
import subprocess

import pytest

from agent.tools.git_sync import sync_dashboard_repo


def _init_repo(path: str, name: str = "Test", email: str = "test@test.com") -> None:
    subprocess.run(["git", "init", path], check=True, capture_output=True)
    subprocess.run(["git", "-C", path, "config", "user.name", name], check=True, capture_output=True)
    subprocess.run(["git", "-C", path, "config", "user.email", email], check=True, capture_output=True)


class TestSyncDashboardRepo:
    def test_repo_not_present(self, tmp_path):
        result = sync_dashboard_repo(str(tmp_path / "nonexistent-abc123"))
        assert result["ok"] is False
        assert "not found" in result["reason"]

    def test_no_changes(self, tmp_path):
        repo = str(tmp_path / "repo")
        _init_repo(repo)
        # Create and commit an initial file so there's a HEAD
        file_path = os.path.join(repo, "README.md")
        with open(file_path, "w") as f:
            f.write("hello")
        subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", "init"], check=True, capture_output=True)
        # Call sync without modifying anything
        result = sync_dashboard_repo(repo, files=["README.md"])
        assert result["ok"] is True
        assert "no changes" in result["reason"]

    def test_happy_path_with_push(self, tmp_path):
        # Create a bare repo to act as the remote origin
        bare = str(tmp_path / "bare.git")
        subprocess.run(["git", "init", "--bare", bare], check=True, capture_output=True)

        # Clone it as the working repo
        work = str(tmp_path / "work")
        subprocess.run(["git", "clone", bare, work], check=True, capture_output=True)
        subprocess.run(["git", "-C", work, "config", "user.name", "Test"], check=True, capture_output=True)
        subprocess.run(["git", "-C", work, "config", "user.email", "test@test.com"], check=True, capture_output=True)

        # Create an initial commit so the branch exists on remote
        readme = os.path.join(work, "README.md")
        with open(readme, "w") as f:
            f.write("init")
        subprocess.run(["git", "-C", work, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", work, "commit", "-m", "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", work, "push", "-u", "origin", "HEAD"], check=True, capture_output=True)

        # Now write a new file and sync
        os.makedirs(os.path.join(work, "public"), exist_ok=True)
        data_file = os.path.join(work, "public", "data.json")
        with open(data_file, "w") as f:
            f.write('{"schema_version": 1}')

        result = sync_dashboard_repo(work, files=["public/data.json"])
        assert result["ok"] is True

    def test_push_failure_tolerated(self, tmp_path):
        repo = str(tmp_path / "repo")
        _init_repo(repo)

        readme = os.path.join(repo, "README.md")
        with open(readme, "w") as f:
            f.write("init")
        subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", "init"], check=True, capture_output=True)

        # Set a bad remote
        subprocess.run(
            ["git", "-C", repo, "remote", "add", "origin", "https://invalid.example.com/nope.git"],
            check=True, capture_output=True,
        )

        # Write a change so there's something to commit
        with open(readme, "w") as f:
            f.write("changed")

        result = sync_dashboard_repo(repo, files=["README.md"])
        # Push fails but function must not raise and must return ok=False
        assert result["ok"] is False
        assert "push" in result["reason"].lower() or "failed" in result["reason"].lower()
