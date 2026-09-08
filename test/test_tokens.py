"""Faz 23 -- what the report counts, and what it refuses to count.

`stats` answers the question somebody installing this actually has: is it worth
the requests it spends? It could not answer it in bytes, because bytes are not
what a request is billed in and not what a context window holds.

The whole of this phase is that the new number is **measured** rather than
estimated. What is defended here is mostly the refusal: a run nobody counted
stays uncounted and says so, instead of being filled in with bytes divided by
four -- which is a rule of thumb about English prose, and this tool is pointed
at Japanese, at base64 and at stack traces.
"""

from __future__ import annotations

import json

import pytest

from sift import cli, distill, model, store, view
from sift import digest as d
from test_distill import _Judge

LOG = "".join(f"line {n}\n" for n in range(1, 41))


@pytest.fixture
def kayit(tmp_path):
    path = tmp_path / "ci.log"
    path.write_text(LOG, encoding="utf-8")
    return path


def _reply(**usage) -> bytes:
    body = {"choices": [{"message": {"content": "3"}}]}
    if usage:
        body["usage"] = usage
    return json.dumps(body).encode("utf-8")


def test_what_the_endpoint_counted_is_what_is_recorded():
    assert (
        model._spent(_reply(prompt_tokens=900, completion_tokens=12, total_tokens=912)) == 912
    )


@pytest.mark.parametrize(
    ("body", "why"),
    [
        (_reply(), "no usage in the reply"),
        (b'{"usage": {"total_tokens": "many"}}', "a count that is not a number"),
        (b'{"usage": null}', "usage that is not an object"),
        (b"not json at all", "a body that is not a reply"),
        (b'{"usage": {"total_tokens": -5}}', "a count below zero"),
    ],
)
def test_a_reply_that_did_not_say_costs_zero_rather_than_a_guess(body, why):
    """Zero means nobody counted. It is not a failure and it is not filled in."""
    assert model._spent(body) == 0, why


def test_the_cost_of_every_ask_reaches_the_view(kayit):
    built = d.digest(kayit, _Judge("3", tokens=250))

    assert built is not None
    assert built.asks == 1
    assert built.tokens == 250


def test_narrowing_costs_are_counted_too(kayit):
    """A second pass is a second request. A report that counted only the first
    would understate the tool exactly when it was working hardest."""
    every = ", ".join(str(n) for n in range(1, 41))
    judge = _Judge(every, "3", tokens=100)

    built = distill.select(LOG.splitlines(), "which lines?", "h", judge, budget=2)

    assert built is not None
    assert built.asks > 1, "this text was supposed to need narrowing"
    assert built.tokens == 100 * built.asks


def test_a_remembered_answer_costs_nothing_and_says_zero(kayit, monkeypatch):
    monkeypatch.setenv("SIFT_CACHE", "1")
    judge = _Judge("3", tokens=250)

    first = d.digest(kayit, judge)
    second = d.digest(kayit, judge)

    assert first is not None and second is not None
    assert (first.tokens, second.tokens) == (250, 0)


def test_a_view_nobody_could_ask_about_costs_nothing(kayit):
    """No key, no network, no answer: the fallback is free and says so."""
    built = d.ends_of(kayit)
    assert built.tokens == 0


def _recorded(handle: str, tokens: int) -> None:
    """A finished capture with a view already measured, written straight to disk."""
    store.begin(handle)
    store.record(
        store.Saving(
            handle=handle,
            raw_bytes=10_000,
            shown_bytes=500,
            kept=5,
            total=100,
            model="test-model",
            asks=1,
            tokens=tokens,
        )
    )
    store.finish(
        store.Meta(
            handle=handle,
            command=["pytest"],
            shell=False,
            exit_code=0,
            timed_out=False,
            started_at=store.now(),
            duration_s=1.0,
            byte_count=10_000,
            cwd="/tmp",
        )
    )


def test_the_report_prints_what_was_counted(capsys):
    _recorded("aaaa1111", tokens=1_234)

    assert cli.main(["stats"]) == 0

    said = capsys.readouterr().out
    assert "tokens" in said
    assert "1,234" in said
    assert "as the endpoint counted them" in said


def test_a_run_nobody_counted_is_left_out_and_said_so(capsys):
    _recorded("aaaa1111", tokens=1_000)
    _recorded("bbbb2222", tokens=0)

    assert cli.main(["stats"]) == 0

    said = capsys.readouterr().out
    assert "1 not counted" in said
    assert "—" in said, "an uncounted run is a dash, not a number nobody measured"


def test_a_report_written_before_this_field_existed_still_loads():
    """The field is defaulted, so an old `view.json` reads as what it was: a run
    from before anybody was counting."""
    store.begin("aaaa1111")
    store.view_path("aaaa1111").write_text(
        json.dumps(
            {
                "handle": "aaaa1111",
                "raw_bytes": 10,
                "shown_bytes": 5,
                "kept": 1,
                "total": 2,
                "model": "old",
                "asks": 1,
            }
        ),
        encoding="utf-8",
    )

    found = store.load_saving("aaaa1111")

    assert found is not None
    assert found.tokens == 0


def test_the_footer_is_untouched_by_any_of_this(kayit):
    """The cost belongs in the report, not in every view. A footer is read by
    somebody looking at their own output, and what a request cost is not what
    they are looking at."""
    built = d.digest(kayit, _Judge("3", tokens=250))

    assert built is not None
    assert "250" not in view.outline_footer(str(kayit), built, "test-model")
