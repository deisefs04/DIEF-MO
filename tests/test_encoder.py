import pytest

from dief_mo.encoder import generate_id, decode_id, validate_code


def test_generate_basic():
    assert generate_id("E001", "PRO", "M001", 1) == "E001_PRO_M001_001"


def test_generate_pads_sequence():
    assert generate_id("E001", "PRO", "M001", 42) == "E001_PRO_M001_042"


def test_generate_rejects_empty():
    with pytest.raises(ValueError):
        generate_id("", "PRO", "M001", 1)


def test_generate_rejects_zero_seq():
    with pytest.raises(ValueError):
        generate_id("E001", "PRO", "M001", 0)


def test_generate_rejects_underscore_in_code():
    # underscore is the separator and must never appear inside a code part
    with pytest.raises(ValueError):
        generate_id("E001", "P_RO", "M001", 1)


def test_generate_rejects_space_in_code():
    with pytest.raises(ValueError):
        generate_id("E001", "PR O", "M001", 1)


def test_validate_code_trims():
    assert validate_code("  PRO  ", "area") == "PRO"


def test_decode_roundtrip():
    parts = decode_id("E001_PRO_M001_007")
    assert parts == {"experiment": "E001", "area": "PRO", "matrix": "M001", "seq": 7}


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_id("not-an-id")