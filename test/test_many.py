"""Faz 15 -- several questions at once, and the ceiling that does not multiply.

The rule this file exists for is the one that cost a day in phase 8. Concurrency
was read at two levels with nothing tying them together, so the two multiplied:
six became thirty-six, the endpoint refused what it could not take, and the
refusals were counted as lines the tool had lost.

Phase 15 makes that mistake easy to repeat -- several files, several running
commands, each split into pieces -- so the ceiling stopped being arithmetic every
caller redoes and became a gate every ask goes through. What is measured here is
that it holds: not that the gate was called, but that at no instant were there
more requests in the air than the machine was told to allow.
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from sift import background, many, store, view
from sift.distill import View
from sift.model import Answer


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    yield
    for left in store.started():
        background.stop(left.handle)


class _Counting:
    """A model that reports the most requests that were ever in the air at once.

    It sleeps while it is "answering", which is what makes the measurement mean
    anything: without it every ask would finish before the next began and a
    broken ceiling would look exactly like a kept one.
    """

    def __init__(self) -> None:
        self.last_error: str | None = None
        self.now = 0
        self.most = 0
        self._lock = threading.Lock()

    def ask(self, system: str, user: str, *, max_tokens: int = 1024):
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
        try:
            time.sleep(0.05)
            return Answer(text="1", model="test-model", tries=1)
        finally:
            with self._lock:
                self.now -= 1


# -- the ceiling -------------------------------------------------------------


def test_asking_about_many_things_never_exceeds_the_one_ceiling(tmp_path, monkeypatch):
    """The phase 8 defect, turned into a guard.

    Six files asked about at once, each of which may itself be split. The number
    that matters is not how many jobs were started but how many requests existed
    at the same moment, and that number is the one the machine was given.
    """
    monkeypatch.setenv("SIFT_WORKERS", "2")
    judge = _Counting()
    monkeypatch.setattr(view, "Bridge", lambda: judge)

    paths = []
    for n in range(6):
        one = tmp_path / f"kayit{n}.log"
        one.write_text("bir\niki\nuc\n", encoding="utf-8")
        paths.append(str(one))

    got = view.best_digests(paths)

    assert len(got) == 6
    assert judge.most <= 2, f"{judge.most} requests were in the air at once, ceiling was 2"
    assert judge.most > 1, "nothing ran in parallel, so the ceiling was not what was measured"


def test_the_answers_come_back_in_the_order_they_were_asked():
    """Which job finishes first is a fact about the network, not about the answer.

    A result that reordered itself by timing would be a different answer to the
    same question every time it was asked.
    """
    def slow(n: int):
        def job() -> int:
            time.sleep(0.05 * (5 - n))
            return n

        return job

    assert many.together([slow(n) for n in range(5)]) == [0, 1, 2, 3, 4]


def test_one_job_is_run_without_a_pool():
    assert many.together([lambda: "tek"]) == ["tek"]
    assert many.together([]) == []


def test_a_job_that_raises_comes_back_out_rather_than_leaving_a_hole():
    def explode() -> None:
        raise RuntimeError("is patladi")

    with pytest.raises(RuntimeError):
        many.together([lambda: 1, explode])


# -- one file that cannot be read does not take the others with it -----------


def test_an_unreadable_file_says_so_in_its_own_place(tmp_path, monkeypatch):
    monkeypatch.setattr(view, "Bridge", lambda: _Counting())
    good = tmp_path / "var.log"
    good.write_text("bir\niki\n", encoding="utf-8")

    got = view.best_digests([str(good), str(tmp_path / "yok.log")])

    assert got[0][2] != "unreadable"
    assert "bir" in got[0][1].text
    assert got[1][2].startswith("unreadable")
    assert isinstance(got[1][1], View)


# -- waiting instead of asking again -----------------------------------------


def test_waiting_returns_as_soon_as_something_is_said():
    """An empty answer is a tool result that stays in the conversation for good.

    So a caller watching a build should be able to wait for it to speak rather
    than pay for five answers that say nothing has happened.
    """
    code = "import time; time.sleep(0.4); print('geldi', flush=True); time.sleep(30)"
    started = background.launch([sys.executable, "-c", code])

    began = time.monotonic()
    assert background.wait_for(started.handle, 15.0) is True
    assert time.monotonic() - began < 10, "it waited far longer than it needed to"
    assert background.unread(started.handle)[0] == ["geldi"]


def test_waiting_on_a_run_that_has_already_finished_does_not_wait():
    """There is nothing else coming, and the caller was told to wait ten seconds."""
    started = background.launch([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 15
    while store.load(started.handle) is None and time.monotonic() < deadline:
        time.sleep(0.05)

    background.seen(started.handle, background.unread(started.handle)[2])

    began = time.monotonic()
    assert background.wait_for(started.handle, 10.0) is False
    assert time.monotonic() - began < 5, "it waited for a command that had ended"
