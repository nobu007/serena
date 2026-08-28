"""Guard against pip shell-redirect artifacts (files like ``=24.0``) being tracked.

``pip install pkg>=24.0`` without quotes redirects pip's output into an empty
file named ``=24.0`` instead of installing anything. One such file ended up
committed (530583c) and had to be removed again (63861a3); the ``=*`` pattern
in ``.gitignore`` must keep these artifacts out of the tree so the mistake
cannot recur.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _is_git_worktree() -> bool:
    """Whether the tests run inside a git checkout (false e.g. for a tarball)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return result.stdout.strip() == b"true"


@pytest.mark.skipif(not _is_git_worktree(), reason="not running inside a git worktree")
@pytest.mark.parametrize("artifact", ["=24.0", "=1.2.3", "test/serena/=0.5"])
def test_pip_redirect_artifact_is_ignored(artifact: str) -> None:
    """Files created by an unquoted `pip install pkg>=x.y` must be git-ignored."""
    result = subprocess.run(
        ["git", "check-ignore", "--", artifact],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, f"{artifact} is not ignored: keep the '=*' pattern in .gitignore"


@pytest.mark.skipif(not _is_git_worktree(), reason="not running inside a git worktree")
def test_regular_files_are_not_ignored() -> None:
    """The '=*' pattern must not swallow regular repository files."""
    result = subprocess.run(
        ["git", "check-ignore", "--", "pyproject.toml"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert result.returncode == 1, "pyproject.toml should not be git-ignored"
