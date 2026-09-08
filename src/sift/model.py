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
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sift.privacy import sending_on

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

DEFAULT_LADDER = (
    "nvidia/nemotron-3-ultra-550b-a55b",  # flagship: asked first, always
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
_DEFAULT_TIMEOUT = 90.0


@dataclass(frozen=True)
class Reply:
    """One HTTP answer, reduced to the two things that matter here.

    A status of 0 means the endpoint was never reached at all -- no network, no
    DNS, a refused connection. It is grouped with the busy statuses because it
    says the same thing: try again, or try elsewhere.
    """

    status: int
    body: bytes


@dataclass(frozen=True)
class Answer:
    """What the model said, and what it took to get it."""

    text: str
    model: str
    tries: int


Transport = Callable[..., Reply]


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
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.ladder = tuple(ladder) if ladder is not None else default_ladder()
        written_url = base_url or os.environ.get("SIFT_BASE_URL") or DEFAULT_BASE_URL
        self.base_url = written_url.rstrip("/")
        self.api_key = find_key() if api_key is None else api_key
        self.timeout = _as_float(os.environ.get("SIFT_TIMEOUT"), _DEFAULT_TIMEOUT, timeout)
        self.last_error: str | None = None
        self._post = transport or post
        self._sleep = sleep

    @property
    def available(self) -> bool:
        """Whether there is a key to ask with.

        Callers use this to choose a path before spending effort building a
        prompt, not to decide whether they are allowed to fail: `ask` is safe to
        call either way.
        """
        return bool(self.api_key)

    def ask(self, system: str, user: str, *, max_tokens: int = 1024) -> Answer | None:
        """Put a question to the best model that will take it, or return nothing.

        The ladder is walked from the top. A rung that is busy or unreachable is
        tried once more and then left behind; a rung that does not exist is left
        behind immediately. A rejected key ends the walk altogether -- a smaller
        model will reject it just as firmly, and asking again only spends the
        user's time to arrive at the same place.
        """
        if not sending_on():
            # Asked before the key, because the reason a caller is given should
            # be the one they can act on: a switch they set is not a key they
            # forgot.
            self.last_error = "sending is switched off (SIFT_NO_MODEL)"
            return None

        if not self.available:
            self.last_error = "no api key"
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        tries = 0

        for model in self.ladder:
            body = json.dumps(
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                ensure_ascii=False,
            ).encode("utf-8")

            for attempt in range(_TRIES_PER_RUNG):
                tries += 1
                reply = self._reach(url, headers, body)

                if reply.status == 200:
                    text = _said(reply.body)
                    if text is not None:
                        self.last_error = None
                        return Answer(text=text, model=model, tries=tries)
                    self.last_error = f"{model}: reply could not be read"
                    break  # the same model will phrase it the same way again

                if reply.status in (401, 403):
                    self.last_error = f"key rejected ({reply.status})"
                    return None

                if reply.status in TRANSIENT:
                    self.last_error = f"{model}: busy or unreachable ({reply.status})"
                    if attempt + 1 < _TRIES_PER_RUNG:
                        self._sleep(_BACKOFF_SECONDS * (attempt + 1))
                    continue

                # 404 and the rest of the 4xx family are statements about this
                # request. A different model may still accept it, so the walk goes
                # on, but repeating it word for word to the same one will not.
                self.last_error = f"{model}: refused ({reply.status})"
                break

        return None

    def _reach(self, url: str, headers: dict[str, str], body: bytes) -> Reply:
        """Call the transport, turning any way it can fail into an unreachable reply."""
        try:
            return self._post(url=url, headers=headers, body=body, timeout=self.timeout)
        except OSError as exc:  # a transport of one's own is allowed to be less careful
            return Reply(0, str(exc).encode("utf-8", "replace"))


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


def _as_float(written: str | None, fallback: float, given: float | None) -> float:
    """A number the caller gave, else one from the environment, else the default."""
    if given is not None:
        return float(given)
    try:
        return float(written) if written else fallback
    except ValueError:
        return fallback
