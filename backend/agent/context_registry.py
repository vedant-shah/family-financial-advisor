from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PreloadPolicy = Literal["always", "classifier_predicted", "agent_invoked"]


@dataclass(frozen=True)
class ContextEntry:
    name: str
    path_template: str
    description: str
    preload: PreloadPolicy
    scope: Literal["family", "member", "skill"]
    required: bool = False


REGISTRY: tuple[ContextEntry, ...] = (
    # --- always ---
    ContextEntry(
        name="family.household",
        path_template="memory/family/household.md",
        description="Joint accounts, shared expenses, family roster",
        preload="always",
        scope="family",
        required=True,
    ),
    ContextEntry(
        name="member.profile",
        path_template="memory/members/{member}/profile.md",
        description="Age, role, income, employment, retirement targets",
        preload="always",
        scope="member",
        required=True,
    ),
    ContextEntry(
        name="member.conversations",
        path_template="memory/members/{member}/conversations.md",
        description="Last 3-5 session summaries",
        preload="always",
        scope="member",
    ),
    ContextEntry(
        name="family.calendar",
        path_template="memory/family/calendar.md",
        description="Recurring events and future state changes",
        preload="always",
        scope="family",
    ),
    ContextEntry(
        name="skill.core_system",
        path_template="skills/core_system.md",
        description="Standing advisor instructions",
        preload="always",
        scope="skill",
        required=True,
    ),
    # --- classifier_predicted ---
    ContextEntry(
        name="member.portfolio_summary",
        path_template="memory/members/{member}/portfolio_summary.md",
        description="Investment and allocation questions",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.goals",
        path_template="memory/members/{member}/goals.md",
        description="Goal planning, surplus allocation",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.liabilities",
        path_template="memory/members/{member}/liabilities.md",
        description="Loan questions, debt management",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.risk_profile",
        path_template="memory/members/{member}/risk_profile.md",
        description="Allocation, investment recommendations",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.tax",
        path_template="memory/members/{member}/tax.md",
        description="80C/80D, ELSS, capital gains questions",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.insurance",
        path_template="memory/members/{member}/insurance.md",
        description="Coverage assessment",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="member.income_expenses",
        path_template="memory/members/{member}/income_expenses.md",
        description="Cash flow, savings rate questions",
        preload="classifier_predicted",
        scope="member",
    ),
    ContextEntry(
        name="family.inferences",
        path_template="memory/family/inferences.md",
        description="Cross-member financial observations (high confidence)",
        preload="classifier_predicted",
        scope="family",
    ),
    # --- agent_invoked ---
    ContextEntry(
        name="skill.surplus_allocation",
        path_template="skills/surplus_allocation.md",
        description="Deploying spare cash (FD vs MF, lump sum vs SIP decisions)",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="skill.emergency_response",
        path_template="skills/emergency_response.md",
        description="Sudden expense or financial shock",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="skill.goal_planning",
        path_template="skills/goal_planning.md",
        description="Setting or modifying a financial goal",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="skill.savings_strategy",
        path_template="skills/savings_strategy.md",
        description="Monthly cash flow, SIP setup, budget review",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="skill.financial_literacy",
        path_template="skills/financial_literacy.md",
        description="Definitions, concepts, financial education",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="skill.personal_finance",
        path_template="skills/personal_finance.md",
        description="Holistic review, multi-topic planning",
        preload="agent_invoked",
        scope="skill",
    ),
    ContextEntry(
        name="member.inferences",
        path_template="memory/members/{member}/inferences.md",
        description="Low-confidence member observations",
        preload="agent_invoked",
        scope="member",
    ),
    ContextEntry(
        name="member.agent_notes",
        path_template="memory/members/{member}/agent_notes.md",
        description="Prior agent reasoning, superseded recommendations",
        preload="agent_invoked",
        scope="member",
    ),
)

_BY_NAME: dict[str, ContextEntry] = {e.name: e for e in REGISTRY}


def entries_by_policy(policy: PreloadPolicy) -> list[ContextEntry]:
    return [e for e in REGISTRY if e.preload == policy]


def entry_by_name(name: str) -> ContextEntry | None:
    return _BY_NAME.get(name)


def resolve_path(entry: ContextEntry, member: str, project_root: Path) -> Path:
    path = entry.path_template.replace("{member}", member)
    return project_root / path
