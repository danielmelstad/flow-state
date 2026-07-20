import pytest

from example_service import slugify


def test_basic_text_becomes_hyphenated_lowercase():
    assert slugify("Hello, World!") == "hello-world"


def test_accents_are_stripped():
    assert slugify("Þórsmörk café") == "orsmork-cafe"


def test_truncation_never_leaves_trailing_hyphen():
    assert slugify("alpha beta gamma", max_length=11) == "alpha-beta"


def test_max_length_must_be_positive():
    with pytest.raises(ValueError):
        slugify("anything", max_length=0)
