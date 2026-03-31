"""F1 tests for work item manager. Zero LLM calls."""

import pytest

from rapids_core.work_item_manager import (
    migrate_rapids_json,
    next_work_item_id,
    create_work_item,
    list_work_items,
    get_work_item,
    get_active_work_item,
    switch_work_item,
    advance_work_item_phase,
    complete_work_item,
    format_work_items_table,
    WORK_ITEM_TYPES,
)


def _old_config(tier=3, phase="analysis", project_id="test"):
    """Create an old-format rapids.json config (no work_items)."""
    from rapids_core.phase_router import route_phases
    return {
        "project": {"id": project_id},
        "scope": {"tier": tier, "phases": route_phases(tier)},
        "current": {"phase": phase},
        "plugins": [],
    }


def _new_config(items=None, active_id="WI-001"):
    """Create a new-format rapids.json config with work_items."""
    if items is None:
        items = [
            {
                "id": "WI-001", "title": "Build API", "type": "feature",
                "tier": 3, "phases": ["analysis", "plan", "implement", "deploy"],
                "current_phase": "implement", "status": "active",
            },
        ]
    return {
        "project": {"id": "test"},
        "scope": {"default_tier": 3, "default_phases": ["analysis", "plan", "implement", "deploy"]},
        "work_items": items,
        "active_work_item": active_id,
        "current": {"phase": items[0]["current_phase"] if items else "implement"},
        "plugins": [],
    }


class TestMigrateRapidsJson:
    def test_old_format_gets_work_items(self):
        config = _old_config(tier=3, phase="analysis")
        migrated = migrate_rapids_json(config)
        assert "work_items" in migrated
        assert len(migrated["work_items"]) == 1

    def test_migrated_item_has_correct_tier(self):
        config = _old_config(tier=4, phase="research")
        migrated = migrate_rapids_json(config)
        item = migrated["work_items"][0]
        assert item["tier"] == 4
        assert item["current_phase"] == "research"

    def test_migrated_item_has_correct_phases(self):
        config = _old_config(tier=2)
        migrated = migrate_rapids_json(config)
        item = migrated["work_items"][0]
        assert item["phases"] == ["plan", "implement"]

    def test_sets_active_work_item(self):
        config = _old_config()
        migrated = migrate_rapids_json(config)
        assert migrated["active_work_item"] == "WI-001"

    def test_already_new_format_unchanged(self):
        config = _new_config()
        result = migrate_rapids_json(config)
        assert result is config  # Same object, no modification

    def test_preserves_plugins(self):
        config = _old_config()
        config["plugins"] = ["rapids-gcp"]
        migrated = migrate_rapids_json(config)
        assert migrated["plugins"] == ["rapids-gcp"]

    def test_preserves_project_id(self):
        config = _old_config(project_id="my-project")
        migrated = migrate_rapids_json(config)
        assert migrated["project"]["id"] == "my-project"


class TestNextWorkItemId:
    def test_empty_config(self):
        assert next_work_item_id({"work_items": []}) == "WI-001"

    def test_one_item(self):
        config = _new_config()
        assert next_work_item_id(config) == "WI-002"

    def test_gap_in_ids(self):
        config = _new_config(items=[
            {"id": "WI-001", "tier": 1, "phases": [], "current_phase": "", "status": "complete"},
            {"id": "WI-005", "tier": 1, "phases": [], "current_phase": "", "status": "active"},
        ])
        assert next_work_item_id(config) == "WI-006"

    def test_no_work_items_key(self):
        assert next_work_item_id({}) == "WI-001"


class TestCreateWorkItem:
    def test_creates_bug_fix(self):
        config = _new_config()
        item = create_work_item(config, "Fix login crash", "bug", tier=1)
        assert item["id"] == "WI-002"
        assert item["type"] == "bug"
        assert item["tier"] == 1
        assert item["phases"] == ["implement"]
        assert item["current_phase"] == "implement"
        assert item["status"] == "active"

    def test_creates_enhancement(self):
        config = _new_config()
        item = create_work_item(config, "Add logging", "enhancement", tier=2)
        assert item["tier"] == 2
        assert item["phases"] == ["plan", "implement"]

    def test_creates_feature(self):
        config = _new_config()
        item = create_work_item(config, "Payment gateway", "feature", tier=3)
        assert item["tier"] == 3
        assert "deploy" in item["phases"]

    def test_sets_as_active(self):
        config = _new_config()
        item = create_work_item(config, "Bug fix", "bug", tier=1)
        assert config["active_work_item"] == item["id"]

    def test_added_to_work_items_array(self):
        config = _new_config()
        create_work_item(config, "Bug", "bug", tier=1)
        assert len(config["work_items"]) == 2

    def test_invalid_type_raises(self):
        config = _new_config()
        with pytest.raises(ValueError, match="Invalid work item type"):
            create_work_item(config, "X", "invalid_type", tier=1)

    def test_no_tier_or_signals_raises(self):
        config = _new_config()
        with pytest.raises(ValueError, match="Either scope_signals or tier"):
            create_work_item(config, "X", "bug")

    def test_auto_migrates_old_config(self):
        config = _old_config()
        item = create_work_item(config, "Bug", "bug", tier=1)
        assert "work_items" in config
        assert len(config["work_items"]) == 2  # migrated + new


