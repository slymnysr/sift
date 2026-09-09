"""Reaching a model, and never depending on having reached one.

`sift` asks a model which lines of a capture are worth showing. That question is
worth asking well, so the ladder starts at the largest model available and only
steps down when a rung cannot be reached. Stepping down is about availability,
never about spending less: every rung here is free, and the top one is where the
judgement is best.

Three things are deliberate.

**Nothing is raised.** `ask` returns an answer or nothing at all. A missing key,
an unplugged network, a model that is busy, a reply that makes no sense -- none
of these are the user's problem, and none of them may stop a tool whose job is to
run their command. Everything that goes wrong is recorded in `last_error` for
anyone who wants to look, and then the caller carries on without a model.

**No client library.** This talks to an OpenAI-shaped endpoint over `urllib`,
which is in the standard library. A tool that gets installed into other people's
environments should not drag a dependency tree in behind it, and the request here
is a single POST -- there is nothing to abstract.

**Only what the caller hands over leaves this machine.** No identity, no
environment, no paths, nothing gathered on the side. What gets sent is the
prompt, and deciding what is safe to put in that prompt is the caller's job, not
a hidden one taken on here.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sift.privacy import sending_on

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

DEFAULT_LADDER = (
    # Ordered by measurement, not by parameter count, and the flagship is not on
    # it. Measured on 2026-09-08 against the free tier: the 550b holds a request
    # in a queue for 107-124 seconds before it answers, on two independent
    # providers -- so the wait is the model's, not one endpoint's mood. The same
    # question costs `super` about six seconds and `lightning` about fourteen.
    #
    # Keeping it first cost every distillation 181.5 seconds it could not use:
    # two timeouts at 90s, then the fall to the rung that was going to answer
    # anyway. Measured end to end, one 404-line build took 500 seconds. Without
    # it, the same work is 6-15.
    #
    # It is left out rather than moved last because last is where a ladder goes
    # when everything above it has failed -- which is exactly when nobody can
    # afford to wait two minutes. `SIFT_MODELS` puts it back for anyone who
    # wants it.
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
)

KEY_FILE = Path("~/.config/nvidia/api_key")
KEY_VARIABLES = ("SIFT_API_KEY", "NVIDIA_API_KEY")

# Conditions that say "not now" rather than "not ever". Anything else is a fact
# about the request, and a fact about the request does not improve on retry.
TRANSIENT = frozenset({0, 408, 409, 425, 429, 500, 502, 503, 504})

_TRIES_PER_RUNG = 2
_BACKOFF_SECONDS = 1.5
# How long one ask may take before the rung is given up on.
#
# Measured. A rung that is going to answer answers in about six seconds; a rung
# that is queued takes over a hundred. Ninety was the worst number available:
# far past the first, far short of the second, so it paid a minute and a half
# and learned nothing. Twenty-five is comfortably past a working rung and
# comfortably short of a queued one. `SIFT_TIMEOUT` moves it.
_DEFAULT_TIMEOUT = 25.0

# What the second pass waits, when the first one ran out of time everywhere.
#
# The first pass is short on purpose, and short is right nearly always: a rung
# that is going to answer answers in about six seconds. But "nobody answered in
# twenty-five seconds" is not the same statement as "nobody was going to" --
# measured, a queued rung clears at 107-124 seconds, which is where the flagship
# sits when the free tier is busy.
#
# So the choice between fast and patient is not made. Both are, in that order,
# and the patience is only ever spent when the quick way came back with nothing.
# On an ordinary day it costs nothing at all: the first pass answers and the
# second never begins. `SIFT_PATIENCE=0` turns it off for a caller who would
# rather have a quick no.
_PATIENT_TIMEOUT = 150.0


@dataclass(frozen=True)
class Reply:
    """One HTTP answer, reduced to the two things that matter here.

    A status of 0 means the endpoint was never reached at all -- no network, no
    DNS, a refused connection. It is grouped with the busy statuses because it
    says the same thing: try again, or try elsewhere.
    """

    status: int
    body: bytes
    # Whether the endpoint took longer than it was given, as opposed to
    # refusing quickly. Both are "try elsewhere", and only one of them is worth
    # asking twice: a refusal costs a moment, a wait costs the whole timeout.
    timed_out: bool = False


@dataclass(frozen=True)
class Answer:
    """What the model said, and what it took to get it."""

    text: str
    model: str
    tries: int
    # What the endpoint says this exchange cost, in its own tokens. Read from
    # the reply rather than worked out here: a token count computed by dividing
    # bytes by four is a guess wearing the clothes of a measurement, and it is
    # wrong by different amounts in every language this tool is pointed at.
    # Zero when the reply did not say, which is the honest answer to "how many"
    # when nobody counted.
    tokens: int = 0


Transport = Callable[..., Reply]


def own_endpoint() -> str | None:
    """The endpoint somebody pointed this at on purpose, if they did.

    `SIFT_BASE_URL` is not a preference; it is a decision about where questions
    go. Somebody who set it is running their own model -- Ollama, llama.cpp,
    vLLM, LM Studio, a company gateway -- and every one of those answers without
    a key, because there is nobody to bill.
    """
    written = (os.environ.get("SIFT_BASE_URL") or "").strip()
    return written or None


def somewhere_to_ask() -> bool:
    """Whether a question has anywhere to go: a key, or an endpoint of one's own.

    The two are alternatives rather than a pair. The default endpoint bills, so
    it needs a key and a machine without one has not finished being set up. An
    endpoint someone typed themselves is the opposite: they said where, and what
    it wants is its business.
    """
    return find_key() is not None or own_endpoint() is not None


def find_key() -> str | None:
    """The API key, from the environment or from where `nemotron` keeps it.

    The file is checked last so that a shell can override it for one command
    without editing anything, which is what a person debugging expects.
    """
    for name in KEY_VARIABLES:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    try:
        value = KEY_FILE.expanduser().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def effort() -> str | None:
    """How hard the model should think before answering, or None to leave it alone.

    Measured, and the measurement is the reason this exists. Asked which lines
    matter in a 404-line build, the model wrote 924 tokens of reasoning to
    produce a twelve-token answer, and the caller waited 15.3 seconds for it.
    The same question at `reasoning_effort=low` took 2.4 seconds and named the
    same lines.

    Deliberately a setting rather than a constant: it is an OpenAI-shaped field
    that not every endpoint accepts, and an endpoint that rejects it would
    otherwise turn a speed setting into no answer at all.
    """
    written = os.environ.get("SIFT_EFFORT", "").strip().lower()
    return written or None


def default_ladder() -> tuple[str, ...]:
    """The rungs to try, in order, with `SIFT_MODELS` overriding the built-in list."""
    written = os.environ.get("SIFT_MODELS", "")
    chosen = tuple(part.strip() for part in written.split(",") if part.strip())
    return chosen or DEFAULT_LADDER


class Bridge:
    """A way to ask a model something, or to find out that you cannot."""

    def __init__(
        self,
        *,
        ladder: Sequence[str] | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        patience: float | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.ladder = tuple(ladder) if ladder is not None else default_ladder()
        written_url = base_url or os.environ.get("SIFT_BASE_URL") or DEFAULT_BASE_URL
        self.base_url = written_url.rstrip("/")
        self.api_key = find_key() if api_key is None else api_key
        # Whether this was pointed somewhere on purpose. A key is not the only
        # way to have somewhere to ask, and a local model is not billed.
        self.own_endpoint = bool(base_url or own_endpoint())
        self.timeout = _as_float(os.environ.get("SIFT_TIMEOUT"), _DEFAULT_TIMEOUT, timeout)
        self.patience = _as_float(
            os.environ.get("SIFT_PATIENCE"), _PATIENT_TIMEOUT, patience
        )
        self.last_error: str | None = None
        self._post = transport or post
        self._sleep = sleep

    @property
    def available(self) -> bool:
        """Whether there is anywhere to ask: a key, or an endpoint of one's own.

        Callers use this to choose a path before spending effort building a
        prompt, not to decide whether they are allowed to fail: `ask` is safe to
        call either way.

        A key is not the only way. The default endpoint bills and so it needs
        one; a model somebody is running themselves does not, and refusing to
        ask it because no key was found would be refusing on behalf of a
        transaction that nobody is making.
        """
        return bool(self.api_key) or self.own_endpoint

    def ask(self, system: str, user: str, *, max_tokens: int = 1024) -> Answer | None:
        """Put a question to the best model that will take it, or return nothing.

        The ladder is walked twice at most, and the second walk is the whole of
        why the first one may be impatient.

        **The quick pass.** Every rung, with the short timeout. A rung that is
        going to answer answers in about six seconds, so this is the pass that
        does the work nearly every time.

        **The patient pass.** Only when the quick one ran out of time, and only
        for that reason. "Nobody answered in twenty-five seconds" is not the same
        statement as "nobody was going to": measured, a queued rung clears at
        107-124 seconds. A rejected key or a refused request is not a queue and
        waiting cannot help it, so neither buys a second pass.

        Between them these give what one timeout could not. A single short value
        is fast and gives up on a busy hour; a single long one waits two minutes
        for every distillation to be sure. Two passes are fast when it is fast
        and patient when patience is the only thing left.
        """
        if not sending_on():
            # Asked before the key, because the reason a caller is given should
            # be the one they can act on: a switch they set is not a key they
            # forgot.
            self.last_error = "sending is switched off (SIFT_NO_MODEL)"
            return None

        if not self.available:
            self.last_error = "no api key and no endpoint of your own"
            return None

        answer, queued = self._walk(system, user, max_tokens, self.timeout)
        if answer is not None or not queued:
            return answer

        if self.patience <= self.timeout:
            return None

        quick = self.last_error
        answer, _ = self._walk(system, user, max_tokens, self.patience)
        if answer is None and self.last_error:
            self.last_error = f"{quick}; then {self.patience:g}s: {self.last_error}"
        return answer

    def _walk(
        self, system: str, user: str, max_tokens: int, timeout: float
    ) -> tuple[Answer | None, bool]:
        """One pass down the ladder. Returns the answer, and whether to be patient.

        The second half of that pair is the only thing this knows that `ask`
        does not: a walk that ended in timeouts may be worth repeating slowly,
        and a walk that ended in refusals is not. A rejected key returns False
        with it -- waiting will not mint a new key, and a second pass would put
        a dead one in front of every rung again.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Sent only when there is one. `Bearer None` is a string a local server
        # has to decide what to do with, and some of them decide wrongly.
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        tries = 0
        queued = False

        for model in self.ladder:
            wanted = effort()
            body = _body(model, system, user, max_tokens, wanted)

            for attempt in range(_TRIES_PER_RUNG):
                tries += 1
                reply = self._reach(url, headers, body, timeout)

                if reply.status == 200:
                    text = _said(reply.body)
                    if text is not None:
                        self.last_error = None
                        return (
                            Answer(
                                text=text,
                                model=model,
                                tries=tries,
                                tokens=_spent(reply.body),
                            ),
                            False,
                        )
                    self.last_error = f"{model}: reply could not be read"
                    break  # the same model will phrase it the same way again

                if reply.status in (401, 403):
                    self.last_error = f"key rejected ({reply.status})"
                    return None, False

                if reply.status in TRANSIENT:
                    self.last_error = f"{model}: busy or unreachable ({reply.status})"
                    if reply.timed_out:
                        # Measured, and this is the whole of it. A rung on a free
                        # tier can hold a request in a queue for 107-124 seconds
                        # before answering or refusing. A timeout means that queue
                        # is longer than this pass is willing to wait, and asking
                        # the same rung again inside the same pass is joining the
                        # same queue again -- a second full timeout for the same
                        # answer. Waiting longer is the patient pass's job, once,
                        # after every rung has had its quick chance.
                        #
                        # A fast refusal is a different thing: it cost a moment,
                        # and the moment after may go through.
                        self.last_error = f"{model}: no answer in {timeout:g}s"
                        queued = True
                        break
                    if attempt + 1 < _TRIES_PER_RUNG:
                        self._sleep(_BACKOFF_SECONDS * (attempt + 1))
                    continue

                # 404 and the rest of the 4xx family are statements about this
                # request. A different model may still accept it, so the walk goes
                # on, but repeating it word for word to the same one will not.
                if wanted:
                    # Unless the only thing wrong with it was ours. `SIFT_EFFORT`
                    # is a speed setting this tool adds; an endpoint that will
                    # not take the field should cost the caller a second
                    # request, never an answer. Asked again without it, and only
                    # once -- if it is refused again the reason was not this.
                    self.last_error = f"{model}: refused ({reply.status}) with effort"
                    wanted = None
                    body = _body(model, system, user, max_tokens, None)
                    continue
                self.last_error = f"{model}: refused ({reply.status})"
                break

        return None, queued

    def _reach(
        self, url: str, headers: dict[str, str], body: bytes, timeout: float
    ) -> Reply:
        """Call the transport, turning any way it can fail into an unreachable reply."""
        try:
            return self._post(url=url, headers=headers, body=body, timeout=timeout)
        except TimeoutError as exc:
            return Reply(0, str(exc).encode("utf-8", "replace"), timed_out=True)
        except OSError as exc:  # a transport of one's own is allowed to be less careful
            waited = isinstance(exc, socket.timeout) or "timed out" in str(exc).lower()
            return Reply(0, str(exc).encode("utf-8", "replace"), timed_out=waited)


