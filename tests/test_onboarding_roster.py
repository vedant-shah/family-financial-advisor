"""POST /api/onboarding/roster — persist the onboarding "who" phase.

The family roster the user builds in setup becomes the source of truth for who
exists: each member gets a directory + identity profile.md. The backend owns the
canonical member ids (slugify + dedup against existing dirs), so the picker
reflects onboarding output. Create-or-update only — never deletes. Identity only,
no money figures (those persist in a later round).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def _post(client, members):
    return client.post("/api/onboarding/roster", json={"members": members})


def test_roster_creates_dirs_and_profiles(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = _post(
            client,
            [
                {"name": "Asha", "relationship": "self", "isSelf": True},
                {"name": "Ravi", "relationship": "father", "isSelf": False},
            ],
        )
    assert resp.status_code == 200
    assert (tmp_memory / "members" / "asha" / "profile.md").is_file()
    assert (tmp_memory / "members" / "ravi" / "profile.md").is_file()
    assert "## identity.name" in (tmp_memory / "members" / "asha" / "profile.md").read_text()


def test_roster_returns_self_and_canonical_ids(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = _post(
            client,
            [
                {"name": "Asha", "relationship": "self", "isSelf": True},
                {"name": "Ravi", "relationship": "father", "isSelf": False},
            ],
        )
    body = resp.json()
    assert body["self"] == "asha"
    # Same order as request, each with its canonical id.
    assert [m["id"] for m in body["members"]] == ["asha", "ravi"]
    assert body["members"][0]["isSelf"] is True


def test_roster_maps_fields_and_writes_no_money(tmp_memory) -> None:
    with TestClient(app) as client:
        _post(
            client,
            [
                {
                    "name": "Asha",
                    "relationship": "self",
                    "isSelf": True,
                    "age": 30,
                    "earns": True,
                    "occupation": "Doctor",
                    "moneyComfort": "high",
                }
            ],
        )
    content = (tmp_memory / "members" / "asha" / "profile.md").read_text()
    assert "- age: 30" in content
    assert "- earning_status: earning" in content
    assert "- occupation: Doctor" in content
    assert "- financial_literacy: high" in content
    lower = content.lower()
    for forbidden in ("income", "salary", "loan", "amount"):
        assert forbidden not in lower


def test_roster_earns_false_maps_to_not_earning(tmp_memory) -> None:
    with TestClient(app) as client:
        _post(
            client,
            [{"name": "Ravi", "relationship": "self", "isSelf": True, "earns": False}],
        )
    content = (tmp_memory / "members" / "ravi" / "profile.md").read_text()
    assert "- earning_status: not_earning" in content


def test_roster_resubmit_is_idempotent(tmp_memory) -> None:
    members = [
        {"name": "Asha", "relationship": "self", "isSelf": True},
        {"name": "Ravi", "relationship": "father", "isSelf": False},
    ]
    with TestClient(app) as client:
        first = _post(client, members).json()
        # Client adopts canonical ids and resubmits them.
        with_ids = [
            {**m, "id": first["members"][i]["id"]} for i, m in enumerate(members)
        ]
        _post(client, with_ids)
    members_dir = tmp_memory / "members"
    # No duplicate dirs (fixture seeds vedant+mom; we added asha+ravi).
    assert sorted(d.name for d in members_dir.iterdir()) == [
        "asha", "mom", "ravi", "vedant",
    ]
    content = (members_dir / "asha" / "profile.md").read_text()
    assert content.count("## identity.name") == 1


def test_roster_rename_keeps_id_and_supersedes(tmp_memory) -> None:
    with TestClient(app) as client:
        first = _post(
            client, [{"name": "Asha", "relationship": "self", "isSelf": True}]
        ).json()
        sid = first["self"]
        _post(
            client,
            [{"id": sid, "name": "Asha Patel", "relationship": "self", "isSelf": True}],
        )
    # Same dir/id, name superseded in place.
    content = (tmp_memory / "members" / sid / "profile.md").read_text()
    assert "- name: Asha Patel" in content
    assert "- status: SUPERSEDED" in content


def test_roster_dedups_colliding_names(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = _post(
            client,
            [
                {"name": "Sam", "relationship": "self", "isSelf": True},
                {"name": "Sam", "relationship": "brother", "isSelf": False},
            ],
        )
    ids = [m["id"] for m in resp.json()["members"]]
    assert ids == ["sam", "sam-2"]


def test_roster_writes_household_members_table(tmp_memory) -> None:
    with TestClient(app) as client:
        _post(
            client,
            [
                {"name": "Asha", "relationship": "self", "isSelf": True, "earns": True},
                {"name": "Ravi", "relationship": "father", "isSelf": False, "earns": False},
            ],
        )
    household = (tmp_memory / "family" / "household.md").read_text()
    # The advisor reads household.md to answer "who is in my family", so every
    # roster member must appear with their name + relationship + earning status.
    assert "| asha | Asha | self | yes |" in household
    assert "| ravi | Ravi | father | no |" in household
    # No leftover placeholder rows from any prior template.
    assert "[member" not in household


def test_roster_household_reflects_latest_submission(tmp_memory) -> None:
    # Adding a member on resubmit rewrites the table; the client re-keys with the
    # canonical ids it adopted, so the existing member is not duplicated.
    with TestClient(app) as client:
        first = _post(
            client, [{"name": "Asha", "relationship": "self", "isSelf": True}]
        ).json()
        asha_id = first["self"]
        _post(
            client,
            [
                {"id": asha_id, "name": "Asha", "relationship": "self", "isSelf": True},
                {"name": "Ravi", "relationship": "brother", "isSelf": False},
            ],
        )
    household = (tmp_memory / "family" / "household.md").read_text()
    assert household.count("| asha |") == 1
    assert "| ravi |" in household


def test_roster_requires_exactly_one_self(tmp_memory) -> None:
    with TestClient(app) as client:
        zero = _post(
            client, [{"name": "Asha", "relationship": "father", "isSelf": False}]
        )
        two = _post(
            client,
            [
                {"name": "Asha", "relationship": "self", "isSelf": True},
                {"name": "Ravi", "relationship": "self", "isSelf": True},
            ],
        )
    assert zero.status_code == 400
    assert two.status_code == 400


def test_roster_rejects_invalid_provided_id(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = _post(
            client,
            [{"id": "../etc", "name": "Asha", "relationship": "self", "isSelf": True}],
        )
    assert resp.status_code == 400
