"""Faz 20 -- when a line is not a unit anybody can choose.

What is defended here is not that JSON is understood. It is narrower and it is
the only thing the rest of the tool rests on: a record shown to a reader is a
slice of the source, offset to offset, and never something rebuilt from a parsed
value. Everything else in this file is about when to reach for that unit and
when to leave the text as lines.
"""

from __future__ import annotations

import json

import pytest

from sift import digest as d
from sift import records
from test_distill import _Judge

# One line, four records. This is the shape the phase exists for: `lines.of`
# finds a single unit here, so a view of it is either nothing or all 262 bytes.
ONE_LINE = (
    '[{"id":1,"status":"ok"},{"id":2,"status":"ok"},'
    '{"id":3,"status":"failed","error":"connection refused"},'
    '{"id":4,"status":"ok"}]'
)


def test_a_single_line_array_has_records_where_it_has_no_lines():
    found = records.of(ONE_LINE)
    assert found is not None
    assert len(found) == 4
    assert found[2] == '{"id":3,"status":"failed","error":"connection refused"}'


def test_a_record_is_a_slice_of_the_source_and_not_a_value_written_back():
    """The first rule, in the one place a new unit could quietly break it.

    Re-serialising would be indistinguishable from working, most of the time.
    These three are the times it is not: an exponent comes back multiplied out,
    a float keeps a decimal point it never had, and keys come back sorted or not
    depending on a flag nobody set. Each of those is this tool writing text and
    calling it the file's own.
    """
    written = '[{"z":1, "a":2, "big":1E2, "round":1.0}, {"z":3, "a":4}]'
    found = records.of(written)
    assert found is not None
    assert found[0] == '{"z":1, "a":2, "big":1E2, "round":1.0}'
    assert found[0] != json.dumps(json.loads(found[0]))


def test_the_records_together_are_the_whole_array():
    """Nothing between them and nothing outside them, so a count of folded
    records is a count of the whole text rather than of a part of it."""
    found = records.of(ONE_LINE)
    assert found is not None
    rebuilt = "[" + ",".join(found) + "]"
    assert json.loads(rebuilt) == json.loads(ONE_LINE)


@pytest.mark.parametrize(
    ("written", "why"),
    [
        ("FAILED test_auth.py::test_expired_token - assert 401 == 200", "output"),
        ('{"results": [{"id": 1}, {"id": 2}]}', "an object wrapping one"),
        ("[]", "empty"),
        ('[{"id": 1}]', "one record is not a choice"),
        ('[{"id": 1}, {"id": 2}] and then some prose', "not a whole document"),
        ('[{"id": 1}, {"id": 2}', "never closed"),
        ('[{"id": 1}, {"id": 2},]', "a comma with nothing after it"),
        ("", "nothing at all"),
    ],
)
def test_what_is_left_as_lines(written, why):
    """Every one of these is answered "no" rather than raised over, because this
    is asked of every capture and almost none of them are a JSON array."""
    assert records.of(written) is None, why


def test_a_bracket_inside_a_string_does_not_end_a_record():
    """Why the standard decoder scans this and not a bracket counter.

    A log line inside a record is the ordinary case, not a corner one, and every
    counter written for this gets it wrong in the same way.
    """
    written = '[{"msg": "expected ] at end of [list], got }"}, {"msg": "fine"}]'
    found = records.of(written)
    assert found is not None
    assert len(found) == 2
    assert found[0] == '{"msg": "expected ] at end of [list], got }"}'


def test_a_view_of_an_array_counts_records_and_says_so(tmp_path):
    """The number in the footer and the number in the gap are the same number,
    and both of them say what they are counting."""
    path = tmp_path / "export.json"
    path.write_text(ONE_LINE, encoding="utf-8")

    built = d.digest(path, _Judge("3"))

    assert built is not None
    assert built.unit == "record"
    assert (built.kept, built.total) == (1, 4)
    assert '"error":"connection refused"' in built.text
    assert "records not shown" in built.text
    assert "lines not shown" not in built.text


def test_the_question_asked_about_a_list_is_not_the_question_asked_about_a_log(
    tmp_path,
):
    """A model told it is reading numbered lines will answer about lines. There
    are none here worth naming, and asking anyway is asking about a unit that
    does not exist."""
    path = tmp_path / "export.json"
    path.write_text(ONE_LINE, encoding="utf-8")

    judge = _Judge("1")
    d.digest(path, judge)

    asked = judge.seen[0][0]
    assert "records of a JSON array" in asked
    assert "numbered by line" not in asked


def test_a_log_is_still_read_as_lines(tmp_path):
    """The other half of the same rule: nothing here changes for a text that is
    not a list, and the unit it reports is the one it used."""
    path = tmp_path / "ci.log"
    path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    built = d.digest(path, _Judge("2"))

    assert built is not None
    assert built.unit == "line"
    assert built.total == 4
    assert "lines not shown" in built.text


def test_without_a_model_the_ends_of_a_list_are_records_too(tmp_path):
    """The safety net counts in whatever the text was made of. A fallback that
    silently went back to lines would show one unit and call it four."""
    path = tmp_path / "export.json"
    path.write_text(ONE_LINE, encoding="utf-8")

    built = d.ends_of(path)

    assert built.unit == "record"
    assert built.total == 4
