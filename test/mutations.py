"""Proving that the tests can fail.

A green suite means nothing on its own. It says the tests did not object to this
version of the code -- not that they would object to a worse one. Twice already
in this project a test passed while proving nothing: a `pgrep` pattern that never
matched anything, and an assertion about a process that had quietly ended before
the assertion ran. Both looked exactly like the tests around them.

So each rule the code follows gets deliberately broken here, one at a time, and
the suite has to notice. A break that goes unnoticed is not a small problem: it
means that rule is unguarded, and the next person to change that line will be
told everything is fine.

    python test/mutations.py

Every mutation is applied to a file on disk and undone immediately afterwards,
whether the run succeeded, failed, or was interrupted. The baseline is checked
first, because if the suite is already red then every mutation would look caught
and the whole exercise would be theatre.

This is not collected by pytest -- it runs pytest. It lives in `test/` because
that is where the things that check the code belong.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "sift"


@dataclass(frozen=True)
class Mutation:
    """One rule, and the smallest edit that breaks it."""

    file: str
    rule: str
    before: str
    after: str

    @property
    def path(self) -> Path:
        return SOURCE / self.file


# Split across adjacent literals only to stay inside the line limit: what they
# join into has to match the source byte for byte.
_POST_CALL = "            return self._post("
_POST_ARGS = "url=url, headers=headers, body=body, timeout=self.timeout)\n"
_REACH_GUARDED = (
    "        try:\n"
    + _POST_CALL
    + _POST_ARGS
    + "        except OSError as exc:"
    + "  # a transport of one's own is allowed to be less careful\n"
    + '            return Reply(0, str(exc).encode("utf-8", "replace"))\n'
)
_REACH_BARE = "        return self._post(" + _POST_ARGS


MUTATIONS = [
    # -- Faz 1: capture ------------------------------------------------------
    Mutation(
        "capture.py",
        "a timeout ends the whole tree, not just the process it started",
        "            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)",
        "            proc.kill()",
    ),
    Mutation(
        "capture.py",
        "a stranger holding the pipe cannot hold the run open",
        "            _pump_until_stopped(source, sink, stop)",
        "            _pump_until_closed(source, sink)",
    ),
    Mutation(
        "capture.py",
        "a byte that is not utf-8 does not stop the capture",
        'return self.raw.decode("utf-8", errors="replace")',
        'return self.raw.decode("utf-8")',
    ),
    Mutation(
        "capture.py",
        "a run is marked complete only once it has finished",
        "    store.finish(meta)\n    return Capture(meta)",
        "    return Capture(meta)",
    ),
    Mutation(
        "store.py",
        "the same command run twice gets two handles",
        "seed = f\"{started_at!r}|{os.getpid()}|{' '.join(command)}\"",
        'seed = " ".join(command)',
    ),
    Mutation(
        "peek.py",
        "a range past the end is clamped, not refused",
        "    last = total if end is None else max(first, min(end, total))",
        "    last = total if end is None else end",
    ),
    # -- Faz 2: model bridge -------------------------------------------------
    Mutation(
        "model.py",
        "the largest model is asked first",
        '    "nvidia/nemotron-3-ultra-550b-a55b",  # flagship: asked first, always\n'
        '    "nvidia/nemotron-3-super-120b-a12b",\n',
        '    "nvidia/nemotron-3-super-120b-a12b",\n'
        '    "nvidia/nemotron-3-ultra-550b-a55b",  # flagship: asked first, always\n',
    ),
    Mutation(
        "model.py",
        "no key means nothing is sent at all",
        "        if not self.available:\n",
        "        if False:\n",
    ),
    Mutation(
        "model.py",
        "a rejected key ends the walk instead of touring the ladder",
        '                    self.last_error = f"key rejected ({reply.status})"\n'
        "                    return None\n",
        '                    self.last_error = f"key rejected ({reply.status})"\n'
        "                    break\n",
    ),
    Mutation(
        "model.py",
        "a busy rung is given a second chance before it is left behind",
        "_TRIES_PER_RUNG = 2",
        "_TRIES_PER_RUNG = 1",
    ),
    Mutation(
        "model.py",
        "an unreachable endpoint does not cost the flagship",
        "TRANSIENT = frozenset({0, 408, 409, 425, 429, 500, 502, 503, 504})",
        "TRANSIENT = frozenset({408, 409, 425, 429, 500, 502, 503, 504})",
    ),
    Mutation(
        "model.py",
        "a transport that raises is turned into an unreachable reply",
        _REACH_GUARDED,
        _REACH_BARE,
    ),
    Mutation(
        "model.py",
        "an empty answer counts as no answer",
        "    if not isinstance(content, str) or not content.strip():",
        "    if not isinstance(content, str):",
    ),
    Mutation(
        "model.py",
        "the environment beats the stored key file",
        "    for name in KEY_VARIABLES:\n"
        '        value = (os.environ.get(name) or "").strip()\n'
        "        if value:\n"
        "            return value\n"
        "    try:\n"
        '        value = KEY_FILE.expanduser().read_text(encoding="utf-8").strip()\n'
        "    except OSError:\n"
        "        return None\n"
        "    return value or None\n",
        "    try:\n"
        '        value = KEY_FILE.expanduser().read_text(encoding="utf-8").strip()\n'
        "        if value:\n"
        "            return value\n"
        "    except OSError:\n"
        "        pass\n"
        "    for name in KEY_VARIABLES:\n"
        '        value = (os.environ.get(name) or "").strip()\n'
        "        if value:\n"
        "            return value\n"
        "    return None\n",
    ),
    Mutation(
        "model.py",
        "nothing is added to the prompt on the way out",
        '                    "stream": False,\n',
        '                    "stream": False,\n                    "user": os.getcwd(),\n',
    ),
]


def _run_suite() -> tuple[int, str]:
    """The suite, with the live call switched off so the network cannot decide this."""
    env = dict(os.environ)
    env.pop("SIFT_LIVE", None)
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "--no-header", "-p", "no:cacheprovider", "-x"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    tail = ""
    for line in reversed(finished.stdout.strip().splitlines()):
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if any(word in clean for word in ("passed", "failed", "error")):
            tail = clean
            break
    return finished.returncode, tail


def main() -> int:
    code, tail = _run_suite()
    if code != 0:
        print(f"Baseline is not green ({tail}). Fix that first -- until then every")
        print("mutation would look caught for the wrong reason.")
        return 2
    print(f"baseline  {tail}\n")

    escaped: list[Mutation] = []
    for mutation in MUTATIONS:
        original = mutation.path.read_text(encoding="utf-8")
        found = original.count(mutation.before)
        if found != 1:
            print(f"NO ANCHOR  {mutation.rule}  ({found} matches in {mutation.file})")
            escaped.append(mutation)
            continue
        try:
            mutation.path.write_text(
                original.replace(mutation.before, mutation.after, 1), encoding="utf-8"
            )
            code, tail = _run_suite()
        finally:
            mutation.path.write_text(original, encoding="utf-8")
        if code == 0:
            print(f"ESCAPED    {mutation.rule}  ({tail})")
            escaped.append(mutation)
        else:
            print(f"caught     {mutation.rule}")

    print(f"\n{len(MUTATIONS) - len(escaped)}/{len(MUTATIONS)} caught")
    if escaped:
        print("An escaped mutation means that rule is unguarded, not that it is unimportant.")
    return 1 if escaped else 0


if __name__ == "__main__":
    raise SystemExit(main())
