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
        """A bare name is a module of the tool; a path is relative to the repo.

        The measurement scripts under `test/` decide what this project claims to
        have measured, and a rule that only holds because nothing checks it is no
        better there than in `src/`.
        """
        return ROOT / self.file if "/" in self.file else SOURCE / self.file


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
    # -- Faz 3: distillation -------------------------------------------------
    Mutation(
        "distill.py",
        "a number past the end of the capture is dropped, not merely unprintable",
        "        end = min(end, total)",
        "        end = end",
    ),
    Mutation(
        "distill.py",
        "there is no line before the first one",
        "        start = max(start, 1)",
        "        start = start",
    ),
    Mutation(
        "distill.py",
        "every piece is numbered as part of the whole capture",
        "    batches = _batches(list(enumerate(lines, 1)))",
        "    batches = _batches([(1, line) for line in lines])",
    ),
    Mutation(
        "distill.py",
        "the first line of a capture is line one",
        "    batches = _batches(list(enumerate(lines, 1)))",
        "    batches = _batches(list(enumerate(lines, 0)))",
    ),
    Mutation(
        "distill.py",
        "a capture too long for one ask is split",
        "        if current and size + cost > CHARS_PER_ASK:",
        "        if False:",
    ),
    Mutation(
        "distill.py",
        "an answer with no numbers in it is no answer",
        "    if not chosen:\n        return None\n",
        "    if False:\n        return None\n",
    ),
    Mutation(
        "distill.py",
        "lines folded away before a shown one are marked",
        "        if start > previous_end + 1:",
        "        if False:",
    ),
    Mutation(
        "distill.py",
        "lines folded away after the last shown one are marked",
        "    if previous_end < len(lines):",
        "    if False:",
    ),
    Mutation(
        "distill.py",
        "a line too wide to judge is shortened before it is asked about",
        "PROMPT_LINE_CAP = 400",
        "PROMPT_LINE_CAP = 100_000",
    ),
    Mutation(
        "distill.py",
        "a gap is written the way the README says it is written",
        '    return f"─ {count:,} {word} not shown · sift peek {handle} for any of them ─"',
        '    return f"─ {count} {word} not shown · sift peek {handle} for any of them ─"',
    ),
    Mutation(
        "distill.py",
        "the view is built from the capture and from nothing else",
        "        text=render(lines, chosen, handle),",
        "        text=render(lines, chosen, handle) + answer.text,",
    ),
    # -- Faz 4: the safety net -----------------------------------------------
    Mutation(
        "fallback.py",
        "the ends are shown, and no claim is made about the middle",
        "    return set(range(1, head + 1)) | set(range(total - tail + 1, total + 1))",
        "    return set(range(1, head + tail + 1))",
    ),
    Mutation(
        "fallback.py",
        "a capture shorter than the ends asked for is shown whole",
        "    if total <= head + tail:\n        return set(range(1, total + 1))\n",
        "    if False:\n        return set(range(1, total + 1))\n",
    ),
    Mutation(
        "fallback.py",
        "a run that failed gets more of its ending",
        "    tail = TAIL_WHEN_FAILED if capture.meta.failed else TAIL",
        "    tail = TAIL",
    ),
    Mutation(
        "fallback.py",
        "a view nobody chose does not claim a model chose it",
        "        model=None,",
        '        model="fallback",',
    ),
    Mutation(
        "store.py",
        "a handle that was never captured is not an empty capture",
        '        raise FileNotFoundError(f"no capture named {handle!r}")',
        '        return b""',
    ),
    Mutation(
        "cli.py",
        "the command's own exit code comes back out",
        "    return capture.meta.exit_code or 0",
        "    return 0",
    ),
    Mutation(
        "cli.py",
        "a run stopped for taking too long is reported the way a shell reports it",
        "    if capture.meta.timed_out:\n        return TIMED_OUT\n",
        "    if False:\n        return TIMED_OUT\n",
    ),
    Mutation(
        "view.py",
        "a bug in the distiller costs the view and nothing else",
        "    except Exception as exc:  # a bug here must not cost the caller their output",
        "    except ValueError as exc:  # a bug here must not cost the caller their output",
    ),
    Mutation(
        "cli.py",
        "a command that cannot be run is reported, not raised at the user",
        "    except OSError as exc:\n"
        '        print(f"sift: {exc}", file=sys.stderr)\n'
        "        return CANNOT_RUN\n",
        "    except ValueError as exc:\n"
        '        print(f"sift: {exc}", file=sys.stderr)\n'
        "        return CANNOT_RUN\n",
    ),
    Mutation(
        "cli.py",
        "the view goes to stdout and the note about it goes to stderr",
        "    print(footer(capture, view, who), file=sys.stderr)",
        "    print(footer(capture, view, who))",
    ),
    Mutation(
        "cli.py",
        "when everything that chooses lines fails, every line is shown",
        "    except Exception as exc:  # the view is optional; the output is not",
        "    except ValueError as exc:  # the view is optional; the output is not",
    ),
    Mutation(
        "cli.py",
        "the last resort shows the capture rather than announcing it",
        "        sys.stdout.write(capture.text())",
        '        sys.stdout.write("")',
    ),
    Mutation(
        "cli.py",
        "a flag is only a flag at the front, before the command begins",
        '        if args[0] == "--timeout" and len(args) > 1:',
        '        if "--timeout" in args and len(args) > 1:',
    ),
    # -- Faz 5: one definition of a line, for every language ------------------
    Mutation(
        "lines.py",
        "a line ends at a newline and at nothing else",
        "    found = text.split(\"\\n\")",
        "    found = text.splitlines()",
    ),
    Mutation(
        "lines.py",
        "a trailing newline ends the last line rather than starting another",
        "    if found[-1] == \"\":\n",
        "    if False:\n",
    ),
    Mutation(
        "lines.py",
        "a carriage return before a newline belongs to the ending",
        '    return [line[:-1] if line.endswith("\\r") else line for line in found]',
        "    return found",
    ),
    Mutation(
        "store.py",
        "a capture is read as bytes, so nothing rewrites its line endings",
        "    return p.read_bytes()",
        '    return p.read_text(encoding="utf-8", errors="replace").encode("utf-8")',
    ),
    # -- Faz 6: what a file declares, without a table of languages -----------
    Mutation(
        "outline.py",
        "a file is read as bytes, so nothing rewrites its line endings",
        '    return text_lines.of(Path(path).read_bytes().decode("utf-8", errors="replace"))',
        '    return text_lines.of(Path(path).read_text(errors="replace"))',
    ),
    Mutation(
        "outline.py",
        "the outline is asked about the file and never about its name",
        "    return select(read(path), QUESTION, str(path), bridge, budget=BUDGET)",
        "    return select(\n"
        "        [str(path), *read(path)], QUESTION, str(path), bridge, budget=BUDGET\n"
        "    )",
    ),
    Mutation(
        "distill.py",
        "the question put to the model is the one the caller asked",
        "    batches = _batches(list(enumerate(lines, 1)))\n"
        "    asked = prompt(question, budget, len(batches))",
        "    batches = _batches(list(enumerate(lines, 1)))\n"
        "    asked = prompt(QUESTION, budget, len(batches))",
    ),
    Mutation(
        "peek.py",
        "a capture is answered by the store, whatever the working directory holds",
        "    try:\n        return store.read_raw(handle)\n    except FileNotFoundError:\n",
        "    found = Path(handle)\n    if found.is_file():\n        return found.read_bytes()\n"
        "    try:\n        return store.read_raw(handle)\n    except FileNotFoundError:\n",
    ),
    Mutation(
        "cli.py",
        "a file that cannot be read is reported, not raised at the user",
        "    except OSError as exc:  # the file itself cannot be read; there is no view",
        "    except ValueError as exc:  # the file itself cannot be read; there is no view",
    ),
    Mutation(
        "view.py",
        "an outline nobody chose falls to the ends of the file, not to an error",
        '    return ends_of(path), f"no model ({reason})"',
        "    raise RuntimeError(reason)",
    ),
    # -- Faz 7: the server, and everything stderr used to carry --------------
    Mutation(
        "server.py",
        "the note about a view travels inside the result, because there is no stderr",
        '    return f"{text}\\n\\n{note}" if text else note',
        "    return text if text else note",
    ),
    Mutation(
        "view.py",
        "one note serves both front ends, so neither can drift from the other",
        '        f" · {who} · {meta.duration_s:.1f}s"',
        '        f" · {meta.duration_s:.1f}s"',
    ),
    Mutation(
        "server.py",
        "a command line written by a client is a command line, pipes and all",
        "        capture = run_command([command], shell=True, timeout=timeout)",
        "        capture = run_command([command], shell=False, timeout=timeout)",
    ),
    Mutation(
        "server.py",
        "a file that cannot be read comes back as a sentence, not as a stack",
        "    except OSError as exc:  # the file cannot be read; there is no view to give\n"
        '        return f"sift: {exc}"\n',
        "    except OSError:  # the file cannot be read; there is no view to give\n"
        "        raise\n",
    ),
    Mutation(
        "server.py",
        "a command that cannot even be started comes back as a sentence too",
        "    except OSError as exc:\n"
        '        return f"sift: {exc}"\n'
        "    view, who = best_view(capture)\n",
        "    except OSError:\n"
        "        raise\n"
        "    view, who = best_view(capture)\n",
    ),
    Mutation(
        "server.py",
        "every tool on offer is named in the instructions the calling model reads",
        '    name="peek",',
        '    name="slice",',
    ),
    # -- Faz 8: what a view is allowed to cost ------------------------------
    Mutation(
        "distill.py",
        "a budget is divided between the asks, not repeated to each of them",
        "    each = max(1, budget // asks)",
        "    each = budget",
    ),
    Mutation(
        "distill.py",
        "a share of the budget never falls to nothing",
        "    each = max(1, budget // asks)",
        "    each = budget // asks",
    ),
    Mutation(
        "distill.py",
        "the budget reaches the model rather than only the docstring",
        '    share = ceiling(budget, asks) if budget is not None else ""',
        '    share = ""',
    ),
    Mutation(
        "distill.py",
        "every prompt ends with the one way of answering",
        "    return question + share + ANSWER_FORMAT",
        "    return question + share",
    ),
    Mutation(
        "distill.py",
        "an answer longer than the budget is handed back",
        "    if budget is not None and len(chosen) > budget:",
        "    if False:",
    ),
    Mutation(
        "distill.py",
        "the second pass is shown the lines it chose, with the numbers they had",
        "        shortlist = [(number, lines[number - 1]) for number in sorted(chosen)]",
        "        shortlist = list(enumerate(sorted(lines[n - 1] for n in chosen), 1))",
    ),
    Mutation(
        "distill.py",
        "the second pass asks a different question from the first",
        "        asked = prompt(question + NARROWING, budget, len(batches))",
        "        asked = prompt(question, budget, len(batches))",
    ),
    Mutation(
        "distill.py",
        "narrowing can drop a line and can never add one",
        "                kept |= read_numbers(answer.text, len(lines)) & chosen",
        "                kept |= read_numbers(answer.text, len(lines))",
    ),
    Mutation(
        "distill.py",
        "a round nobody answered leaves the answer before it standing",
        "        if not kept or len(kept) >= len(chosen):",
        "        if len(kept) >= len(chosen):",
    ),
    Mutation(
        "distill.py",
        "narrowing stops once it stops shortening anything",
        "        if not kept or len(kept) >= len(chosen):",
        "        if not kept:",
    ),
    Mutation(
        "distill.py",
        "an answer is handed back a fixed number of times and no more",
        "    for _ in range(NARROW_ROUNDS):",
        "    while True:",
    ),
    Mutation(
        "outline.py",
        "an outline is given the budget this module states, not the one distilling uses",
        "    return select(read(path), QUESTION, str(path), bridge, budget=BUDGET)",
        "    return select(read(path), QUESTION, str(path), bridge, budget=None)",
    ),
    Mutation(
        "view.py",
        "the bill is for the view, against what the capture would have cost",
        "            raw_bytes=capture.meta.byte_count,",
        "            raw_bytes=len(view.text.encode(\"utf-8\")),",
    ),
    Mutation(
        "view.py",
        "what is written down is the size of the view that was handed over",
        '            shown_bytes=len(view.text.encode("utf-8")),',
        "            shown_bytes=capture.meta.byte_count,",
    ),
    Mutation(
        "store.py",
        "bookkeeping that cannot be written costs the report and nothing else",
        "    with contextlib.suppress(OSError):",
        "    if True:",
    ),
    Mutation(
        "store.py",
        "a capture nobody viewed is left out rather than counted as free",
        "        found = load_saving(meta.handle)\n"
        "        if found is not None:\n"
        "            pairs.append((meta, found))",
        "        found = load_saving(meta.handle)\n"
        "        if found is None:\n"
        "            found = Saving(meta.handle, meta.byte_count, 0, 0, 0, None, 0)\n"
        "        pairs.append((meta, found))",
    ),
    Mutation(
        "cli.py",
        "the report adds up the bytes the views actually cost",
        "        shown += saving.shown_bytes",
        "        shown += 0",
    ),
    # -- Faz 8: asking at once, and saying when an answer never came --------
    Mutation(
        "distill.py",
        "the pieces of one capture are asked about at the same time",
        "    if len(batches) == 1:",
        "    if True:  # noqa: SIM108",
    ),
    Mutation(
        "distill.py",
        "how many are asked at once is what the caller asked for",
        "    with ThreadPoolExecutor(max_workers=min(workers(), len(batches))) as pool:",
        "    with ThreadPoolExecutor(max_workers=1) as pool:",
    ),
    Mutation(
        "distill.py",
        "how many at once never falls below one",
        'return max(1, int(written)) if written.isdigit() else WORKERS',
        'return int(written) if written.isdigit() else WORKERS',
    ),
    Mutation(
        "distill.py",
        "a question that came back with nothing is counted",
        "            unanswered += 1",
        "            unanswered += 0",
    ),
    Mutation(
        "distill.py",
        "the count of silent questions leaves the function it was counted in",
        "        unanswered=unanswered,",
        "        unanswered=0,",
    ),
    Mutation(
        "view.py",
        "the reader is told when part of the capture was never looked at",
        '        f" · {who} · {meta.duration_s:.1f}s" + silence(view)',
        '        f" · {who} · {meta.duration_s:.1f}s"',
    ),
    Mutation(
        "view.py",
        "silence is only reported when there was some",
        "    if not view.unanswered:\n        return \"\"",
        "    if True:\n        return \"\"",
    ),
    Mutation(
        "view.py",
        "the bill keeps the questions that came back with nothing",
        "            unanswered=view.unanswered,",
        "            unanswered=0,",
    ),
    # -- Faz 8: what the measurement may and may not blame ------------------
    Mutation(
        "test/budget.py",
        "a sample nobody answered for is left out of the row rather than scored",
        "    if view is None or view.unanswered:",
        "    if view is None:",
    ),
    Mutation(
        "test/budget.py",
        "the row counts the samples it was actually able to use",
        "    row.counted += 1",
        "    row.counted += 0",
    ),
    Mutation(
        "test/budget.py",
        "a line lost with and without a ceiling is not charged to the ceiling",
        "    cost = [line for line in default.missed if line not in without]",
        "    cost = list(default.missed)",
    ),
    Mutation(
        "test/budget.py",
        "with no unbounded row to compare against, every miss is the ceiling's",
        "        return list(default.missed), []",
        "        return [], []",
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


def main(argv: list[str] | None = None) -> int:
    """Every mutation, or only the ones whose rule contains the given words.

        python test/mutations.py                 # all of them
        python test/mutations.py numbering       # while fixing one escape

    The filter is for the minutes between finding an escape and fixing it. A
    filtered run is not a passing battery, and it says so at the end.
    """
    words = " ".join(argv if argv is not None else sys.argv[1:]).strip().lower()
    chosen = [m for m in MUTATIONS if words in m.rule.lower()]
    if not chosen:
        print(f"No mutation mentions {words!r}.")
        return 2

    code, tail = _run_suite()
    if code != 0:
        print(f"Baseline is not green ({tail}). Fix that first -- until then every")
        print("mutation would look caught for the wrong reason.")
        return 2
    print(f"baseline  {tail}\n")

    escaped: list[Mutation] = []
    for mutation in chosen:
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

    print(f"\n{len(chosen) - len(escaped)}/{len(chosen)} caught")
    if words:
        print(f"(only the {len(chosen)} mutations mentioning {words!r} were run)")
    if escaped:
        print("An escaped mutation means that rule is unguarded, not that it is unimportant.")
    return 1 if escaped else 0


if __name__ == "__main__":
    raise SystemExit(main())
