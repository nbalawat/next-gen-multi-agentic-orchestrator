"""F2-level integration tests for worktree manager. Uses real git repos, zero LLM calls.

Each test creates a fresh git repo in tmp_path to test actual worktree behavior.
"""

import json
import subprocess
import pytest
from pathlib import Path

from rapids_core.worktree_manager import (
    create_worktree,
    remove_worktree,
    list_worktrees,
    get_worktree_status,
    merge_worktree,
    cleanup_merged_worktrees,
    WorktreeInfo,
    MergeResult,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a fresh git repository with an initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)

    # Create initial commit (worktrees need at least one commit)
    (repo / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True)

    return repo


class TestCreateWorktree:
    def test_creates_branch_and_directory(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        assert Path(wt_path).is_dir()
        # Branch should exist
        result = subprocess.run(
            ["git", "branch", "--list", "rapids/test/F001"],
            cwd=git_repo, capture_output=True, text=True,
        )
        assert "rapids/test/F001" in result.stdout

    def test_worktree_has_repo_files(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        assert (Path(wt_path) / "README.md").exists()

    def test_custom_worktree_directory(self, git_repo, tmp_path):
        custom_dir = str(tmp_path / "custom-worktree")
        wt_path = create_worktree("rapids/test/F001", worktree_dir=custom_dir, cwd=str(git_repo))
        assert wt_path == str(Path(custom_dir).resolve())
        assert Path(wt_path).is_dir()

    def test_worktree_is_independent(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        # Write a file in the worktree
        (Path(wt_path) / "new_file.txt").write_text("worktree content")
        # File should NOT exist in main repo
        assert not (git_repo / "new_file.txt").exists()

    def test_multiple_worktrees(self, git_repo):
        wt1 = create_worktree("rapids/test/F001", cwd=str(git_repo))
        wt2 = create_worktree("rapids/test/F002", cwd=str(git_repo))
        assert Path(wt1).is_dir()
        assert Path(wt2).is_dir()
        assert wt1 != wt2


class TestRemoveWorktree:
    def test_removes_directory(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        assert Path(wt_path).is_dir()
        remove_worktree(wt_path, cwd=str(git_repo))
        assert not Path(wt_path).is_dir()

    def test_force_remove_with_changes(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        # Create uncommitted changes
        (Path(wt_path) / "dirty_file.txt").write_text("uncommitted")
        remove_worktree(wt_path, force=True, cwd=str(git_repo))
        assert not Path(wt_path).is_dir()

    def test_remove_nonexistent_raises(self, git_repo):
        with pytest.raises(RuntimeError):
            remove_worktree("/tmp/nonexistent-worktree-12345", cwd=str(git_repo))


class TestListWorktrees:
    def test_lists_main_worktree(self, git_repo):
        worktrees = list_worktrees(cwd=str(git_repo))
        assert len(worktrees) >= 1
        assert any(wt.branch == "main" for wt in worktrees)

    def test_lists_created_worktrees(self, git_repo):
        create_worktree("rapids/test/F001", cwd=str(git_repo))
        create_worktree("rapids/test/F002", cwd=str(git_repo))
        worktrees = list_worktrees(cwd=str(git_repo))
        branches = [wt.branch for wt in worktrees]
        assert "rapids/test/F001" in branches
        assert "rapids/test/F002" in branches

    def test_removed_worktree_not_listed(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        remove_worktree(wt_path, cwd=str(git_repo))
        worktrees = list_worktrees(cwd=str(git_repo))
        branches = [wt.branch for wt in worktrees]
        assert "rapids/test/F001" not in branches


class TestGetWorktreeStatus:
    def test_existing_worktree(self, git_repo):
        create_worktree("rapids/test/F001", cwd=str(git_repo))
        status = get_worktree_status("rapids/test/F001", cwd=str(git_repo))
        assert status["exists"] is True
        assert status["path"] is not None

    def test_nonexistent_branch(self, git_repo):
        status = get_worktree_status("rapids/test/F999", cwd=str(git_repo))
        assert status["exists"] is False

    def test_clean_worktree(self, git_repo):
        create_worktree("rapids/test/F001", cwd=str(git_repo))
        status = get_worktree_status("rapids/test/F001", cwd=str(git_repo))
        assert status["clean"] is True


class TestMergeWorktree:
    def test_fast_forward_merge(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))
        # Create a commit in the worktree
        new_file = Path(wt_path) / "feature.py"
        new_file.write_text("def feature(): pass\n")
        subprocess.run(["git", "add", "feature.py"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add feature"], cwd=wt_path, capture_output=True,
        )

        # Merge back
        result = merge_worktree("rapids/test/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is True
        assert result.merged_commits >= 1
        assert result.conflict is False

        # Verify file exists in main
        assert (git_repo / "feature.py").exists()

    def test_merge_with_multiple_commits(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))

        # Create multiple commits
        for i in range(3):
            f = Path(wt_path) / f"file_{i}.py"
            f.write_text(f"# File {i}\n")
            subprocess.run(["git", "add", f"file_{i}.py"], cwd=wt_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Add file {i}"], cwd=wt_path, capture_output=True,
            )

        result = merge_worktree("rapids/test/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is True
        assert result.merged_commits >= 3

    def test_merge_conflict_detection(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))

        # Modify README in both main and worktree to create conflict
        (git_repo / "README.md").write_text("# Main changes\n")
        subprocess.run(["git", "add", "README.md"], cwd=git_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Change README in main"], cwd=git_repo, capture_output=True,
        )

        (Path(wt_path) / "README.md").write_text("# Worktree changes\n")
        subprocess.run(["git", "add", "README.md"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Change README in worktree"], cwd=wt_path, capture_output=True,
        )

        result = merge_worktree("rapids/test/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is False
        assert result.conflict is True

        # Verify merge was aborted (no MERGE_HEAD)
        merge_head = git_repo / ".git" / "MERGE_HEAD"
        assert not merge_head.exists()

    def test_merge_no_commits_succeeds(self, git_repo):
        create_worktree("rapids/test/F001", cwd=str(git_repo))
        # No changes in worktree
        result = merge_worktree("rapids/test/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is True
        assert result.merged_commits == 0


class TestCleanupMergedWorktrees:
    def test_cleans_merged_worktrees(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))

        # Create a commit and merge it
        (Path(wt_path) / "done.txt").write_text("done")
        subprocess.run(["git", "add", "done.txt"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Feature done"], cwd=wt_path, capture_output=True,
        )
        merge_worktree("rapids/test/F001", target_branch="main", cwd=str(git_repo))

        # Cleanup
        cleaned = cleanup_merged_worktrees(cwd=str(git_repo))
        assert "rapids/test/F001" in cleaned

    def test_keeps_unmerged_worktrees(self, git_repo):
        wt_path = create_worktree("rapids/test/F001", cwd=str(git_repo))

        # Create a commit but DON'T merge
        (Path(wt_path) / "wip.txt").write_text("work in progress")
        subprocess.run(["git", "add", "wip.txt"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "WIP"], cwd=wt_path, capture_output=True,
        )

        cleaned = cleanup_merged_worktrees(cwd=str(git_repo))
        assert "rapids/test/F001" not in cleaned

        # Worktree should still exist
        worktrees = list_worktrees(cwd=str(git_repo))
        branches = [wt.branch for wt in worktrees]
        assert "rapids/test/F001" in branches


class TestFullLifecycle:
    def test_create_work_commit_merge_cleanup(self, git_repo):
        """End-to-end test: create → work → commit → merge → cleanup."""
        # 1. Create worktree
        wt_path = create_worktree("rapids/proj/F001", cwd=str(git_repo))
        assert Path(wt_path).is_dir()

        # 2. Simulate agent work
        feature_file = Path(wt_path) / "src" / "feature.py"
        feature_file.parent.mkdir(parents=True, exist_ok=True)
        feature_file.write_text("def my_feature():\n    return 42\n")

        test_file = Path(wt_path) / "tests" / "test_feature.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("from src.feature import my_feature\ndef test_it(): assert my_feature() == 42\n")

        # 3. Commit in worktree
        subprocess.run(["git", "add", "-A"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(F001): implement feature"],
            cwd=wt_path, capture_output=True,
        )

        # 4. Verify worktree status
        status = get_worktree_status("rapids/proj/F001", cwd=str(git_repo))
        assert status["exists"] is True
        assert status["clean"] is True

        # 5. Merge back to main
        result = merge_worktree("rapids/proj/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is True
        assert result.merged_commits >= 1

        # 6. Verify merged content in main
        assert (git_repo / "src" / "feature.py").exists()
        assert (git_repo / "tests" / "test_feature.py").exists()
        content = (git_repo / "src" / "feature.py").read_text()
        assert "my_feature" in content

        # 7. Cleanup
        cleaned = cleanup_merged_worktrees(cwd=str(git_repo))
        assert "rapids/proj/F001" in cleaned

        # 8. Verify cleanup
        assert not Path(wt_path).is_dir()
        worktrees = list_worktrees(cwd=str(git_repo))
        branches = [wt.branch for wt in worktrees]
        assert "rapids/proj/F001" not in branches

    def test_multiple_features_parallel(self, git_repo):
        """Multiple features implemented in parallel worktrees, merged sequentially."""
        # Create 3 parallel worktrees
        wt_paths = {}
        for fid in ["F001", "F002", "F003"]:
            wt_paths[fid] = create_worktree(f"rapids/proj/{fid}", cwd=str(git_repo))

        # Simulate work in each (non-conflicting files)
        for fid, wt_path in wt_paths.items():
            f = Path(wt_path) / f"{fid.lower()}.py"
            f.write_text(f"# Feature {fid}\ndef {fid.lower()}(): pass\n")
            subprocess.run(["git", "add", "-A"], cwd=wt_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"feat({fid}): implement"],
                cwd=wt_path, capture_output=True,
            )

        # Merge all back sequentially
        for fid in ["F001", "F002", "F003"]:
            result = merge_worktree(f"rapids/proj/{fid}", target_branch="main", cwd=str(git_repo))
            assert result.success is True, f"Failed to merge {fid}: {result.error}"

        # Verify all files exist in main
        for fid in ["F001", "F002", "F003"]:
            assert (git_repo / f"{fid.lower()}.py").exists()

        # Cleanup all
        cleaned = cleanup_merged_worktrees(cwd=str(git_repo))
        assert len(cleaned) == 3

    def test_feature_progress_in_worktree(self, git_repo):
        """Feature progress files work correctly in worktree context."""
        from rapids_core.feature_progress import (
            initialize_feature_progress,
            update_feature_status,
            read_feature_progress,
        )

        wt_path = create_worktree("rapids/proj/F001", cwd=str(git_repo))

        # Create .rapids structure in worktree (simulating worktree-create hook)
        impl_dir = Path(wt_path) / ".rapids" / "phases" / "implement"
        impl_dir.mkdir(parents=True, exist_ok=True)

        feature_xml = """<feature id="F001" version="1.0" priority="high" depends_on="" plugin="">
            <n>Test Feature</n>
            <description>Test</description>
            <acceptance_criteria>
                <criterion>Criterion 1</criterion>
                <criterion>Criterion 2</criterion>
            </acceptance_criteria>
        </feature>"""

        # Initialize progress in worktree
        progress = initialize_feature_progress("F001", feature_xml, str(impl_dir))
        assert progress["status"] == "not_started"
        assert len(progress["acceptance_criteria"]) == 2

        # Update progress
        progress_file = str(impl_dir / "feature-progress-F001.json")
        update_feature_status(progress_file, status="in_progress", criterion_index=0, criterion_status="complete")

        # Read back
        updated = read_feature_progress(progress_file)
        assert updated["status"] == "in_progress"
        assert updated["acceptance_criteria"][0]["status"] == "complete"

        # Commit progress file in worktree
        subprocess.run(["git", "add", "-A"], cwd=wt_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat(F001): criterion 1 done"],
            cwd=wt_path, capture_output=True,
        )

        # Merge and verify progress file comes with it
        result = merge_worktree("rapids/proj/F001", target_branch="main", cwd=str(git_repo))
        assert result.success is True
        assert (git_repo / ".rapids" / "phases" / "implement" / "feature-progress-F001.json").exists()
