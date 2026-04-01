"""F1 tests for Persona Gatekeeping. Zero LLM calls."""

import json
import pytest
from pathlib import Path

import yaml

from rapids_core.persona import (
    load_personas,
    get_persona,
    set_active_persona,
    get_active_persona,
    check_permission,
    get_allowed_activities,
    can_delegate,
    format_persona_badge,
    build_persona_selection_question,
)


@pytest.fixture
def personas_dir(tmp_path):
    """Create a temp personas directory with test personas."""
    d = tmp_path / "personas"
    d.mkdir()
    personas = {
        "personas": [
            {
                "id": "lead", "name": "Lead",
                "allowed_phases": ["research", "analysis", "plan", "implement", "deploy"],
                "allowed_actions": ["read", "design", "implement", "approve_gate", "override_gate", "deploy"],
                "denied_actions": [],
                "can_delegate_to": ["developer", "reviewer"],
                "approval_required_for": [],
            },
            {
                "id": "developer", "name": "Developer",
                "allowed_phases": ["plan", "implement"],
                "allowed_actions": ["read", "implement", "modify_code", "run_tests"],
                "denied_actions": ["deploy", "override_gate"],
                "can_delegate_to": [],
                "approval_required_for": ["phase_transition"],
            },
            {
                "id": "stakeholder", "name": "Stakeholder",
                "allowed_phases": ["research", "analysis", "plan", "implement", "deploy"],
                "allowed_actions": ["read", "view_status"],
                "denied_actions": ["implement", "modify_code", "deploy"],
                "can_delegate_to": [],
                "approval_required_for": [],
            },
        ],
    }
    (d / "personas.yaml").write_text(yaml.dump(personas))
    return d


class TestLoadPersonas:
    def test_loads_all(self, personas_dir):
        personas = load_personas(personas_dir)
        assert len(personas) == 3

    def test_sets_defaults(self, personas_dir):
        personas = load_personas(personas_dir)
        for p in personas:
            assert "allowed_phases" in p
            assert "allowed_actions" in p
            assert "denied_actions" in p

    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_personas(tmp_path / "nonexistent") == []

    def test_loads_real_personas(self):
        real_dir = Path(__file__).parent.parent.parent / "rapids-core" / "personas"
        if not real_dir.exists():
            pytest.skip("rapids-core/personas/ not found")
        personas = load_personas(real_dir)
        assert len(personas) >= 4
        ids = [p["id"] for p in personas]
        assert "lead" in ids
        assert "developer" in ids


class TestGetPersona:
    def test_found(self, personas_dir):
        p = get_persona("developer", personas_dir)
        assert p is not None
        assert p["name"] == "Developer"

    def test_not_found(self, personas_dir):
        assert get_persona("nonexistent", personas_dir) is None


class TestSetActivePersona:
    def test_sets_persona(self, personas_dir):
        config = {}
        # Patch to use test personas
        from unittest.mock import patch
        with patch("rapids_core.persona._PERSONAS_DIR", personas_dir):
            set_active_persona(config, "developer")
        assert config["active_persona"] == "developer"

    def test_invalid_raises(self, personas_dir):
        from unittest.mock import patch
        with patch("rapids_core.persona._PERSONAS_DIR", personas_dir):
            with pytest.raises(ValueError, match="Unknown persona"):
                set_active_persona({}, "nonexistent")


class TestGetActivePersona:
    def test_defaults_to_lead(self, personas_dir):
        from unittest.mock import patch
        with patch("rapids_core.persona._PERSONAS_DIR", personas_dir):
            p = get_active_persona({})
        assert p is not None
        assert p["id"] == "lead"

    def test_returns_set_persona(self, personas_dir):
        from unittest.mock import patch
        with patch("rapids_core.persona._PERSONAS_DIR", personas_dir):
            p = get_active_persona({"active_persona": "developer"})
        assert p["id"] == "developer"


class TestCheckPermission:
    def test_lead_can_do_everything(self, personas_dir):
        lead = get_persona("lead", personas_dir)
        result = check_permission(lead, "deploy", phase="deploy")
        assert result["allowed"] is True

    def test_developer_cannot_deploy(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        result = check_permission(dev, "deploy", phase="implement")
        assert result["allowed"] is False

    def test_developer_cannot_override_gate(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        result = check_permission(dev, "override_gate")
        assert result["allowed"] is False

    def test_developer_can_implement(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        result = check_permission(dev, "implement", phase="implement")
        assert result["allowed"] is True

    def test_stakeholder_cannot_implement(self, personas_dir):
        sh = get_persona("stakeholder", personas_dir)
        result = check_permission(sh, "implement")
        assert result["allowed"] is False

    def test_phase_restriction(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        # Developer can't work in research phase
        result = check_permission(dev, "read", phase="research")
        assert result["allowed"] is False

    def test_approval_required(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        result = check_permission(dev, "phase_transition")
        assert result.get("requires_approval") is True

    def test_denied_overrides_allowed(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        # deploy is in denied_actions even though developer has "read" in allowed
        result = check_permission(dev, "deploy")
        assert result["allowed"] is False


class TestGetAllowedActivities:
    def test_lead_gets_all(self, personas_dir):
        lead = get_persona("lead", personas_dir)
        activities = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
        result = get_allowed_activities(lead, "implement", activities)
        assert len(result) == 3

    def test_wrong_phase_gets_none(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        activities = [{"id": "a1"}, {"id": "a2"}]
        result = get_allowed_activities(dev, "research", activities)
        assert len(result) == 0

    def test_right_phase_gets_activities(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        activities = [{"id": "a1"}, {"id": "a2"}]
        result = get_allowed_activities(dev, "implement", activities)
        assert len(result) == 2


class TestCanDelegate:
    def test_lead_can_delegate_to_developer(self, personas_dir):
        lead = get_persona("lead", personas_dir)
        assert can_delegate(lead, "developer") is True

    def test_developer_cannot_delegate(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        assert can_delegate(dev, "lead") is False

    def test_lead_cannot_delegate_to_unknown(self, personas_dir):
        lead = get_persona("lead", personas_dir)
        assert can_delegate(lead, "stakeholder") is False


class TestFormatPersonaBadge:
    def test_format(self, personas_dir):
        dev = get_persona("developer", personas_dir)
        assert format_persona_badge(dev) == "[Developer]"


class TestBuildPersonaSelectionQuestion:
    def test_valid_payload(self, personas_dir):
        personas = load_personas(personas_dir)
        payload = build_persona_selection_question(personas)
        assert "questions" in payload
        q = payload["questions"][0]
        assert len(q["options"]) >= 2
        assert q["header"] == "Role"

    def test_lead_recommended(self, personas_dir):
        personas = load_personas(personas_dir)
        payload = build_persona_selection_question(personas)
        first = payload["questions"][0]["options"][0]
        assert "Lead" in first["label"]
        assert "Recommended" in first["label"]

    def test_max_four_options(self):
        many = [{"id": f"p{i}", "name": f"P{i}", "description": f"Desc {i}"} for i in range(6)]
        payload = build_persona_selection_question(many)
        assert len(payload["questions"][0]["options"]) <= 4
