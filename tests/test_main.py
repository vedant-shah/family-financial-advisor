"""Tests for member-id validation in backend.main.

`_validate_member_id` guards every place a member id is used as a path
segment under memory/ and sessions/, so a crafted X-Member-Id (e.g. containing
"../") is rejected with 400 before it reaches any filesystem lookup.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import _assert_member_exists, _validate_member_id, app

INVALID_MEMBER_IDS = [
    "../etc",
    "../../etc/passwd",
    "a/b",
    "UPPER",
    "",
    "a" * 65,
    "vedant ",
    "vedant.json",
]


@pytest.mark.parametrize("member", ["vedant", "mom", "a", "a-b_c", "a" * 64])
def test_validate_member_id_accepts_valid_slugs(member: str) -> None:
    _validate_member_id(member)  # should not raise


@pytest.mark.parametrize("member", INVALID_MEMBER_IDS)
def test_validate_member_id_rejects_invalid_slugs(member: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_member_id(member)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("member", ["../etc", "a/b", ""])
def test_assert_member_exists_rejects_traversal_before_dir_check(
    member: str, tmp_memory
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _assert_member_exists(member)
    assert exc_info.value.status_code == 400


def test_api_history_rejects_invalid_member_id(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = client.get("/api/history", headers={"X-Member-Id": "../etc"})
    assert resp.status_code == 400


def test_session_close_rejects_invalid_member_id(tmp_memory) -> None:
    with TestClient(app) as client:
        resp = client.post("/session/close", json={"member": "../etc"})
    assert resp.status_code == 400
