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
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


class _Fake:
    """A transport with its answers written in advance, and a memory of the asks."""

    def __init__(self, *replies: Reply | Exception) -> None:
        self.replies = list(replies)
        self.asked: list[dict] = []
        self.slept: list[float] = []

    def __call__(self, *, url: str, headers: dict, body: bytes, timeout: float) -> Reply:
        self.asked.append(json.loads(body))
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


def test_the_ladder_runs_from_the_largest_model_down():
    """Order is the design here, and it cannot be checked against itself.

    Asking whether the first rung equals `DEFAULT_LADDER[0]` asks the code
    whether it agrees with itself: reorder the list and the expectation
    reorders with it. The intent has to be written out instead -- largest
    first, and every step down the ladder a step down in size.
    """
    assert [_size_word(name) for name in m.DEFAULT_LADDER] == [
        "ultra",
        "super",
        "lightning",
    ]
    assert m.DEFAULT_LADDER[0] == FLAGSHIP


def test_the_largest_model_is_asked_first():
    """The ladder is ordered by judgement, and the best judgement is asked for first."""
    fake = _Fake(_ok())
    answer = _bridge(fake).ask("sistem", "kullanici")
    assert answer is not None
    assert answer.model == FLAGSHIP
    assert answer.tries == 1
    assert fake.models == [FLAGSHIP]


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
    fake = _Fake(*[Reply(503, b"") for _ in range(6)])
    bridge = _bridge(fake)
    assert bridge.ask("sistem", "kullanici") is None
    assert len(fake.asked) == 6, "her basamak ikiser kez denenmeli"
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
    assert Bridge(api_key="x").timeout == 90.0


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
