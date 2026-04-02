"""Feature progress tracking: manages per-feature progress files during implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


def initialize_feature_progress(
    feature_id: str,
    feature_xml: str,
    output_dir: str,
) -> dict:
    """Create a feature progress tracking file from a feature spec XML.

    Parses the acceptance criteria from the XML and creates a progress file
    with each criterion in ``pending`` status.

    Args:
        feature_id: The feature ID (e.g., ``F001``).
        feature_xml: Raw XML content of the feature spec.
        output_dir: Directory to write the progress file to.

    Returns:
        The created progress dict.

    Raises:
        ValueError: If the XML cannot be parsed or has no acceptance criteria.
    """
    try:
        root = ElementTree.fromstring(feature_xml)
    except ElementTree.ParseError as e:
        raise ValueError(f"Cannot parse feature spec XML: {e}") from e

    ac_elem = root.find("acceptance_criteria")
    if ac_elem is None:
        raise ValueError(f"Feature {feature_id} has no acceptance_criteria element")

    criteria = []
    for criterion in ac_elem.findall("criterion"):
        text = (criterion.text or "").strip()
        if text:
            criteria.append({
                "criterion": text,
                "status": "pending",
                "tests": [],
                "commits": [],
            })

    if not criteria:
        raise ValueError(f"Feature {feature_id} has no acceptance criteria")

    progress = {
        "feature_id": feature_id,
        "status": "not_started",
        "acceptance_criteria": criteria,
        "started_at": None,
        "completed_at": None,
        "evaluator_verdict": None,
        "retry_count": 0,
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    progress_file = output_path / f"feature-progress-{feature_id}.json"
    progress_file.write_text(json.dumps(progress, indent=2) + "\n")

    return progress


def read_feature_progress(progress_file: str) -> dict:
    """Read a feature progress file.

    Args:
        progress_file: Path to the progress JSON file.

    Returns:
        The progress dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    return json.loads(Path(progress_file).read_text())


def update_feature_status(
    progress_file: str,
    status: str | None = None,
    criterion_index: int | None = None,
    criterion_status: str | None = None,
    test_name: str | None = None,
    commit_hash: str | None = None,
    evaluator_verdict: str | None = None,
    increment_retry: bool = False,
) -> dict:
    """Update a feature progress file.

    Args:
        progress_file: Path to the progress JSON file.
        status: New overall status (not_started, in_progress, complete).
        criterion_index: 0-based index of the criterion to update.
        criterion_status: New status for the criterion (pending, in_progress, complete).
        test_name: Test name to append to the criterion's test list.
        commit_hash: Commit hash to append to the criterion's commit list.
        evaluator_verdict: Set the evaluator verdict (pass, fail).
        increment_retry: If True, increment the retry count.

    Returns:
        The updated progress dict.
    """
    path = Path(progress_file)
    progress = json.loads(path.read_text())

    now = datetime.now(timezone.utc).isoformat()

    if status is not None:
        progress["status"] = status
        if status == "in_progress" and progress["started_at"] is None:
            progress["started_at"] = now
        elif status == "complete":
            progress["completed_at"] = now

    if criterion_index is not None and 0 <= criterion_index < len(progress["acceptance_criteria"]):
        criterion = progress["acceptance_criteria"][criterion_index]
        if criterion_status is not None:
            criterion["status"] = criterion_status
        if test_name is not None:
            criterion["tests"].append(test_name)
        if commit_hash is not None:
            criterion["commits"].append(commit_hash)

    if evaluator_verdict is not None:
        progress["evaluator_verdict"] = evaluator_verdict

    if increment_retry:
        progress["retry_count"] = progress.get("retry_count", 0) + 1

    path.write_text(json.dumps(progress, indent=2) + "\n")
    return progress


