"""Faz 24 -- a machine nobody finished setting up.

There are three states here and only the middle one is new. Switched off on
purpose is a decision and is respected. A key the endpoint will not take, or an
endpoint that is down, is the third rule's territory and falls back to the ends
of the output. **No key at all** is neither: nothing works as advertised, and
until now the tool said so in five quiet words at the end of a footer.

For a person that is survivable -- they can see a view built out of the first
ten lines and the last forty and judge it. For a model it is not: it is handed a
short text with a footer it has no reason to distrust, and a quietly worse
answer is the one thing this project will not give a reader who cannot check it.

So the two callers are answered differently, and that difference is what is
defended here. The command line still runs the command, still returns the exit
code, and says loudly what it could not do. The server declines, says why, and
tells the caller to use its own shell -- which is not breaking its work, it is
getting out of the way of it.
"""

from __future__ import annotations

import inspect

import pytest

from sift import cli
from sift import server as s

SAY = "echo merhaba"


async def _said(call):
    """Whatever the tool answered, waited for if it needed waiting for.

    `run` is a coroutine because a command that takes ten minutes has to be able
    to say it is still going; the other six answer straight away. The list below
    is about what every tool does when nobody finished setting this up, and that
    question is the same for both kinds.
    """
    got = call()
    return await got if inspect.isawaitable(got) else got


@pytest.fixture(autouse=True)
def _unconfigured(monkeypatch):
    """A machine with no key and no switch: somebody who has not finished."""
    monkeypatch.delenv("SIFT_NO_MODEL", raising=False)


@pytest.mark.parametrize(
    ("call", "what"),
    [
        (lambda: s.run(SAY), "run"),
        (lambda: s.run(SAY, background=True), "run in the background"),
        (lambda: s.follow(), "follow"),
        (lambda: s.outline("README.md"), "outline"),
        (lambda: s.digest("README.md"), "digest"),
        (lambda: s.digest_many(["README.md"]), "digest_many"),
        (lambda: s.tool("loc"), "tool"),
    ],
)
async def test_every_tool_that_needs_a_model_declines(call, what):
    said = await _said(call)

    assert said == s.NO_KEY, f"{what} answered as though it were set up"


async def test_the_command_is_not_run_at_all(tmp_path):
    """Declining means declining. A tool that ran the command and then said it
    had not would be worse than either answer on its own."""
    proof = tmp_path / "ran"

    await s.run(f'touch "{proof}"')

    assert not proof.exists()


def test_what_it_says_is_what_somebody_can_act_on():
    """Three places a key can go, where to get one, and what to do instead in
    the meantime. A warning that does not say what to do is noise with a
    conscience."""
    said = s.NO_KEY

    assert "SIFT_API_KEY" in said
    assert "NVIDIA_API_KEY" in said
    assert "~/.config/nvidia/api_key" in said
    assert "build.nvidia.com" in said
    assert "your own shell tool" in said
    assert "SIFT_NO_MODEL" in said


def test_peek_still_works_because_it_never_needed_a_model(tmp_path):
    """The way back to the bytes is not part of the deal. It reads a file and
    prints it, and a machine with no key can still do that."""
    path = tmp_path / "ci.log"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    said = s.peek(str(path), first=1, last=1)

    assert "one" in said
    assert said != s.NO_KEY


async def test_switched_off_on_purpose_is_not_the_same_as_unset(monkeypatch):
    """`SIFT_NO_MODEL=1` is somebody's decision. The server keeps working, and
    nothing lectures them about a key they chose not to use."""
    monkeypatch.setenv("SIFT_NO_MODEL", "1")

    said = await s.run(SAY)

    assert said != s.NO_KEY
    assert "merhaba" in said


async def test_a_key_that_exists_is_enough_to_be_set_up(monkeypatch):
    """The gate asks whether one was ever provided, not whether it works. A key
    the endpoint refuses is the third rule's problem and falls back; refusing to
    start over it would be this tool deciding it knows better than the endpoint.
    """
    monkeypatch.setenv("SIFT_API_KEY", "not a real key")
    monkeypatch.setenv("SIFT_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SIFT_MODELS", "only-one")

    said = await s.run(SAY)

    assert said != s.NO_KEY
    assert "merhaba" in said


async def test_an_endpoint_of_your_own_is_enough_to_be_set_up(monkeypatch):
    """Somebody running their own model has finished setting this up.

    This gate exists because a machine with no key hands an agent a much worse
    view that looks exactly like a good one. A machine pointed at a local model
    is not that machine: it has somewhere to ask, and what that endpoint wants
    for credentials is between the two of them.
    """
    monkeypatch.setenv("SIFT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("SIFT_MODELS", "qwen3:8b")

    said = await s.run(SAY)

    assert said != s.NO_KEY
    assert "merhaba" in said


def test_the_banner_is_not_printed_to_somebody_running_their_own_model(
    capsys, monkeypatch
):
    """And the command line does not send them after a key they do not need."""
    monkeypatch.setenv("SIFT_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("SIFT_MODELS", "only-one")

    assert cli.main(["run", "--", "echo", "merhaba"]) == 0

    said = capsys.readouterr()
    assert "no API key" not in said.err
    assert "merhaba" in said.out, "ucuncu kural: komut yine calisir"


# -- the other caller, who can see what they were given ----------------------


def test_the_command_line_still_runs_the_command_and_says_what_it_could_not_do(
    capsys,
):
    """The third rule, unmoved. The banner is loud and it is only a banner."""
    assert cli.main(["run", "--", "echo", "merhaba"]) == 0

    said = capsys.readouterr()
    assert "merhaba" in said.out, "the command's own output is not negotiable"
    assert "no API key" in said.err
    assert "build.nvidia.com" in said.err


def test_the_banner_is_on_the_error_stream_and_not_in_the_view(capsys):
    """A view is what somebody pipes somewhere. A warning inside one is a line
    that was never in their output."""
    cli.main(["run", "--", "echo", "merhaba"])

    said = capsys.readouterr()
    assert "no API key" not in said.out


def test_nothing_is_said_about_a_key_that_was_never_going_to_be_used(capsys):
    """`peek`, `list` and `stats` answer out of what is already on disk."""
    cli.main(["run", "--", "echo", "merhaba"])
    capsys.readouterr()

    cli.main(["list"])
    cli.main(["stats"])

    assert "no API key" not in capsys.readouterr().err


def test_a_decision_is_not_nagged_about(capsys, monkeypatch):
    monkeypatch.setenv("SIFT_NO_MODEL", "1")

    cli.main(["run", "--", "echo", "merhaba"])

    said = capsys.readouterr()
    assert "merhaba" in said.out
    assert "no API key" not in said.err