class TestListWorkItems:
    def test_lists_active_only(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 1, "phases": [], "current_phase": ""},
            {"id": "WI-002", "status": "complete", "tier": 1, "phases": [], "current_phase": ""},
        ]
        config = _new_config(items=items)
        active = list_work_items(config, active_only=True)
        assert len(active) == 1
        assert active[0]["id"] == "WI-001"

    def test_lists_all(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 1, "phases": [], "current_phase": ""},
            {"id": "WI-002", "status": "complete", "tier": 1, "phases": [], "current_phase": ""},
        ]
        config = _new_config(items=items)
        all_items = list_work_items(config, active_only=False)
        assert len(all_items) == 2

    def test_auto_migrates(self):
        config = _old_config()
        items = list_work_items(config)
        assert len(items) == 1


class TestGetWorkItem:
    def test_found(self):
        config = _new_config()
        item = get_work_item(config, "WI-001")
        assert item is not None
        assert item["id"] == "WI-001"

    def test_not_found(self):
        config = _new_config()
        assert get_work_item(config, "WI-999") is None


class TestGetActiveWorkItem:
    def test_returns_active(self):
        config = _new_config()
        item = get_active_work_item(config)
        assert item is not None
        assert item["id"] == "WI-001"

    def test_falls_back_to_first_active(self):
        config = _new_config()
        config["active_work_item"] = None
        item = get_active_work_item(config)
        assert item is not None


class TestSwitchWorkItem:
    def test_switches(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 3, "phases": ["implement"], "current_phase": "implement"},
            {"id": "WI-002", "status": "active", "tier": 1, "phases": ["implement"], "current_phase": "implement"},
        ]
        config = _new_config(items=items)
        switch_work_item(config, "WI-002")
        assert config["active_work_item"] == "WI-002"

    def test_updates_current_phase(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 3, "phases": ["analysis", "plan"], "current_phase": "analysis"},
            {"id": "WI-002", "status": "active", "tier": 1, "phases": ["implement"], "current_phase": "implement"},
        ]
        config = _new_config(items=items)
        switch_work_item(config, "WI-002")
        assert config["current"]["phase"] == "implement"

    def test_not_found_raises(self):
        config = _new_config()
        with pytest.raises(ValueError, match="not found"):
            switch_work_item(config, "WI-999")


class TestAdvanceWorkItemPhase:
    def test_advances_to_next_phase(self):
        config = _new_config(items=[{
            "id": "WI-001", "status": "active", "tier": 3,
            "phases": ["analysis", "plan", "implement", "deploy"],
            "current_phase": "analysis",
        }])
        item = advance_work_item_phase(config, "WI-001")
        assert item is not None
        assert item["current_phase"] == "plan"

    def test_last_phase_returns_none(self):
        config = _new_config(items=[{
            "id": "WI-001", "status": "active", "tier": 3,
            "phases": ["analysis", "plan", "implement", "deploy"],
            "current_phase": "deploy",
        }])
        result = advance_work_item_phase(config, "WI-001")
        assert result is None

    def test_updates_current_phase_if_active(self):
        config = _new_config(items=[{
            "id": "WI-001", "status": "active", "tier": 2,
            "phases": ["plan", "implement"],
            "current_phase": "plan",
        }])
        advance_work_item_phase(config, "WI-001")
        assert config["current"]["phase"] == "implement"

    def test_not_found_raises(self):
        config = _new_config()
        with pytest.raises(ValueError, match="not found"):
            advance_work_item_phase(config, "WI-999")

    def test_does_not_affect_other_items(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 3,
             "phases": ["analysis", "plan", "implement", "deploy"], "current_phase": "deploy"},
            {"id": "WI-002", "status": "active", "tier": 1,
             "phases": ["implement"], "current_phase": "implement"},
        ]
        config = _new_config(items=items, active_id="WI-002")
        advance_work_item_phase(config, "WI-001")  # WI-001 is at deploy, can't advance
        # WI-002 unchanged
        assert get_work_item(config, "WI-002")["current_phase"] == "implement"


