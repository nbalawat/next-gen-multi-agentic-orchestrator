"""F4 smoke tests: scope classification with Haiku. ~$0.01 per run."""

import pytest

# These tests require the anthropic SDK and an API key.
# They are skipped automatically if ANTHROPIC_API_KEY is not set.

SCOPE_TEST_CASES = [
    {
        "description": "Fix the null pointer exception in the login handler",
        "expected_tier_range": (1, 2),
    },
    {
        "description": "Add a due_date field to the todo items API with validation and database migration",
        "expected_tier_range": (2, 3),
    },
    {
        "description": "Build a payment reconciliation dashboard that reads from Bigtable and displays real-time transaction matching with React",
        "expected_tier_range": (3, 4),
    },
    {
        "description": "Build a new event-driven payments platform with PubSub, Bigtable, Dataflow, and Cloud Run including monitoring and alerting",
        "expected_tier_range": (4, 5),
    },
]


@pytest.mark.f4
class TestScopeClassificationLLM:
    """Smoke tests that verify scope classification produces reasonable results.

    These tests use the deterministic scope classifier, not the LLM.
    The LLM-based version would use Haiku to classify descriptions.
    """

    def test_bug_fix_low_tier(self):
        from rapids_core.scope_classifier import classify_scope

        result = classify_scope({
            "description": "Fix the null pointer exception in the login handler",
            "files_impacted": 2,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low",
        })
        assert 1 <= result.tier <= 2

    def test_medium_project_mid_tier(self):
        from rapids_core.scope_classifier import classify_scope

        result = classify_scope({
            "description": "Build a payment dashboard with Bigtable",
            "files_impacted": 15,
            "new_infrastructure": False,
            "integrations": ["bigtable", "react"],
            "domain_complexity": "moderate",
        })
        assert 3 <= result.tier <= 4

    def test_large_project_high_tier(self):
        from rapids_core.scope_classifier import classify_scope

        result = classify_scope({
            "description": "Build new event-driven payments platform",
            "files_impacted": 100,
            "new_infrastructure": True,
            "integrations": ["pubsub", "bigtable", "dataflow", "cloud-run"],
            "domain_complexity": "high",
        })
        assert result.tier >= 4
