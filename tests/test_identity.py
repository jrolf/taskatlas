"""Tests for prefixed identity generation and validation."""

import pytest

from taskatlas._identity import make_id, validate_id


class TestMakeId:
    def test_all_entity_prefixes(self):
        for prefix in ("d", "g", "t", "lk", "ev", "n"):
            generated = make_id(prefix)
            assert generated.startswith(f"{prefix}-")
            assert validate_id(generated, expected_prefix=prefix) == generated

    def test_collision_avoidance_against_existing_set(self):
        first = make_id("t")
        second = make_id("t", existing={first})
        assert second != first

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="Invalid ID prefix"):
            make_id("bad")


class TestValidateId:
    def test_wrong_expected_prefix_raises(self):
        did = make_id("d")
        with pytest.raises(ValueError, match="Expected prefix"):
            validate_id(did, expected_prefix="g")

    def test_malformed_ids_raise(self):
        for bad in ("", None, 123, "nodash", "d-", "zz-12345678"):
            with pytest.raises(ValueError):
                validate_id(bad)
