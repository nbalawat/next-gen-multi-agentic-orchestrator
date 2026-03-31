"""Worktree manager: git worktree lifecycle for isolated feature implementation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: str
    branch: str
    head: str
    is_bare: bool = False


@dataclass
class MergeResult:
    """Result of merging a worktree branch."""

    success: bool
    branch: str
    merged_commits: int = 0
    conflict: bool = False
    error: str = ""


def _run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def create_worktree(
    branch_name: str,
    worktree_dir: str | None = None,
    base_branch: str = "HEAD",
    cwd: str | None = None,
) -> str:
    """Create a new git worktree for isolated feature work.

    Args:
        branch_name: Branch name for the worktree (e.g., ``rapids/my-proj/F001``).
        worktree_dir: Directory path for the worktree. If None, derived from branch name
                      as ``.git/rapids-worktrees/<sanitized_branch>``.
        base_branch: The branch/commit to base the new branch on.
        cwd: Working directory for git commands.

    Returns:
        Absolute path to the created worktree directory.

    Raises:
        RuntimeError: If git worktree add fails.
    """
    if worktree_dir is None:
        # Derive worktree path from branch name
        sanitized = branch_name.replace("/", "_")
        result = _run_git(["rev-parse", "--git-dir"], cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(f"Not a git repository: {result.stderr.strip()}")
        git_dir = Path(result.stdout.strip())
        if not git_dir.is_absolute():
            git_dir = Path(cwd or ".").resolve() / git_dir
        worktree_path = git_dir.parent / ".rapids-worktrees" / sanitized
        worktree_dir = str(worktree_path)

    # Create the worktree with a new branch
    result = _run_git(
        ["worktree", "add", "-b", branch_name, worktree_dir, base_branch],
        cwd=cwd,
    )
    if result.returncode != 0:
        # Branch might already exist — try without -b
        result = _run_git(
            ["worktree", "add", worktree_dir, branch_name],
            cwd=cwd,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr.strip()}")

    return str(Path(worktree_dir).resolve())


def remove_worktree(worktree_path: str, force: bool = False, cwd: str | None = None) -> None:
    """Remove a git worktree.

    Args:
        worktree_path: Path to the worktree to remove.
        force: If True, force removal even if there are changes.
        cwd: Working directory for git commands.

    Raises:
        RuntimeError: If git worktree remove fails.
    """
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(worktree_path)

    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to remove worktree: {result.stderr.strip()}")


def list_worktrees(cwd: str | None = None) -> list[WorktreeInfo]:
    """List all git worktrees.

    Args:
        cwd: Working directory for git commands.

    Returns:
        List of WorktreeInfo for each worktree (including the main one).
    """
    result = _run_git(["worktree", "list", "--porcelain"], cwd=cwd)
    if result.returncode != 0:
        return []

    worktrees: list[WorktreeInfo] = []
    current: dict[str, str] = {}

    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            if current.get("worktree"):
                worktrees.append(WorktreeInfo(
                    path=current.get("worktree", ""),
                    branch=current.get("branch", "").replace("refs/heads/", ""),
                    head=current.get("HEAD", ""),
                    is_bare="bare" in current,
                ))
            current = {}
        elif line.startswith("worktree "):
            current["worktree"] = line[9:]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:]
        elif line == "bare":
            current["bare"] = "true"
        elif line == "detached":
            current["branch"] = "(detached)"

    # Handle last entry (no trailing blank line)
    if current.get("worktree"):
        worktrees.append(WorktreeInfo(
            path=current.get("worktree", ""),
            branch=current.get("branch", "").replace("refs/heads/", ""),
            head=current.get("HEAD", ""),
            is_bare="bare" in current,
        ))

    return worktrees


def get_worktree_status(branch_name: str, cwd: str | None = None) -> dict:
    """Get the status of a worktree by its branch name.

    Args:
        branch_name: The branch name to look up.
        cwd: Working directory for git commands.

    Returns:
        Dict with keys: exists (bool), path (str|None), clean (bool), ahead (int).
    """
    worktrees = list_worktrees(cwd=cwd)
    for wt in worktrees:
        if wt.branch == branch_name:
            # Check if clean
            status_result = _run_git(["status", "--porcelain"], cwd=wt.path)
            is_clean = status_result.returncode == 0 and not status_result.stdout.strip()

            # Count commits ahead of base
            log_result = _run_git(
                ["rev-list", "--count", f"HEAD...{branch_name}"],
                cwd=cwd,
            )
            ahead = 0
            if log_result.returncode == 0:
                try:
                    ahead = int(log_result.stdout.strip())
                except ValueError:
                    pass

            return {
                "exists": True,
                "path": wt.path,
                "clean": is_clean,
                "ahead": ahead,
            }

    return {"exists": False, "path": None, "clean": False, "ahead": 0}


def merge_worktree(
    branch_name: str,
    target_branch: str | None = None,
    cwd: str | None = None,
) -> MergeResult:
    """Merge a worktree branch back into the target branch.

    Args:
        branch_name: The branch to merge (e.g., ``rapids/my-proj/F001``).
        target_branch: The branch to merge into. If None, uses the current branch.
        cwd: Working directory for git commands (should be the main repo, not a worktree).

    Returns:
        MergeResult with success status, commit count, and conflict info.
    """
    # Get current branch if target not specified
    if target_branch is None:
        result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        if result.returncode != 0:
            return MergeResult(success=False, branch=branch_name, error=result.stderr.strip())
        target_branch = result.stdout.strip()

    # Count commits to merge
    log_result = _run_git(
        ["rev-list", "--count", f"{target_branch}..{branch_name}"],
        cwd=cwd,
    )
    merged_commits = 0
    if log_result.returncode == 0:
        try:
            merged_commits = int(log_result.stdout.strip())
        except ValueError:
            pass

    if merged_commits == 0:
        return MergeResult(
            success=True,
            branch=branch_name,
            merged_commits=0,
        )

    # Perform the merge
    result = _run_git(
        ["merge", branch_name, "--no-edit", "-m", f"Merge feature branch {branch_name}"],
        cwd=cwd,
    )

    if result.returncode != 0:
        # Check for merge conflict
        if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
            # Abort the merge to leave repo clean
            _run_git(["merge", "--abort"], cwd=cwd)
            return MergeResult(
                success=False,
                branch=branch_name,
                merged_commits=merged_commits,
                conflict=True,
                error=result.stdout.strip(),
            )
        return MergeResult(
            success=False,
            branch=branch_name,
            error=result.stderr.strip(),
        )

    return MergeResult(
        success=True,
        branch=branch_name,
        merged_commits=merged_commits,
    )


def cleanup_merged_worktrees(cwd: str | None = None) -> list[str]:
    """Remove worktrees whose branches have already been merged.

    Args:
        cwd: Working directory for git commands.

    Returns:
        List of branch names that were cleaned up.
    """
    worktrees = list_worktrees(cwd=cwd)
    current_branch_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    current_branch = current_branch_result.stdout.strip() if current_branch_result.returncode == 0 else ""

    # Get merged branches
    merged_result = _run_git(["branch", "--merged", current_branch], cwd=cwd)
    merged_branches = set()
    if merged_result.returncode == 0:
        for line in merged_result.stdout.strip().split("\n"):
            branch = line.strip().lstrip("*+ ")
            if branch:
                merged_branches.add(branch)

    cleaned = []
    for wt in worktrees:
        # Skip main worktree and current branch
        if not wt.branch or wt.branch == current_branch:
            continue
        # Only clean up rapids-prefixed branches
        if not wt.branch.startswith("rapids/"):
            continue
        if wt.branch in merged_branches:
            try:
                remove_worktree(wt.path, force=True, cwd=cwd)
                # Also delete the branch
                _run_git(["branch", "-d", wt.branch], cwd=cwd)
                cleaned.append(wt.branch)
            except RuntimeError:
                pass  # Skip if removal fails

    # Prune stale worktree entries
    _run_git(["worktree", "prune"], cwd=cwd)

    return cleaned


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for worktree management."""
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: worktree-manager.sh <command> [args]", file=sys.stderr)
        print("Commands: create, remove, list, status, merge, cleanup", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "create":
        if len(sys.argv) < 3:
            print("Usage: worktree-manager.sh create <branch_name> [worktree_dir]", file=sys.stderr)
            sys.exit(1)
        branch = sys.argv[2]
        wt_dir = sys.argv[3] if len(sys.argv) > 3 else None
        path = create_worktree(branch, worktree_dir=wt_dir)
        print(json.dumps({"path": path, "branch": branch}))

    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: worktree-manager.sh remove <worktree_path> [--force]", file=sys.stderr)
            sys.exit(1)
        force = "--force" in sys.argv
        remove_worktree(sys.argv[2], force=force)
        print(json.dumps({"removed": sys.argv[2]}))

    elif command == "list":
        wts = list_worktrees()
        print(json.dumps([{"path": w.path, "branch": w.branch, "head": w.head} for w in wts], indent=2))

    elif command == "status":
        if len(sys.argv) < 3:
            print("Usage: worktree-manager.sh status <branch_name>", file=sys.stderr)
            sys.exit(1)
        status = get_worktree_status(sys.argv[2])
        print(json.dumps(status, indent=2))

    elif command == "merge":
        if len(sys.argv) < 3:
            print("Usage: worktree-manager.sh merge <branch_name> [target_branch]", file=sys.stderr)
            sys.exit(1)
        target = sys.argv[3] if len(sys.argv) > 3 else None
        result = merge_worktree(sys.argv[2], target_branch=target)
        print(json.dumps({
            "success": result.success,
            "branch": result.branch,
            "merged_commits": result.merged_commits,
            "conflict": result.conflict,
            "error": result.error,
        }, indent=2))

    elif command == "cleanup":
        cleaned = cleanup_merged_worktrees()
        print(json.dumps({"cleaned": cleaned}))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
