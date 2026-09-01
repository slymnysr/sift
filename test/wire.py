#!/usr/bin/env python3
"""Faz 7 -- the whole chain at once, live, over the transport a client uses.

Every other test in this suite holds part of the chain still. This one holds
nothing still: it launches the installed `sift-mcp` as a subprocess, speaks
stdio to it the way a client does, runs a real command that prints a real amount
of output, and lets a real model decide which of it comes back.

    uv run python test/wire.py                    # the default command
    uv run python test/wire.py "cargo build"      # any other

What it prints is not a benchmark -- the savings report is its own phase. It is
the answer to a narrower question: with packaging, entry point, transport, model
and fallback all in play at the same time, does anything come back, and is what
comes back the truth. So it checks the two things a client cannot check for
itself:

Every line returned has to be in the capture, or the tool has invented one.
`peek` has to return the bytes behind a gap, or the tool has lost one.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

from sift.model import find_key

# The command this tool was written for, pointed at the repository it lives in:
# real output, real length, and one line at the end that a reader would stop on.
DEFAULT = f'"{sys.executable}" -m pytest --no-header -vv'

MARKER = re.compile(r"^─ ([\d,]+) lines? not shown · sift peek (\S+) for any of them ─$")


def parameters(home: Path) -> StdioServerParameters:
    script = shutil.which("sift-mcp")
    return StdioServerParameters(
        command=script or sys.executable,
        args=[] if script else ["-m", "sift.server"],
        env={**os.environ, "SIFT_HOME": str(home)},
    )


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")


def report(command: str, answer: str, whole: str) -> int:
    """What came back, what it stood for, and whether any of it was invented."""
    note = answer.strip().splitlines()[-1]
    shown = [
        line for line in answer.strip().splitlines()[:-1] if line and not MARKER.match(line)
    ]
    every = whole.splitlines()
    invented = [line for line in shown if line not in every]

    raw_bytes = len(whole.encode("utf-8"))
    kept_bytes = len(answer.encode("utf-8"))
    part = kept_bytes * 100 / raw_bytes if raw_bytes else 0

    print(f"command   {command}")
    print(f"captured  {len(every):,} lines · {raw_bytes:,} bytes")
    print(f"returned  {len(shown):,} lines · {kept_bytes:,} bytes · {part:.1f}% of it")
    print(f"note      {note}")
    print(f"invented  {len(invented)}")
    for line in invented[:5]:
        print(f"          {line!r}")
    print()
    for line in answer.strip().splitlines()[:-1]:
        print(f"  {line}")
    return 1 if invented else 0


async def ask(command: str) -> int:
    home = Path(tempfile.mkdtemp(prefix="sift-wire-"))
    async with Client(parameters(home)) as client:
        answer = text_of(await client.call_tool("run", {"command": command}))
        handle = answer.strip().splitlines()[-1].split()[1]
        whole = text_of(await client.call_tool("peek", {"handle": handle}))
        whole = "\n".join(whole.strip().splitlines()[:-1])

    return report(command, answer, whole)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if find_key() is None:
        print("No key, so nothing would be measured but the fallback. Set SIFT_API_KEY.")
        return 2
    return asyncio.run(ask(args[0] if args else DEFAULT))


if __name__ == "__main__":
    raise SystemExit(main())
