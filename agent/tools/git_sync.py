"""
Commits and pushes the data.json file in the sibling dashboard repository.

Public surface:
    sync_dashboard_repo(repo_path, files=None) -> dict(ok, reason)
        Never raises. Returns {"ok": True/False, "reason": str}.
"""

import subprocess
from datetime import datetime, timezone


def sync_dashboard_repo(repo_path: str, files: list = None) -> dict:
    """Stage, commit, and push files in the given git repo. Never raises."""
    import os
    if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
        return {"ok": False, "reason": f"repo not found at {repo_path}"}

    try:
        if files:
            add_args = ["git", "-C", repo_path, "add"] + files
        else:
            add_args = ["git", "-C", repo_path, "add", "-A"]
        r = subprocess.run(add_args, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"ok": False, "reason": f"git add failed: {r.stderr}"}

        status = subprocess.run(
            ["git", "-C", repo_path, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        if not status.stdout.strip():
            return {"ok": True, "reason": "no changes to commit"}

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", f"data: run2 snapshot {ts}"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"ok": False, "reason": f"git commit failed: {r.stderr}"}

        r = subprocess.run(
            ["git", "-C", repo_path, "push"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"ok": False, "reason": f"git push failed: {r.stderr}"}

        return {"ok": True, "reason": "pushed successfully"}

    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
