import pytest

from app.prompts import MissingVariableError, extract_variables, render_template


def test_extract_variables_ordered_and_deduped():
    assert extract_variables("Hi {{name}}, about {{topic}} for {{name}}.") == ["name", "topic"]


def test_extract_variables_tolerates_inner_spaces_and_none():
    assert extract_variables("{{  a  }} and {{b}}") == ["a", "b"]
    assert extract_variables("no vars here") == []


def test_render_template_substitutes_all_occurrences():
    assert render_template("{{a}}-{{b}}-{{a}}", {"a": "1", "b": "2"}) == "1-2-1"


def test_render_template_stringifies_values():
    assert render_template("n={{n}}", {"n": 5}) == "n=5"


def test_render_template_missing_variable_raises_with_name():
    with pytest.raises(MissingVariableError) as ei:
        render_template("hi {{name}}", {})
    assert str(ei.value) == "name"


def test_render_template_leaves_single_braces_alone():
    assert render_template("a {b} c {{d}}", {"d": "x"}) == "a {b} c x"
