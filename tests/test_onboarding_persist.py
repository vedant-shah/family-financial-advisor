"""persist_member_data: save a member's onboarding money/goals slice to memory.

Runs after the roster (identity) is saved. Maps the draft's finances/goals/
dependent-support into the existing writers, each written AS the member so
cross-member isolation holds. Idempotent per fact (value in the dedup id), so an
unchanged re-submit is a NOOP and a changed value supersedes.

Insurance (health/term) and the gut-check -> risk_profile are intentionally NOT
persisted here yet (no clean target schema).
"""
from __future__ import annotations

from backend.agent.onboarding_persist import persist_member_data


def _read(tmp_memory, fname, member="vedant"):
    p = tmp_memory / "members" / member / fname
    return p.read_text() if p.exists() else ""


def test_persist_income_and_spend(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {
            "finances": {
                "incomes": [
                    {"key": "salary", "label": "Salary", "amount": 120000, "cadence": "monthly"}
                ],
                "spend": 50000,
            }
        },
        today="2026-06-14",
    )
    fin = _read(tmp_memory, "finances.md")
    assert "## income.salary" in fin
    assert "- value: 120000" in fin
    assert "- category: income" in fin
    assert "- cadence: monthly" in fin
    assert "## expense.total" in fin
    assert "- category: expense" in fin
    assert "- source: onboarding_form" in fin


def test_persist_loans_balance_and_emi(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {"finances": {"loans": [{"key": "home", "label": "Home", "emi": 40000, "remaining": 3500000}]}},
        today="2026-06-14",
    )
    fin = _read(tmp_memory, "finances.md")
    assert "## liability.home" in fin
    assert "- value: 3500000" in fin
    assert "## liability.home.emi" in fin
    assert "- value: 40000" in fin


def test_persist_assets_and_emergency_fund(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {"finances": {"assets": [{"key": "fd", "label": "FD", "amount": 200000}], "emergencyFund": 150000}},
        today="2026-06-14",
    )
    pf = _read(tmp_memory, "portfolio_summary.md")
    assert "## fd" in pf
    assert "- value: 200000" in pf
    assert "- asset_class: fd" in pf
    assert "## cash.emergency_fund" in pf
    assert "- value: 150000" in pf


def test_persist_goals_with_target(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {"goals": [{"id": "g1", "title": "House", "bucket": "long", "amount": 5000000, "notSure": False}]},
        today="2026-06-14",
    )
    g = _read(tmp_memory, "goals.md")
    assert "## House" in g
    assert "- target: 5000000" in g
    assert "- horizon: long" in g


def test_persist_dependents_support_amount(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {"supportMonthly": "20000"}, today="2026-06-14")
    fin = _read(tmp_memory, "finances.md")
    assert "## expense.dependents_support" in fin
    assert "- value: 20000" in fin


def test_empty_slice_writes_nothing(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {}, today="2026-06-14")
    assert _read(tmp_memory, "finances.md") == ""
    assert _read(tmp_memory, "portfolio_summary.md") == ""
    assert _read(tmp_memory, "goals.md") == ""


def test_blank_and_zero_amounts_skipped(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {
            "finances": {
                "incomes": [{"key": "salary", "label": "S", "amount": None, "cadence": "monthly"}],
                "assets": [{"key": "fd", "label": "FD", "amount": 0}],
            },
            "goals": [{"id": "g", "title": "", "bucket": "short"}],
        },
        today="2026-06-14",
    )
    assert _read(tmp_memory, "finances.md") == ""
    assert _read(tmp_memory, "portfolio_summary.md") == ""
    assert _read(tmp_memory, "goals.md") == ""


def test_unsure_goal_written_without_target(tmp_memory):
    persist_member_data(
        tmp_memory,
        "vedant",
        {"goals": [{"id": "g", "title": "Retire", "bucket": "long", "amount": 9000000, "notSure": True}]},
        today="2026-06-14",
    )
    g = _read(tmp_memory, "goals.md")
    assert "## Retire" in g
    assert "- target: 9000000" not in g


def test_idempotent_resubmit_is_noop(tmp_memory):
    slice_ = {"finances": {"incomes": [{"key": "salary", "label": "S", "amount": 100000, "cadence": "monthly"}]}}
    persist_member_data(tmp_memory, "vedant", slice_, today="2026-06-14")
    persist_member_data(tmp_memory, "vedant", slice_, today="2026-06-14")
    fin = _read(tmp_memory, "finances.md")
    assert fin.count("## income.salary") == 1


# --- Insurance -> profile.md (user decision: all insurance in profile) ---

def test_health_insurance_written_to_profile(tmp_memory):
    persist_member_data(
        tmp_memory, "vedant",
        {"finances": {"health": {"covered": True, "cover": 500000}}},
        today="2026-06-14",
    )
    prof = _read(tmp_memory, "profile.md")
    assert "## protection.health" in prof
    assert "- covered: yes" in prof
    assert "- cover: 500000" in prof


def test_term_insurance_not_covered_written_to_profile(tmp_memory):
    persist_member_data(
        tmp_memory, "vedant", {"finances": {"term": {"covered": False}}}, today="2026-06-14"
    )
    prof = _read(tmp_memory, "profile.md")
    assert "## protection.term" in prof
    assert "- covered: no" in prof


def test_insurance_untouched_writes_nothing(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {"finances": {}}, today="2026-06-14")
    assert "## protection." not in _read(tmp_memory, "profile.md")


# --- Gut-check -> risk_profile.md ---

def test_gut_check_high_tolerance_long_horizon(tmp_memory):
    persist_member_data(
        tmp_memory, "vedant",
        {"checks": {"answers": {"drop": "buy-more", "sure-or-flip": "flip", "reach": "fine"}}},
        today="2026-06-14",
    )
    risk = _read(tmp_memory, "risk_profile.md")
    assert "## risk_tolerance" in risk
    assert "- stance: high" in risk
    assert "## horizon" in risk
    assert "- stance: long" in risk
    assert "- source: onboarding_quiz" in risk


def test_gut_check_low_tolerance_short_horizon(tmp_memory):
    persist_member_data(
        tmp_memory, "vedant",
        {"checks": {"answers": {"drop": "take-out", "sure-or-flip": "sure", "reach": "no-way"}}},
        today="2026-06-14",
    )
    risk = _read(tmp_memory, "risk_profile.md")
    assert "- stance: low" in risk
    assert "- stance: short" in risk


def test_gut_check_moderate_tolerance(tmp_memory):
    # move-some (-1) + flip (+2) = +1 -> moderate
    persist_member_data(
        tmp_memory, "vedant",
        {"checks": {"answers": {"drop": "move-some", "sure-or-flip": "flip"}}},
        today="2026-06-14",
    )
    assert "- stance: moderate" in _read(tmp_memory, "risk_profile.md")


def test_gut_check_no_answers_writes_nothing(tmp_memory):
    persist_member_data(tmp_memory, "vedant", {"checks": {"answers": {}}}, today="2026-06-14")
    assert _read(tmp_memory, "risk_profile.md") == ""
