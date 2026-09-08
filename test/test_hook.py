"""Faz 18 -- the shell commands a client runs on its own.

What is defended here is not the client's protocol, which is theirs to change.
It is this project's own rules about the gate: that it routes everything rather
than guessing which commands are worth catching, and that every way of going
wrong ends with the shell working exactly as it would have.
"""

from __future__ import annotations

import pytest

from sift import hook


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_HOOK"):
        monkeypatch.delenv(name, raising=False)


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _said(answer: dict) -> str:
    return answer["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_shell_command_is_run_here_and_comes_back_as_a_view():
    got = hook.answer(_bash("echo merhaba"))

    assert "merhaba" in _said(got)
    assert "sift " in _said(got), "the footer says which capture this was"


def test_everything_is_routed_and_nothing_decides_what_looks_noisy():
    """The rule this file exists to keep.

    A list of commands worth catching would know `pytest` and be wrong about the
    in-house script, and it cannot be right in principle: how much a command
    prints is not knowable before it runs. So a one-line command is routed too,
    and costs nothing -- a view of twelve lines is twelve lines.
    """
    got = hook.answer(_bash("echo tek"))

    assert got != {}, "a short command was quietly let through"
    assert "tek" in _said(got)


def test_a_tool_that_is_not_a_shell_is_left_alone():
    assert hook.answer({"tool_name": "Read", "tool_input": {"file_path": "x"}}) == {}


def test_an_event_of_a_shape_nobody_expected_is_carried_on_from():
    for odd in ({}, {"tool_name": "Bash"}, {"tool_name": "Bash", "tool_input": None},
                {"tool_name": "Bash", "tool_input": {"command": "   "}}, "not a dict"):
        assert hook.answer(odd) == {}, f"{odd!r} should have been carried on from"


def test_a_bug_underneath_leaves_the_shell_exactly_as_it_was(monkeypatch):
    """The third rule, in the one place where breaking it breaks the whole client."""
    def explode(*args, **kwargs):
        raise RuntimeError("kirildi")

    monkeypatch.setattr(hook, "run", explode)

    assert hook.answer(_bash("echo merhaba")) == {}


def test_the_gate_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("SIFT_HOOK", "0")
    assert hook.answer(_bash("echo merhaba")) == {}
