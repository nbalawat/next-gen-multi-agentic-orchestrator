"""Recording system: capture and replay RAPIDS sessions for regression testing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RecordingStep:
    """A single step in a recorded RAPIDS session."""

    step: int
    type: str
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    event: str = ""
    path: str = ""
    phase: str = ""

    def matches(self, step_type: str, **filters) -> bool:
        if self.type != step_type:
            return False
        for key, value in filters.items():
            if key == "event" and self.event != value:
                return False
            if key == "phase" and self.phase != value:
                return False
        return True


class Recording:
    """A loaded recording with step access methods."""

    def __init__(self, steps: list[RecordingStep], artifacts: dict[str, str] | None = None,
                 metadata: dict | None = None):
        self.steps = steps
        self.artifacts = artifacts or {}
        self.metadata = metadata or {}

    def get_step(self, step_type: str, **filters) -> RecordingStep | None:
        for step in self.steps:
            if step.matches(step_type, **filters):
                return step
        return None

    def get_steps(self, step_type: str, **filters) -> list[RecordingStep]:
        return [s for s in self.steps if s.matches(step_type, **filters)]

    def get_artifact_content(self, path: str) -> str | None:
        return self.artifacts.get(path)


def load_recording(recording_dir: str | Path) -> Recording:
    """Load a recording from a directory containing recording.jsonl and artifacts/.

    Args:
        recording_dir: Path to the recording directory.

    Returns:
        Recording object with loaded steps and artifacts.
    """
    recording_dir = Path(recording_dir)
    recording_file = recording_dir / "recording.jsonl"

    if not recording_file.is_file():
        raise FileNotFoundError(f"Recording file not found: {recording_file}")

    steps: list[RecordingStep] = []
    for line in recording_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        steps.append(RecordingStep(
            step=data.get("step", 0),
            type=data.get("type", ""),
            input=data.get("input", {}),
            output=data.get("output", {}),
            event=data.get("event", ""),
            path=data.get("path", ""),
            phase=data.get("phase", ""),
        ))

    # Load artifacts
    artifacts: dict[str, str] = {}
    artifacts_dir = recording_dir / "artifacts"
    if artifacts_dir.is_dir():
        for artifact_file in artifacts_dir.rglob("*"):
            if artifact_file.is_file():
                rel_path = str(artifact_file.relative_to(artifacts_dir))
                try:
                    artifacts[rel_path] = artifact_file.read_text()
                except UnicodeDecodeError:
                    continue

    # Load metadata
    metadata: dict = {}
    metadata_file = recording_dir / "metadata.json"
    if metadata_file.is_file():
        metadata = json.loads(metadata_file.read_text())

    return Recording(steps=steps, artifacts=artifacts, metadata=metadata)


def create_synthetic_recording(steps: list[dict], artifacts: dict[str, str] | None = None) -> Recording:
    """Create an in-memory recording for testing without captured data.

    Args:
        steps: List of step dicts.
        artifacts: Optional dict mapping path to content.

    Returns:
        Recording object.
    """
    recording_steps = [
        RecordingStep(
            step=s.get("step", i),
            type=s.get("type", ""),
            input=s.get("input", {}),
            output=s.get("output", {}),
            event=s.get("event", ""),
            path=s.get("path", ""),
            phase=s.get("phase", ""),
        )
        for i, s in enumerate(steps)
    ]
    return Recording(
        steps=recording_steps,
        artifacts=artifacts or {},
        metadata={"synthetic": True},
    )