def aggregate_wave_progress(
    implement_dir: str,
    wave_features: list[str],
) -> dict:
    """Aggregate progress across all features in a wave.

    Args:
        implement_dir: Path to the implement phase directory.
        wave_features: List of feature IDs in the wave.

    Returns:
        Dict with aggregated progress::

            {
                "total_features": 3,
                "complete": 1,
                "in_progress": 1,
                "not_started": 1,
                "failed": 0,
                "features": {
                    "F001": {"status": "complete", "criteria_done": 3, "criteria_total": 3},
                    ...
                }
            }
    """
    impl_path = Path(implement_dir)
    features: dict[str, dict] = {}
    counts = {"complete": 0, "in_progress": 0, "not_started": 0, "failed": 0}

    for fid in wave_features:
        progress_file = impl_path / f"feature-progress-{fid}.json"
        if not progress_file.exists():
            features[fid] = {"status": "not_started", "criteria_done": 0, "criteria_total": 0}
            counts["not_started"] += 1
            continue

        progress = json.loads(progress_file.read_text())
        status = progress.get("status", "not_started")
        criteria = progress.get("acceptance_criteria", [])
        criteria_done = sum(1 for c in criteria if c.get("status") == "complete")
        criteria_total = len(criteria)

        # Check for failure
        if progress.get("evaluator_verdict") == "fail":
            status = "failed"

        features[fid] = {
            "status": status,
            "criteria_done": criteria_done,
            "criteria_total": criteria_total,
        }

        if status == "complete":
            counts["complete"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "in_progress":
            counts["in_progress"] += 1
        else:
            counts["not_started"] += 1

    return {
        "total_features": len(wave_features),
        **counts,
        "features": features,
    }


def is_wave_complete(implement_dir: str, wave_features: list[str]) -> bool:
    """Check if all features in a wave are complete.

    Args:
        implement_dir: Path to the implement phase directory.
        wave_features: List of feature IDs in the wave.

    Returns:
        True if all features have status "complete" with evaluator verdict "pass".
    """
    impl_path = Path(implement_dir)
    for fid in wave_features:
        progress_file = impl_path / f"feature-progress-{fid}.json"
        if not progress_file.exists():
            return False
        progress = json.loads(progress_file.read_text())
        if progress.get("status") != "complete":
            return False
        if progress.get("evaluator_verdict") != "pass":
            return False
    return True


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for feature progress management."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: feature-progress.sh <command> [args]", file=sys.stderr)
        print("Commands: init, read, update, aggregate, is-complete", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        data = json.loads(sys.stdin.read())
        progress = initialize_feature_progress(
            feature_id=data["feature_id"],
            feature_xml=data["feature_xml"],
            output_dir=data["output_dir"],
        )
        print(json.dumps(progress, indent=2))

    elif command == "read":
        if len(sys.argv) < 3:
            print("Usage: feature-progress.sh read <progress_file>", file=sys.stderr)
            sys.exit(1)
        progress = read_feature_progress(sys.argv[2])
        print(json.dumps(progress, indent=2))

    elif command == "update":
        data = json.loads(sys.stdin.read())
        progress = update_feature_status(
            progress_file=data["progress_file"],
            status=data.get("status"),
            criterion_index=data.get("criterion_index"),
            criterion_status=data.get("criterion_status"),
            test_name=data.get("test_name"),
            commit_hash=data.get("commit_hash"),
            evaluator_verdict=data.get("evaluator_verdict"),
            increment_retry=data.get("increment_retry", False),
        )
        print(json.dumps(progress, indent=2))

    elif command == "aggregate":
        data = json.loads(sys.stdin.read())
        result = aggregate_wave_progress(
            implement_dir=data["implement_dir"],
            wave_features=data["wave_features"],
        )
        print(json.dumps(result, indent=2))

    elif command == "is-complete":
        data = json.loads(sys.stdin.read())
        complete = is_wave_complete(
            implement_dir=data["implement_dir"],
            wave_features=data["wave_features"],
        )
        print(json.dumps({"complete": complete}))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


# ─── Aliases for common naming guesses ────────────────────────────────────────
update_progress = update_feature_status
update_feature_progress = update_feature_status
mark_feature_complete = update_feature_status
get_feature_progress = read_feature_progress
init_feature_progress = initialize_feature_progress
check_wave_complete = is_wave_complete


if __name__ == "__main__":
    main()
