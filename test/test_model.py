"""Faz 2 -- the model is asked well, and its absence is never an error."""

from __future__ import annotations

import json
import os

import pytest

from sift import model as m
from sift.model import Bridge, Reply

# Read before any fixture moves it, so the live test below can find the key
# where the person running it actually keeps it.
_REAL_HOME = os.environ.get("HOME", "")

# Written out rather than read from the code, so that reordering the ladder
# cannot quietly reorder what the tests expect of it.
FLAGSHIP = "nvidia/nemotron-3-ultra-550b-a55b"


@pytest.fixture(autouse=True)
def _no_real_key(tmp_path, monkeypatch):
    """No test may find the machine's real key, or its real network.

    `HOME` is moved as well, because the key file is looked up through it and a
    test that quietly picked up a working key would be testing the machine
    rather than the code.
    """
    # This file is about the asking itself, so the switch that stops it comes
    # back off -- `conftest.py` sets it for everything else, which runs without
    # a model on purpose and should say so rather than look unconfigured.
    monkeypatch.delenv("SIFT_NO_MODEL", raising=False)
    for name in (*m.KEY_VARIABLES, "SIFT_MODELS", "SIFT_BASE_URL", "SIFT_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    # `HOME` alone moves `~` on Linux and macOS and not on Windows, where
    # `Path.home()` reads `USERPROFILE`. A file-backed key test that set only
    # `HOME` wrote its key somewhere `find_key` was never going to look.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)
    return tmp_path


class _Fake:
    """A transport with its answers written in advance, and a memory of the asks."""

    def __init__(self, *replies: Reply | Exception) -> None:
        self.replies = list(replies)
        self.asked: list[dict] = []
        self.slept: list[float] = []
        # What each ask was given to wait. The two passes differ in nothing else,
        # so this is how a test tells them apart.
        self.waited: list[float] = []

    def __call__(self, *, url: str, headers: dict, body: bytes, timeout: float) -> Reply:
        self.asked.append(json.loads(body))
        self.waited.append(timeout)
        assert self.replies, "transport asked more often than it was prepared for"
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def models(self) -> list[str]:
        return [ask["model"] for ask in self.asked]


def _ok(text: str = "8-14, 220") -> Reply:
    return Reply(200, json.dumps({"choices": [{"message": {"content": text}}]}).encode())


def _bridge(fake: _Fake, **kwargs) -> Bridge:
    kwargs.setdefault("api_key", "nvapi-sahte")
    return Bridge(transport=fake, sleep=fake.slept.append, **kwargs)


def test_without_a_key_nothing_is_sent_and_nothing_is_raised():
    """The tool runs commands for people who have never heard of an API key."""
    fake = _Fake(_ok())
    bridge = Bridge(transport=fake, api_key="")
    assert not bridge.available
    assert bridge.ask("sistem", "kullanici") is None
    assert fake.asked == [], "anahtar yokken ag uzerinden bir sey gitmemeli"
    assert bridge.last_error == "no api key"


def _size_word(model: str) -> str:
    """How big a rung says it is. Nemotron model ids carry the word."""
    for word in ("ultra", "super", "lightning", "nano"):
        if word in model:
            return word
    return model


def test_the_ladder_is_ordered_by_what_answers_and_not_by_size():
    """The rule Faz 26 replaced, and why it was replaced.

    The ladder used to run largest first, and that reads like the obvious
    design: ask the best judgement, fall to a smaller one when it is busy.
    Measured on 2026-09-08 against the free tier, the flagship holds a request
    in a queue for 107-124 seconds before it answers or refuses -- on two
    independent providers, so the wait belongs to the model rather than to one
    endpoint's mood. `super` answers the same question in about six seconds.

    Keeping the flagship first cost 181.5 seconds of every distillation and
    bought nothing: two timeouts, then the fall to the rung that was going to
    answer anyway. So the order is a measurement now, and the intent is written
    out here rather than checked against the list -- largest is no longer the
    rule, *answers* is.
    """
    assert FLAGSHIP not in m.DEFAULT_LADDER, "the flagship queues; it is not a rung"
    assert [_size_word(name) for name in m.DEFAULT_LADDER] == ["super", "lightning"]


def test_the_flagship_can_still_be_asked_for_by_name():
    """Left out is not shut out. Somebody who will wait two minutes for it says
    so, and nothing here argues."""
    fake = _Fake(_ok())
    bridge = _bridge(fake, ladder=(FLAGSHIP,))
    answer = bridge.ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == FLAGSHIP


def test_the_first_rung_is_asked_first():
    """Whatever the ladder is, the walk starts at the top of it."""
    fake = _Fake(_ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0]
    assert answer.tries == 1
    assert fake.models == [m.DEFAULT_LADDER[0]]


def test_a_busy_rung_is_tried_again_before_it_is_left_behind():
    """Busy is a moment, not a verdict; the flagship deserves a second ask."""
    fake = _Fake(Reply(503, b""), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0], "ayni basamak tekrar denenmeliydi"
    assert answer.tries == 2
    assert fake.slept == [pytest.approx(1.5)]


def test_a_rung_that_stays_busy_hands_the_question_down():
    fake = _Fake(Reply(503, b""), Reply(503, b""), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[1]
    assert fake.models == [m.DEFAULT_LADDER[0], m.DEFAULT_LADDER[0], m.DEFAULT_LADDER[1]]


def test_a_rung_that_ran_out_of_time_is_not_asked_again():
    """The other half of Faz 26, and the more expensive half.

    A busy rung refuses in a moment, so asking again is cheap and often works.
    A rung that ran out of time did not refuse -- it is queued, and the queue is
    longer than the wait. Asking the same rung again joins the same queue again:
    a second full timeout to be told the same thing. Measured, that was 181.5
    seconds of every distillation.

    So the two are told apart here, and only the cheap one is repeated.
    """
    fake = _Fake(TimeoutError("the read operation timed out"), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")

    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[1], "beklemek bir kez odenir, iki kez degil"
    assert fake.models == [m.DEFAULT_LADDER[0], m.DEFAULT_LADDER[1]]
    assert fake.slept == [], "zaman asiminin ustune bir de beklenmez"


def test_a_refusal_that_arrives_quickly_is_still_worth_repeating():
    """Faz 26 narrows the retry; it does not remove it."""
    fake = _Fake(Reply(503, b""), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")

    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0]
    assert fake.slept == [pytest.approx(1.5)]


def test_nothing_is_said_about_effort_unless_somebody_asks(monkeypatch):
    monkeypatch.delenv("SIFT_EFFORT", raising=False)
    fake = _Fake(_ok())
    _bridge(fake).ask("sistem", "kullanici")

    assert "reasoning_effort" not in fake.asked[0]


def test_the_effort_somebody_asked_for_is_what_is_sent(monkeypatch):
    """Measured: this model wrote 924 tokens of reasoning to produce a
    twelve-token answer, and the caller waited 15.3 seconds for it. At `low` the
    same question took 2.4 seconds -- and lost 7.8% of the lines a reader could
    not do without, which is why it is a setting and not the default."""
    monkeypatch.setenv("SIFT_EFFORT", "low")
    fake = _Fake(_ok())
    _bridge(fake).ask("sistem", "kullanici")

    assert fake.asked[0]["reasoning_effort"] == "low"


def test_an_endpoint_that_will_not_take_the_effort_field_is_asked_without_it(
    monkeypatch,
):
    """The field is this tool's idea, not the caller's question.

    Not every endpoint speaking this shape knows `reasoning_effort`, and one
    that rejects it must cost a repeat rather than an answer -- a speed setting
    that turns into silence is worse than no setting.
    """
    monkeypatch.setenv("SIFT_EFFORT", "low")
    fake = _Fake(Reply(400, b"unknown field: reasoning_effort"), _ok())

    answer = _bridge(fake).ask("sistem", "kullanici")

    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0], "ayni basamak, sadece alansiz"
    assert "reasoning_effort" in fake.asked[0]
    assert "reasoning_effort" not in fake.asked[1]


def test_it_is_dropped_once_and_not_argued_about(monkeypatch):
    """Refused again without the field means the field was never the problem."""
    monkeypatch.setenv("SIFT_EFFORT", "low")
    fake = _Fake(Reply(400, b""), Reply(400, b""), _ok())

    answer = _bridge(fake).ask("sistem", "kullanici")

    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[1], "ikinci retten sonra alt basamak"


def test_a_ladder_that_ran_out_of_time_is_walked_again_more_slowly():
    """The second option, and the reason the first one is allowed to be brief.

    "Nobody answered in twenty-five seconds" is not "nobody was going to".
    Measured, a queued rung clears at 107-124 seconds. So the quick pass is
    tried on every rung first, and only when all of them ran out of time is the
    same ladder walked again with patience -- which costs nothing on a day when
    the quick pass answers, because then it never happens.
    """
    fake = _Fake(
        TimeoutError("timed out"),  # quick pass, first rung
        TimeoutError("timed out"),  # quick pass, second rung
        _ok(),  # patient pass, first rung
    )
    bridge = _bridge(fake, timeout=25.0, patience=150.0)

    answer = bridge.ask("sistem", "kullanici")

    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0]
    assert fake.waited == [25.0, 25.0, 150.0], "once cabuk, sonra sabirli"


def test_patience_is_spent_on_a_queue_and_on_nothing_else():
    """A refusal is not a queue. Waiting longer cannot turn a 404 into a model."""
    fake = _Fake(*[Reply(404, b"no such model") for _ in range(len(m.DEFAULT_LADDER))])
    bridge = _bridge(fake, timeout=25.0, patience=150.0)

    assert bridge.ask("sistem", "kullanici") is None
    assert 150.0 not in fake.waited, "reddedilen bir istek icin beklenmez"


def test_a_dead_key_is_not_offered_to_every_rung_twice():
    """The one refusal that ends the walk should not begin a second one."""
    fake = _Fake(Reply(401, b"unauthorized"))
    bridge = _bridge(fake, timeout=25.0, patience=150.0)

    assert bridge.ask("sistem", "kullanici") is None
    assert len(fake.asked) == 1


def test_patience_can_be_switched_off(monkeypatch):
    """For a caller who would rather have a quick no than a slow yes."""
    monkeypatch.setenv("SIFT_PATIENCE", "0")
    fake = _Fake(*[TimeoutError("timed out") for _ in range(len(m.DEFAULT_LADDER))])
    bridge = _bridge(fake)

    assert bridge.ask("sistem", "kullanici") is None
    assert set(fake.waited) == {bridge.timeout}, "tek tur, tek zaman asimi"


def test_what_went_wrong_in_both_passes_is_said():
    """A view built without a model says why. With two passes there are two
    reasons, and the second one alone would read as though the first never
    happened."""
    fake = _Fake(
        *[TimeoutError("timed out") for _ in range(len(m.DEFAULT_LADDER))],
        *[Reply(503, b"") for _ in range(len(m.DEFAULT_LADDER) * m._TRIES_PER_RUNG)],
    )
    bridge = _bridge(fake, timeout=25.0, patience=150.0)

    assert bridge.ask("sistem", "kullanici") is None
    assert "no answer in 25s" in (bridge.last_error or "")
    assert "then 150s" in (bridge.last_error or "")


def test_a_rejected_key_ends_the_walk_at_once():
    """A smaller model will refuse the same key just as firmly.

    Walking the rest of the ladder would spend the user's time to arrive at the
    same answer, and would put a dead key in front of three services instead of
    one.
    """
    fake = _Fake(Reply(401, b"unauthorized"))
    bridge = _bridge(fake)
    assert bridge.ask("sistem", "kullanici") is None
    assert len(fake.asked) == 1
    assert "key rejected" in (bridge.last_error or "")


def test_every_rung_busy_is_an_empty_answer_rather_than_an_error():
    kere = len(m.DEFAULT_LADDER) * m._TRIES_PER_RUNG
    fake = _Fake(*[Reply(503, b"") for _ in range(kere)])
    bridge = _bridge(fake)
    assert bridge.ask("sistem", "kullanici") is None
    assert len(fake.asked) == kere, "her basamak ikiser kez denenmeli"
    assert "503" in (bridge.last_error or "")


def test_an_endpoint_that_cannot_be_reached_counts_as_busy():
    """No network is the commonest failure of all, and the least worth shouting about.

    It must not cost the flagship either: a blip in the connection says nothing
    about the model at the top of the ladder, so the next ask goes to it again
    rather than to a smaller one.
    """
    fake = _Fake(Reply(0, b"name resolution failed"), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[0], "ag kesintisi en iyi modele mal olmamali"


def test_a_transport_that_raises_does_not_reach_the_caller():
    fake = _Fake(OSError("baglanti koptu"), _ok())
    bridge = _bridge(fake)
    answer = bridge.ask("sistem", "kullanici")
    assert answer is not None
    assert answer.tries == 2


def test_a_reply_that_cannot_be_read_is_taken_to_the_next_rung():
    """Repeating the question word for word would only be phrased badly again."""
    fake = _Fake(Reply(200, b"bu json degil"), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[1]
    assert len(fake.asked) == 2, "okunamayan cevap ayni basamakta tekrarlanmamali"


def test_an_empty_answer_is_not_an_answer():
    """Acting on silence dressed up as a decision is worse than having no model."""
    fake = _Fake(_ok("   \n  "), _ok("8-14"))
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.text == "8-14"
    assert answer.model == m.DEFAULT_LADDER[1]


def test_a_refusal_is_not_repeated_to_the_model_that_refused():
    fake = _Fake(Reply(404, b"no such model"), _ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == m.DEFAULT_LADDER[1]
    assert len(fake.asked) == 2


def test_only_the_prompt_leaves_this_machine():
    """Whatever is sent has to be something the caller chose to send.

    The masking that decides what is safe to put in a prompt belongs to the
    caller. This test exists so that nothing else can be added here quietly --
    no paths, no environment, no identity gathered on the side.
    """
    fake = _Fake(_ok())
    _bridge(fake).ask("yalniz numara ver", "1| merhaba\n2| dunya")
    (sent,) = fake.asked
    assert set(sent) == {"model", "messages", "temperature", "max_tokens", "stream"}
    assert sent["messages"] == [
        {"role": "system", "content": "yalniz numara ver"},
        {"role": "user", "content": "1| merhaba\n2| dunya"},
    ]


def test_the_key_is_read_from_the_file_when_the_environment_is_silent(tmp_path):
    key_file = tmp_path / ".config" / "nvidia" / "api_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text("nvapi-dosyadan\n", encoding="utf-8")
    assert m.find_key() == "nvapi-dosyadan"


def test_the_environment_beats_the_file(tmp_path, monkeypatch):
    """A shell can override the stored key for one command without editing anything."""
    key_file = tmp_path / ".config" / "nvidia" / "api_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text("nvapi-dosyadan", encoding="utf-8")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-ortamdan")
    assert m.find_key() == "nvapi-ortamdan"


def test_a_missing_key_file_is_simply_no_key():
    assert m.find_key() is None


def test_the_ladder_can_be_replaced_from_the_environment(monkeypatch):
    monkeypatch.setenv("SIFT_MODELS", " ilki , ikincisi ,, ")
    assert m.default_ladder() == ("ilki", "ikincisi")


def test_an_unreadable_timeout_falls_back_instead_of_failing(monkeypatch):
    monkeypatch.setenv("SIFT_TIMEOUT", "cok uzun")
    assert Bridge(api_key="x").timeout == m._DEFAULT_TIMEOUT


@pytest.mark.skipif(
    os.environ.get("SIFT_LIVE") != "1",
    reason="gercek NVIDIA cagrisi: SIFT_LIVE=1 ile calistir",
)
def test_the_bridge_really_reaches_nvidia(monkeypatch):
    """The one test that proves the shape above matches the service it describes.

    Kept out of the ordinary run because it needs a key and a network, and a
    suite that fails when the wifi drops teaches people to ignore it.
    """
    monkeypatch.setenv("HOME", _REAL_HOME)
    bridge = Bridge()
    if not bridge.available:
        pytest.skip("anahtar yok")
    answer = bridge.ask("Yalnizca istenen kelimeyi yaz.", "TAMAM yaz.")
    assert answer is not None, bridge.last_error
    assert "TAMAM" in answer.text.upper()
