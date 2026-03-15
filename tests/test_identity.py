"""Tests for the identity module."""

import pytest

from taskatlas._identity import make_id, validate_id


class TestMakeId:
    def test_goal_prefix(self):
        gid = make_id("g")
        assert gid.startswith("g-")
        assert len(gid) == 10  # "g-" + 8 hex chars

    def test_task_prefix(self):
        tid = make_id("t")
        assert tid.startswith("t-")
        assert len(tid) == 10

    def test_link_prefix(self):
        lid = make_id("lk")
        assert lid.startswith("lk-")
        assert len(lid) == 11

    def test_event_prefix(self):
        eid = make_id("ev")
        assert eid.startswith("ev-")
        assert len(eid) == 11

    def test_note_prefix(self):
        nid = make_id("n")
        assert nid.startswith("n-")
        assert len(nid) == 10

    def test_uniqueness(self):
        ids = {make_id("t") for _ in range(200)}
        assert len(ids) == 200

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="Invalid ID prefix"):
            make_id("bad")


class TestValidateId:
    def test_valid_goal_id(self):
        gid = make_id("g")
        assert validate_id(gid) == gid

    def test_valid_with_expected_prefix(self):
        gid = make_id("g")
        assert validate_id(gid, expected_prefix="g") == gid

    def test_wrong_expected_prefix(self):
        gid = make_id("g")
        with pytest.raises(ValueError, match="Expected prefix"):
            validate_id(gid, expected_prefix="t")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_id("")

    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            validate_id(123)  # type: ignore[arg-type]

    def test_no_dash_raises(self):
        with pytest.raises(ValueError, match="form"):
            validate_id("abc")

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError, match="Unknown ID prefix"):
            validate_id("zz-abcdef01")