class TestCompleteWorkItem:
    def test_marks_complete(self):
        config = _new_config()
        item = complete_work_item(config, "WI-001")
        assert item["status"] == "complete"
        assert "completed_at" in item

    def test_switches_active_to_next(self):
        items = [
            {"id": "WI-001", "status": "active", "tier": 3, "phases": ["implement"], "current_phase": "implement"},
            {"id": "WI-002", "status": "active", "tier": 1, "phases": ["implement"], "current_phase": "implement"},
        ]
        config = _new_config(items=items, active_id="WI-001")
        complete_work_item(config, "WI-001")
        assert config["active_work_item"] == "WI-002"

    def test_no_active_items_left(self):
        config = _new_config()
        complete_work_item(config, "WI-001")
        assert config["active_work_item"] is None

    def test_not_found_raises(self):
        config = _new_config()
        with pytest.raises(ValueError, match="not found"):
            complete_work_item(config, "WI-999")


class TestConcurrentWorkItems:
    """Tests for the core use case: multiple work items at different phases."""

    def test_bug_fix_while_in_deploy(self):
        """A project in Deploy can have a Tier 1 bug fix in Implement."""
        config = _new_config(items=[{
            "id": "WI-001", "title": "Build API", "type": "feature",
            "tier": 4, "phases": ["research", "analysis", "plan", "implement", "deploy"],
            "current_phase": "deploy", "status": "active",
        }])

        # Add a bug fix
        bug = create_work_item(config, "Fix login crash", "bug", tier=1)
        assert bug["tier"] == 1
        assert bug["phases"] == ["implement"]
        assert bug["current_phase"] == "implement"

        # Both items exist and are active
        active = list_work_items(config, active_only=True)
        assert len(active) == 2

        # Bug fix is now the active item
        assert config["active_work_item"] == bug["id"]
        assert config["current"]["phase"] == "implement"

        # Switch back to the feature
        switch_work_item(config, "WI-001")
        assert config["current"]["phase"] == "deploy"

    def test_enhancement_while_in_deploy(self):
        """A Tier 2 enhancement alongside a Tier 4 feature."""
        config = _new_config(items=[{
            "id": "WI-001", "title": "Build API", "type": "feature",
            "tier": 4, "phases": ["research", "analysis", "plan", "implement", "deploy"],
            "current_phase": "deploy", "status": "active",
        }])

        enh = create_work_item(config, "Add logging", "enhancement", tier=2)
        assert enh["phases"] == ["plan", "implement"]
        assert enh["current_phase"] == "plan"

        # Advance enhancement through its phases independently
        advance_work_item_phase(config, enh["id"])
        assert get_work_item(config, enh["id"])["current_phase"] == "implement"

        # Original feature still in deploy
        assert get_work_item(config, "WI-001")["current_phase"] == "deploy"

    def test_three_concurrent_items(self):
        """Three items at different tiers and phases."""
        config = _new_config(items=[{
            "id": "WI-001", "title": "Platform build", "type": "feature",
            "tier": 5, "phases": ["research", "analysis", "plan", "implement", "deploy", "sustain"],
            "current_phase": "sustain", "status": "active",
        }])

        create_work_item(config, "Fix crash", "bug", tier=1)
        create_work_item(config, "Add caching", "enhancement", tier=2)

        active = list_work_items(config, active_only=True)
        assert len(active) == 3

        phases = {i["id"]: i["current_phase"] for i in active}
        assert phases["WI-001"] == "sustain"
        assert phases["WI-002"] == "implement"
        assert phases["WI-003"] == "plan"


class TestFormatWorkItemsTable:
    def test_empty(self):
        result = format_work_items_table([])
        assert "No work items" in result

    def test_shows_items(self):
        items = [
            {"id": "WI-001", "title": "Build API", "type": "feature",
             "tier": 3, "current_phase": "implement", "status": "active"},
        ]
        result = format_work_items_table(items, active_id="WI-001")
        assert "WI-001" in result
        assert "feature" in result
        assert "▶" in result  # active marker

    def test_highlights_active(self):
        items = [
            {"id": "WI-001", "title": "A", "type": "feature", "tier": 3, "current_phase": "deploy", "status": "active"},
            {"id": "WI-002", "title": "B", "type": "bug", "tier": 1, "current_phase": "implement", "status": "active"},
        ]
        result = format_work_items_table(items, active_id="WI-002")
        lines = result.split("\n")
        wi002_line = [l for l in lines if "WI-002" in l][0]
        assert "▶" in wi002_line
