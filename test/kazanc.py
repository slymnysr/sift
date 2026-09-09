"""What a view costs the reader, against what the command actually printed.

`sift stats` answers this in bytes, and bytes are the wrong unit twice over: a
request is not billed in them and a context window does not hold them. So this
script asks the only thing that can answer it exactly -- the model's own
tokenizer -- by sending each text and reading the `usage.prompt_tokens` the
endpoint returns. Nothing here is estimated and nothing is divided by four.

    python test/kazanc.py                       # this project's own test suite
    python test/kazanc.py -- cargo build         # or any command you like

Three requests: one empty, to measure the fixed overhead every message carries,
and one for each of the two texts. The command itself is run once, through
`sift`, exactly as a caller would run it -- what is measured is what a caller
would actually have received, footer included, because over MCP the footer
travels inside the result.

This is not collected by pytest. It spends requests and it needs a key, which
is why it is a script and not a test.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sift.model import DEFAULT_BASE_URL, find_key  # noqa: E402

MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT = ["uv", "run", "python", "-m", "pytest", "-v", "-o", "addopts=",
           "-p", "no:cacheprovider"]
HANDLE = re.compile(r"sift peek ([0-9a-f]{8})")

# The installed command if there is one, and the module if there is not.
# What is measured is what a caller receives, so it has to be run the way
# a caller runs it rather than imported and called.
SIFT = [shutil.which("sift")] if shutil.which("sift") else [
    sys.executable, "-c", "from sift.cli import main; raise SystemExit(main())"
]


def _tokens(text: str, key: str) -> int:
    """What the endpoint says this message costs, before it answers it."""
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 1,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{DEFAULT_BASE_URL}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as reply:
        return json.load(reply)["usage"]["prompt_tokens"]


def main(argv: list[str]) -> int:
    key = find_key()
    if not key:
        print("kazanc: no key, and this measures what a key buys.", file=sys.stderr)
        return 1

    command = argv[argv.index("--") + 1 :] if "--" in argv else DEFAULT
    print("$ sift run --", " ".join(command))

    finished = subprocess.run(
        [*SIFT, "run", "--", *command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # Everything the caller gets: the view, and the line that says what it is.
    got = finished.stdout + "".join(
        line + "\n" for line in finished.stderr.splitlines() if line.startswith("sift ")
    )

    found = HANDLE.search(finished.stdout) or HANDLE.search(finished.stderr)
    if not found:
        print("kazanc: nothing was left out, so there is nothing to weigh.", file=sys.stderr)
        return 1
    raw = subprocess.run(
        [*SIFT, "peek", found.group(1)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    overhead = _tokens("", key)
    before, after = _tokens(raw, key) - overhead, _tokens(got, key) - overhead

    print(f"{'':10}{'lines':>8}{'tokens':>10}")
    print(f"{'printed':10}{raw.count(chr(10)):>8,}{before:>10,}")
    print(f"{'returned':10}{got.count(chr(10)):>8,}{after:>10,}")
    print(f"\n{(before - after) * 100 / before:.1f}% fewer tokens, counted by {MODEL}")
    print(f"handle {found.group(1)} still has every line of it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
