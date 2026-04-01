"""F1 tests for Deploy Lineage. Zero LLM calls."""

import json
import pytest
from pathlib import Path

from rapids_core.lineage import (
    LineageNode,
    LineageGraph,
    build_lineage_graph,
    trace_artifact,
    trace_forward,
    format_lineage_tree,
    export_lineage_json,
)


@pytest.fixture
def rapids_dir(tmp_path):
    """Create a .rapids/ directory with lineage-relevant state."""
    rd = tmp_path / ".rapids"
    rd.mkdir()
    (rd / "audit").mkdir()
    (rd / "phases" / "analysis").mkdir(parents=True)
    (rd / "phases" / "plan").mkdir(parents=True)
    (rd / "phases" / "implement").mkdir(parents=True)
    (rd / "context").mkdir()

    # rapids.json with work items
    (rd / "rapids.json").write_text(json.dumps({
        "project": {"id": "test-project"},
        "work_items": [
            {"id": "WI-001", "title": "Build payment API", "type": "feature",
             "tier": 3, "current_phase": "implement", "status": "active",
             "created_at": "2026-03-01T00:00:00Z"},
        ],
        "active_work_item": "WI-001",
    }))

    # Activity progress for analysis phase
    (rd / "phases" / "analysis" / "activity-progress-analysis.json").write_text(json.dumps({
        "phase": "analysis",
        "activities": {
            "architecture-design": {
                "name": "Architecture Design",
                "status": "complete",
                "gate": True,
                "completed_at": "2026-03-10T00:00:00Z",
                "outputs": {"solution-design": "solution-design.md"},
            },
        },
    }))

    # Activity progress for implement phase
    (rd / "phases" / "implement" / "activity-progress-implement.json").write_text(json.dumps({
        "phase": "implement",
        "activities": {
            "wave-execution": {
                "name": "Wave Execution",
                "status": "complete",
                "gate": True,
                "completed_at": "2026-03-18T00:00:00Z",
                "outputs": {},
            },
        },
    }))

    # Feature progress for implement phase
    (rd / "phases" / "implement" / "feature-progress-F001.json").write_text(json.dumps({
        "feature_id": "F001",
        "status": "complete",
        "evaluator_verdict": "pass",
        "started_at": "2026-03-15T00:00:00Z",
        "acceptance_criteria": [
            {"criterion": "Create endpoint", "status": "complete",
             "tests": ["test_create_endpoint"], "commits": ["abc1234"]},
            {"criterion": "Add validation", "status": "complete",
             "tests": ["test_validation"], "commits": ["def5678"]},
        ],
    }))

    # Timeline with artifact creation and deployment events
    timeline_entries = [
        {"ts": "2026-03-10T00:00:00Z", "event": "artifact_created", "phase": "analysis",
         "details": {"path": "solution-design.md", "activity": "architecture-design"}},
        {"ts": "2026-03-20T00:00:00Z", "event": "deploy_staging", "phase": "deploy",
         "details": {"environment": "staging", "version": "1.0.0"}},
    ]
    (rd / "audit" / "timeline.jsonl").write_text(
        "\n".join(json.dumps(e) for e in timeline_entries) + "\n"
    )
    (rd / "audit" / "cost.jsonl").write_text("")

    return rd


class TestLineageGraph:
    def test_add_node(self):
        g = LineageGraph()
        g.add_node(LineageNode(id="n1", node_type="work_item", ref="WI-001"))
        assert "n1" in g.nodes

    def test_add_edge(self):
        g = LineageGraph()
        g.add_edge("n1", "n2")
        assert ("n1", "n2") in g.edges

    def test_no_duplicate_edges(self):
        g = LineageGraph()
        g.add_edge("n1", "n2")
        g.add_edge("n1", "n2")
        assert len(g.edges) == 1

    def test_parents(self):
        g = LineageGraph()
        g.add_edge("parent", "child")
        assert g.parents("child") == ["parent"]

    def test_children(self):
        g = LineageGraph()
        g.add_edge("parent", "child")
        assert g.children("parent") == ["child"]


