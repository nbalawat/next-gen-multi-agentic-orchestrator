"""Deploy Lineage: traceability from requirement through code to deployment.

Builds a directed acyclic graph (DAG) connecting work items, decisions,
activities, features, artifacts, commits, and deployments so any artifact
can be traced back to its originating requirement and any requirement can
be traced forward to its deployed artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


NODE_TYPES = (
    "work_item", "decision", "activity", "feature",
    "artifact", "test", "commit", "deployment",
)


@dataclass
class LineageNode:
    """A single node in the lineage graph."""

    id: str
    node_type: str  # one of NODE_TYPES
    ref: str  # external reference (WI-001, F001, adr-001.md, abc1234, etc.)
    label: str = ""
    phase: str = ""
    timestamp: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class LineageGraph:
    """Full lineage graph with nodes and edges."""

    nodes: dict[str, LineageNode] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)

    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        if (from_id, to_id) not in self.edges:
            self.edges.append((from_id, to_id))

    def parents(self, node_id: str) -> list[str]:
        return [f for f, t in self.edges if t == node_id]

    def children(self, node_id: str) -> list[str]:
        return [t for f, t in self.edges if f == node_id]


def build_lineage_graph(rapids_dir: str) -> LineageGraph:
    """Build a lineage graph from all RAPIDS project state.

    Walks:
    - rapids.json (work items → phases)
    - activity-progress-*.json (activities → outputs)
    - feature-progress-*.json (features → commits, tests)
    - timeline.jsonl (artifact creation events, deployments)

    Args:
        rapids_dir: Path to the ``.rapids/`` directory.

    Returns:
        A populated LineageGraph.
    """
    rdir = Path(rapids_dir)
    graph = LineageGraph()

    # 1. Work items from rapids.json
    rapids_json = rdir / "rapids.json"
    if rapids_json.exists():
        config = json.loads(rapids_json.read_text())
        for wi in config.get("work_items", []):
            wi_id = wi["id"]
            node = LineageNode(
                id=f"wi:{wi_id}",
                node_type="work_item",
                ref=wi_id,
                label=wi.get("title", ""),
                phase=wi.get("current_phase", ""),
                timestamp=wi.get("created_at", ""),
                metadata={"type": wi.get("type", ""), "tier": wi.get("tier", 0)},
            )
            graph.add_node(node)

    # 2. Activity progress files
    phases_dir = rdir / "phases"
    if phases_dir.is_dir():
        for phase_dir in sorted(phases_dir.iterdir()):
            if not phase_dir.is_dir():
                continue
            phase_name = phase_dir.name

            for ap_file in phase_dir.glob("activity-progress-*.json"):
                try:
                    ap = json.loads(ap_file.read_text())
                    for act_id, act_data in ap.get("activities", {}).items():
                        node = LineageNode(
                            id=f"act:{phase_name}:{act_id}",
                            node_type="activity",
                            ref=act_id,
                            label=act_data.get("name", act_id),
                            phase=phase_name,
                            timestamp=act_data.get("completed_at", ""),
                            metadata={"gate": act_data.get("gate", False)},
                        )
                        graph.add_node(node)

                        # Activity outputs become artifact nodes
                        for out_name, out_path in act_data.get("outputs", {}).items():
                            art_id = f"art:{phase_name}:{out_path}"
                            art_node = LineageNode(
                                id=art_id,
                                node_type="artifact",
                                ref=out_path,
                                label=out_name,
                                phase=phase_name,
                            )
                            graph.add_node(art_node)
                            graph.add_edge(f"act:{phase_name}:{act_id}", art_id)

                except (json.JSONDecodeError, KeyError):
                    continue

            # 3. Feature progress files
            for fp_file in phase_dir.glob("feature-progress-*.json"):
                try:
                    fp = json.loads(fp_file.read_text())
                    fid = fp.get("feature_id", "")
                    feat_node = LineageNode(
                        id=f"feat:{fid}",
                        node_type="feature",
                        ref=fid,
                        label=fid,
                        phase=phase_name,
                        timestamp=fp.get("started_at", ""),
                        metadata={
                            "status": fp.get("status", ""),
                            "verdict": fp.get("evaluator_verdict"),
                        },
                    )
                    graph.add_node(feat_node)

                    # Commits
                    for i, criterion in enumerate(fp.get("acceptance_criteria", [])):
                        for commit in criterion.get("commits", []):
                            commit_id = f"commit:{commit}"
                            commit_node = LineageNode(
                                id=commit_id,
                                node_type="commit",
                                ref=commit,
                                label=f"Commit for {fid} criterion {i + 1}",
                                phase=phase_name,
                            )
                            graph.add_node(commit_node)
                            graph.add_edge(f"feat:{fid}", commit_id)

                        # Tests
                        for test in criterion.get("tests", []):
                            test_id = f"test:{fid}:{test}"
                            test_node = LineageNode(
                                id=test_id,
                                node_type="test",
                                ref=test,
                                label=test,
                                phase=phase_name,
                            )
                            graph.add_node(test_node)
                            graph.add_edge(f"feat:{fid}", test_id)

                except (json.JSONDecodeError, KeyError):
                    continue

    # 4. Timeline events (artifact_created, deployment events)
    timeline_file = rdir / "audit" / "timeline.jsonl"
    if timeline_file.exists():
        for line in timeline_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                event = entry.get("event", "")

                if event == "artifact_created":
                    details = entry.get("details", {})
                    path = details.get("path", "")
                    activity = details.get("activity", "")
                    phase = entry.get("phase", "")
                    art_id = f"art:{phase}:{path}"
                    if art_id not in graph.nodes:
                        graph.add_node(LineageNode(
                            id=art_id,
                            node_type="artifact",
                            ref=path,
                            label=path,
                            phase=phase,
                            timestamp=entry.get("ts", ""),
                        ))
                    if activity:
                        act_node_id = f"act:{phase}:{activity}"
                        if act_node_id in graph.nodes:
                            graph.add_edge(act_node_id, art_id)

                elif event in ("deploy_staging", "deploy_production"):
                    details = entry.get("details", {})
                    deploy_id = f"deploy:{event}:{entry.get('ts', '')}"
                    graph.add_node(LineageNode(
                        id=deploy_id,
                        node_type="deployment",
                        ref=event,
                        label=event.replace("_", " ").title(),
                        phase="deploy",
                        timestamp=entry.get("ts", ""),
                        metadata=details,
                    ))

            except json.JSONDecodeError:
                continue

    # 5. Connect work items → activities (by phase)
    for node_id, node in graph.nodes.items():
        if node.node_type == "activity":
            # Link work items to activities in their current/past phases
            for wi_id, wi_node in graph.nodes.items():
                if wi_node.node_type == "work_item":
                    graph.add_edge(wi_id, node_id)

    # 6. Connect activities → features (implement phase activities produce features)
    for node_id, node in graph.nodes.items():
        if node.node_type == "feature":
            # Link implement-phase activities to features
            for act_id, act_node in graph.nodes.items():
                if act_node.node_type == "activity" and act_node.phase == "implement":
                    graph.add_edge(act_id, node_id)

    return graph


def trace_artifact(graph: LineageGraph, artifact_ref: str) -> list[LineageNode]:
    """Trace an artifact back to its originating requirements.

    Walks the graph backwards from the artifact to find all ancestors.

    Args:
        graph: The lineage graph.
        artifact_ref: The artifact file path or reference to trace.

    Returns:
        List of LineageNodes from root (requirement) to the artifact,
        ordered by depth (ancestors first).
    """
    # Find the artifact node
    target_id = None
    for nid, node in graph.nodes.items():
        if node.node_type == "artifact" and node.ref == artifact_ref:
            target_id = nid
            break
        if node.ref == artifact_ref:
            target_id = nid
            break

    if target_id is None:
        return []

    # BFS backwards
    visited = set()
    chain: list[LineageNode] = []
    queue = [target_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        if current in graph.nodes:
            chain.append(graph.nodes[current])
        for parent in graph.parents(current):
            queue.append(parent)

    # Reverse so ancestors come first
    chain.reverse()
    return chain


def trace_forward(graph: LineageGraph, node_ref: str) -> list[LineageNode]:
    """Trace forward from a requirement/decision to see everything it influenced.

    Args:
        graph: The lineage graph.
        node_ref: The reference to trace from (e.g., "WI-001").

    Returns:
        List of LineageNodes reachable from this node (BFS order).
    """
    # Find the node
    start_id = None
    for nid, node in graph.nodes.items():
        if node.ref == node_ref:
            start_id = nid
            break

    if start_id is None:
        return []

    visited = set()
    result: list[LineageNode] = []
    queue = [start_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        if current in graph.nodes:
            result.append(graph.nodes[current])
        for child in graph.children(current):
            queue.append(child)

    return result


def format_lineage_tree(nodes: list[LineageNode], title: str = "Lineage") -> str:
    """Format a lineage chain as an ASCII tree.

    Args:
        nodes: Ordered list of lineage nodes.
        title: Title for the tree display.

    Returns:
        Formatted ASCII tree string.
    """
    if not nodes:
        return f"  {title}: No lineage found.\n"

    type_icons = {
        "work_item": "📋",
        "decision": "🔷",
        "activity": "⚙",
        "feature": "🔧",
        "artifact": "📄",
        "test": "🧪",
        "commit": "💾",
        "deployment": "🚀",
    }

    lines = [f"  {title}", "  " + "─" * 60]

    for i, node in enumerate(nodes):
        is_last = i == len(nodes) - 1
        connector = "└──" if is_last else "├──"
        icon = type_icons.get(node.node_type, "·")
        phase_tag = f" [{node.phase}]" if node.phase else ""

        lines.append(f"  {connector} {icon} {node.node_type}: {node.ref}{phase_tag}")
        if node.label and node.label != node.ref:
            padding = "    " if is_last else "│   "
            lines.append(f"  {padding} {node.label}")

    return "\n".join(lines) + "\n"


def export_lineage_json(graph: LineageGraph) -> dict:
    """Export the full lineage graph as a JSON-serializable dict.

    Args:
        graph: The lineage graph.

    Returns:
        Dict with ``nodes`` and ``edges`` keys.
    """
    return {
        "nodes": {
            nid: {
                "id": n.id,
                "type": n.node_type,
                "ref": n.ref,
                "label": n.label,
                "phase": n.phase,
                "timestamp": n.timestamp,
                "metadata": n.metadata,
            }
            for nid, n in graph.nodes.items()
        },
        "edges": [{"from": f, "to": t} for f, t in graph.edges],
        "stats": {
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges),
            "node_types": {
                nt: sum(1 for n in graph.nodes.values() if n.node_type == nt)
                for nt in NODE_TYPES
                if any(n.node_type == nt for n in graph.nodes.values())
            },
        },
    }