def post(*, url: str, headers: dict[str, str], body: bytes, timeout: float) -> Reply:
    """One POST, with every failure reported as a status rather than an exception."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return Reply(response.status, response.read())
    except urllib.error.HTTPError as exc:
        return Reply(exc.code, exc.read() or b"")
    except (OSError, ValueError) as exc:
        return Reply(0, str(exc).encode("utf-8", "replace"))


def _body(
    model: str, system: str, user: str, max_tokens: int, effort_now: str | None
) -> bytes:
    """One request, as bytes. Built here so it can be built twice.

    The second time is without `reasoning_effort`, for an endpoint that does not
    know the field -- see the refusal branch in `ask`.
    """
    asked: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if effort_now:
        asked["reasoning_effort"] = effort_now
    return json.dumps(asked, ensure_ascii=False).encode("utf-8")


def _said(body: bytes) -> str | None:
    """The message out of an OpenAI-shaped reply, or None if there is not one.

    An empty answer counts as no answer. A caller that acted on it would be
    acting on silence dressed up as a decision.
    """
    try:
        content = json.loads(body)["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, IndexError, TypeError):
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    return content


def _spent(body: bytes) -> int:
    """What the endpoint says the exchange cost, or zero if it did not say.

    Measured, and that is the whole point of reading it rather than estimating
    it. The alternative on offer is bytes divided by four, which is a rule of
    thumb about English prose being sold as a count -- and this tool is pointed
    at Japanese, at Turkish, at base64 and at stack traces, where it is wrong by
    a factor rather than a margin.

    Zero is not a failure and is not treated as one. It means nobody counted,
    and a report that filled that in with arithmetic would be publishing its own
    guess as the endpoint's number.
    """
    try:
        usage = json.loads(body)["usage"]
        return max(0, int(usage["total_tokens"]))
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError):
        return 0


def _as_float(written: str | None, fallback: float, given: float | None) -> float:
    """A number the caller gave, else one from the environment, else the default."""
    if given is not None:
        return float(given)
    try:
        return float(written) if written else fallback
    except ValueError:
        return fallback