class TestBuildLineageGraph:
    def test_includes_work_items(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        wi_nodes = [n for n in graph.nodes.values() if n.node_type == "work_item"]
        assert len(wi_nodes) == 1
        assert wi_nodes[0].ref == "WI-001"

    def test_includes_activities(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        act_nodes = [n for n in graph.nodes.values() if n.node_type == "activity"]
        assert len(act_nodes) >= 1
        refs = [n.ref for n in act_nodes]
        assert "architecture-design" in refs

    def test_includes_artifacts(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        art_nodes = [n for n in graph.nodes.values() if n.node_type == "artifact"]
        assert len(art_nodes) >= 1
        refs = [n.ref for n in art_nodes]
        assert "solution-design.md" in refs

    def test_includes_features(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        feat_nodes = [n for n in graph.nodes.values() if n.node_type == "feature"]
        assert len(feat_nodes) == 1
        assert feat_nodes[0].ref == "F001"

    def test_includes_commits(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        commit_nodes = [n for n in graph.nodes.values() if n.node_type == "commit"]
        refs = [n.ref for n in commit_nodes]
        assert "abc1234" in refs
        assert "def5678" in refs

    def test_includes_tests(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        test_nodes = [n for n in graph.nodes.values() if n.node_type == "test"]
        refs = [n.ref for n in test_nodes]
        assert "test_create_endpoint" in refs

    def test_includes_deployments(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        deploy_nodes = [n for n in graph.nodes.values() if n.node_type == "deployment"]
        assert len(deploy_nodes) == 1

    def test_edges_connect_activity_to_artifact(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        # architecture-design → solution-design.md
        act_id = "act:analysis:architecture-design"
        art_id = "art:analysis:solution-design.md"
        assert act_id in graph.nodes
        assert art_id in graph.nodes
        assert (act_id, art_id) in graph.edges

    def test_edges_connect_feature_to_commits(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        feat_id = "feat:F001"
        commit_id = "commit:abc1234"
        assert (feat_id, commit_id) in graph.edges

    def test_edges_connect_work_item_to_activities(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        wi_id = "wi:WI-001"
        act_ids = graph.children(wi_id)
        assert len(act_ids) >= 1

    def test_empty_rapids_dir(self, tmp_path):
        rd = tmp_path / ".rapids"
        rd.mkdir()
        graph = build_lineage_graph(str(rd))
        assert len(graph.nodes) == 0


class TestTraceArtifact:
    def test_trace_back_to_work_item(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_artifact(graph, "solution-design.md")
        types = [n.node_type for n in chain]
        assert "work_item" in types
        assert "activity" in types
        assert "artifact" in types

    def test_trace_unknown_artifact(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_artifact(graph, "nonexistent.md")
        assert chain == []

    def test_ancestors_first(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_artifact(graph, "solution-design.md")
        if len(chain) >= 2:
            # Work item should come before artifact
            wi_idx = next((i for i, n in enumerate(chain) if n.node_type == "work_item"), -1)
            art_idx = next((i for i, n in enumerate(chain) if n.node_type == "artifact"), -1)
            if wi_idx >= 0 and art_idx >= 0:
                assert wi_idx < art_idx


class TestTraceForward:
    def test_trace_from_work_item(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_forward(graph, "WI-001")
        types = {n.node_type for n in chain}
        assert "work_item" in types
        assert "activity" in types

    def test_trace_unknown_ref(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_forward(graph, "NONEXISTENT")
        assert chain == []

    def test_includes_commits_and_tests(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        chain = trace_forward(graph, "WI-001")
        types = {n.node_type for n in chain}
        assert "commit" in types
        assert "test" in types


class TestFormatLineageTree:
    def test_empty_chain(self):
        result = format_lineage_tree([])
        assert "No lineage found" in result

    def test_shows_nodes(self):
        nodes = [
            LineageNode(id="wi:WI-001", node_type="work_item", ref="WI-001", label="Build API"),
            LineageNode(id="feat:F001", node_type="feature", ref="F001", label="Payment endpoint"),
            LineageNode(id="commit:abc", node_type="commit", ref="abc1234"),
        ]
        result = format_lineage_tree(nodes, title="Trace")
        assert "WI-001" in result
        assert "F001" in result
        assert "abc1234" in result
        assert "Trace" in result

    def test_shows_type_and_phase(self):
        nodes = [
            LineageNode(id="act:a1", node_type="activity", ref="design", phase="analysis"),
        ]
        result = format_lineage_tree(nodes)
        assert "activity" in result
        assert "[analysis]" in result


class TestExportLineageJson:
    def test_export_structure(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        exported = export_lineage_json(graph)
        assert "nodes" in exported
        assert "edges" in exported
        assert "stats" in exported

    def test_stats_count_nodes(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        exported = export_lineage_json(graph)
        assert exported["stats"]["total_nodes"] == len(graph.nodes)
        assert exported["stats"]["total_edges"] == len(graph.edges)

    def test_stats_node_types(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        exported = export_lineage_json(graph)
        assert "work_item" in exported["stats"]["node_types"]
        assert "feature" in exported["stats"]["node_types"]

    def test_edges_serialized(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        exported = export_lineage_json(graph)
        for edge in exported["edges"]:
            assert "from" in edge
            assert "to" in edge

    def test_json_serializable(self, rapids_dir):
        graph = build_lineage_graph(str(rapids_dir))
        exported = export_lineage_json(graph)
        # Should not raise
        json.dumps(exported)
