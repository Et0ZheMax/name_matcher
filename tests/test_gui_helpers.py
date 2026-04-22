from pathlib import Path

import pytest

from app.gui_helpers import make_default_output_path, parse_limit


def test_make_default_output_path() -> None:
    path = Path("/tmp/source/data.csv")
    assert make_default_output_path(path) == Path("/tmp/source/data_resolved.xlsx")


def test_parse_limit_empty_means_none() -> None:
    assert parse_limit("   ") is None


def test_parse_limit_positive_number() -> None:
    assert parse_limit("25") == 25


@pytest.mark.parametrize("value", ["0", "-2"])
def test_parse_limit_rejects_non_positive(value: str) -> None:
    with pytest.raises(ValueError):
        parse_limit(value)
