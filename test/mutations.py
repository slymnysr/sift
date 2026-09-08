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

import contextlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src" / "sift"


# Where a mutation is written down while it is applied. `finally` undoes every
# mutation this process applies, and that is enough right up until the process
# is not asked politely: a SIGKILL, a machine that reboots, a terminal that
# takes its children with it. None of those run `finally`, and what is left
# behind is a source file with a rule deliberately broken in it -- which the
# next test run reports as a failure somewhere else entirely, or worse, does not
# report at all.
#
# So the intent is written to disk before it is carried out. The next run finds
# it and undoes it before doing anything else. It is one small file and it is
# only ever present for the seconds a suite takes.
JOURNAL = ROOT / "test" / ".mutating.json"

# How the suite is told that the break it is about to run into is deliberate.
#
# `conftest.py` repairs a leftover mutation before every run, which is exactly
# wrong for the one run that wants the mutation there. The note on disk cannot
# tell those two apart -- it is identical in both -- so the difference is said
# out of band, by the process that knows: this one, while it is still alive to
# undo its own work.
MUTATING = "SIFT_MUTATING"


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
        "        end = min(end, first + total - 1)",
        "        end = end",
    ),
    Mutation(
        "distill.py",
        "there is no line before the first one",
        "        start = max(start, first)",
        "        start = start",
    ),
    Mutation(
        "distill.py",
        "every piece is numbered as part of the whole capture",
        "    batches = _batches(list(enumerate(lines, first)))",
        "    batches = _batches([(1, line) for line in lines])",
    ),
    Mutation(
        "distill.py",
        "the numbering starts where the caller said it starts",
        "    batches = _batches(list(enumerate(lines, first)))",
        "    batches = _batches(list(enumerate(lines, 1)))",
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
        "    if not chosen and not always:\n        return None\n",
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
        "    if previous_end < last:",
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
        "        text=render(lines, chosen, handle, first),",
        "        text=render(lines, chosen, handle, first) + answer.text,",
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
        '        reason = bridge.last_error or "no lines chosen"\n'
        "    except Exception as exc:  # a bug here must not cost the caller their output",
        '        reason = bridge.last_error or "no lines chosen"\n'
        "    except ValueError as exc:  # a bug here must not cost the caller their output",
    ),
    Mutation(
        "cli.py",
        "a command that cannot be run is reported, not raised at the user",
        "        capture = run(args, timeout=timeout, shell=shell, cwd=where)\n"
        "    except OSError as exc:\n"
        '        print(f"sift: {exc}", file=sys.stderr)\n'
        "        return CANNOT_RUN\n",
        "        capture = run(args, timeout=timeout, shell=shell, cwd=where)\n"
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
        "        _show(capture, budget, keep)\n"
        "    except Exception as exc:  # the view is optional; the output is not",
        "        _show(capture, budget, keep)\n"
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
        '    found = text.split("\\n")',
        "    found = text.splitlines()",
    ),
    Mutation(
        "lines.py",
        "a trailing newline ends the last line rather than starting another",
        '    if found[-1] == "":\n',
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
        "        read(path),\n        QUESTION,",
        "        [str(path), *read(path)],\n        QUESTION,",
    ),
    Mutation(
        "distill.py",
        "the question put to the model is the one the caller asked",
        "    batches = _batches(list(enumerate(lines, first)))\n"
        "    asked = prompt(question, budget, len(batches))",
        "    batches = _batches(list(enumerate(lines, first)))\n"
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
        "        view, who = best_outline(path, budget, keep)\n"
        "    except OSError as exc:  # the file itself cannot be read; there is no view",
        "        view, who = best_outline(path, budget, keep)\n"
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
        "        capture = run_command([command], shell=True, timeout=timeout, cwd=cwd)",
        "        capture = run_command([command], shell=False, timeout=timeout, cwd=cwd)",
    ),
    Mutation(
        "server.py",
        "a file that cannot be read comes back as a sentence, not as a stack",
        "        view, who = best_outline(path, budget, keep)\n"
        "    except OSError as exc:  # the file cannot be read; there is no view to give\n"
        '        return f"sift: {exc}"\n',
        "        view, who = best_outline(path, budget, keep)\n"
        "    except OSError:  # the file cannot be read; there is no view to give\n"
        "        raise\n",
    ),
    Mutation(
        "server.py",
        "a command that cannot even be started comes back as a sentence too",
        "    except OSError as exc:\n"
        '        return f"sift: {exc}"\n'
        "    view, who = best_view(capture, BUDGET if budget is None else budget, keep)\n",
        "    except OSError:\n        raise\n    view, who = best_view(capture)\n",
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
        "        shortlist = [(number, lines[number - first]) for number in sorted(chosen)]",
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
        "                kept |= read_numbers(answer.text, len(lines), first) & chosen",
        "                kept |= read_numbers(answer.text, len(lines), first)",
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
        "        budget=BUDGET if budget is None else budget,",
        "        budget=budget,",
    ),
    Mutation(
        "view.py",
        "the bill is for the view, against what the capture would have cost",
        "            raw_bytes=capture.meta.byte_count,",
        '            raw_bytes=len(view.text.encode("utf-8")),',
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
        "    with contextlib.suppress(OSError):\n        view_path(saving.handle).write_text(",
        "    if True:\n        view_path(saving.handle).write_text(",
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
        "return max(1, int(written)) if written.isdigit() else WORKERS",
        "return int(written) if written.isdigit() else WORKERS",
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
        '    if not view.unanswered:\n        return ""',
        '    if True:\n        return ""',
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
    # -- Faz 20: when a line is not a unit ------------------------------------
    Mutation(
        "records.py",
        "a record is a slice of the source, never a value written back",
        "        found.append(text[at:end])",
        "        found.append(json.dumps(json.loads(text[at:end])))",
    ),
    Mutation(
        "records.py",
        "a document that goes on after the array is not an array",
        "    if _past_space(text, at + 1) != len(text):",
        "    if False:",
    ),
    Mutation(
        "records.py",
        "one record is not a choice between records",
        "FEWEST = 2",
        "FEWEST = 1",
    ),
    Mutation(
        "distill.py",
        "a gap says what it is counting",
        '    word = unit if count == 1 else unit + "s"',
        '    word = "line" if count == 1 else "lines"',
    ),
    # -- Faz 21: the only thing here that deletes ----------------------------
    Mutation(
        "store.py",
        "a run still marked running is never swept",
        "        if running_path(handle).is_file():",
        "        if False:",
    ),
    Mutation(
        "store.py",
        "a capture whose age is unknown is not deleted on a guess",
        "        if ended is None or ended > cut:",
        "        if ended is not None and ended > cut:",
    ),
    Mutation(
        "store.py",
        "what a removed capture ran is removed with it",
        '        stones[handle] = {"removed_at": now(), "byte_count": size}',
        '        stones[handle] = {"removed_at": now(), "byte_count": size,'
        ' "command": list(meta.command) if meta else []}',
    ),
    Mutation(
        "peek.py",
        "a swept handle is answered differently from one that never existed",
        "        if removed is not None:",
        "        if False:",
    ),
    # -- Faz 22: the same question, asked twice ------------------------------
    Mutation(
        "distill.py",
        "an answer already given is not bought a second time",
        "    if remembered is not None:",
        "    if False:",
    ),
    Mutation(
        "answers.py",
        "the question is part of what an answer is an answer to",
        '    seed = "\\x00".join([text, question, repr(budget), repr(first)])',
        '    seed = "\\x00".join([text, repr(budget), repr(first)])',
    ),
    Mutation(
        "answers.py",
        "the ceiling is part of what an answer is an answer to",
        '    seed = "\\x00".join([text, question, repr(budget), repr(first)])',
        '    seed = "\\x00".join([text, question, repr(first)])',
    ),
    Mutation(
        "answers.py",
        "an answer is old when nothing wants it, not when it was written",
        "        os.utime(where(named))",
        "        pass",
    ),
    Mutation(
        "view.py",
        "a view that cost no question says it was remembered",
        '    return f"{name} (remembered)" if view.model and view.asks == 0 else name',
        "    return name",
    ),
    # -- Faz 9: a command left running ---------------------------------------
    Mutation(
        "background.py",
        "a pid this tool did not start is never signalled",
        "    if running.pid <= 1:\n        return False",
        "    if False:\n        return False",
    ),
    # The same rule, kept a second time and one layer down. Neither of these two
    # may be the only thing standing between a stale marker and `kill(-1)`, so
    # the battery breaks them separately: with either one gone the other still
    # holds, and what is caught is a test failing rather than the machine going
    # quiet. That property is the point, and it is only true if both are tested.
    Mutation(
        "background.py",
        "signalling refuses a pid that is a broadcast rather than a tree",
        "    if pid <= 1:\n        return\n",
        "    if False:\n        return\n",
    ),
    Mutation(
        "background.py",
        "signalling refuses a process group that is a broadcast",
        "            if group > 1:",
        "            if True:",
    ),
    Mutation(
        "background.py",
        "our supervisor leads its own session; a reused pid does not",
        "        return os.getpgid(running.pid) == running.pid",
        "        return True",
    ),
    Mutation(
        "background.py",
        "a supervisor that has exited is not still watching",
        "    if _unreaped(running.pid):\n        return False",
        "    if False:\n        return False",
    ),
    Mutation(
        "background.py",
        "a slice ends at the last newline that arrived",
        '    cut = fresh.rfind(b"\\n")',
        "    cut = len(fresh) - 1",
    ),
    Mutation(
        "background.py",
        "the numbering carries on from where the reader stopped",
        "    first = cursor.lines + 1",
        "    first = 1",
    ),
    Mutation(
        "background.py",
        "a reader is never handed the same line twice",
        "            source.seek(cursor.bytes)",
        "            source.seek(0)",
    ),
    Mutation(
        "background.py",
        "a run nobody could signal is closed rather than left open",
        "    return _close(running, sent)",
        "    return None",
    ),
    Mutation(
        "background.py",
        "a run that had already finished keeps the ending it had",
        "    if running is None:\n        return store.load(handle)",
        "    if running is None:\n        return None",
    ),
    Mutation(
        "background.py",
        "a launched run has a capture from the moment it has a handle",
        "    store.begin(handle).touch(exist_ok=True)",
        "    store.begin(handle)",
    ),
    Mutation(
        "watch.py",
        "the ending is written before the marker comes down",
        "    target = store.raw_path(handle)\n    store.finish(",
        "    target = store.raw_path(handle)\n"
        "    store.clear_running(handle)\n    store.finish(",
    ),
    Mutation(
        "watch.py",
        "a command that could not start is recorded, not left running",
        "        _record(handle, command, shell, cwd, started_at, _CANNOT_START)\n"
        "        return _CANNOT_START",
        "        return _CANNOT_START",
    ),
    Mutation(
        "watch.py",
        "the supervisor adds to a capture rather than starting it over",
        'open(target, "ab")',
        'open(target, "wb")',
    ),
    Mutation(
        "view.py",
        "nothing new is an answer, and it costs nothing to give",
        '    if not lines:\n        return View(handle, "", 0, 0, None, 0), "nothing new"',
        '    if False:\n        return View(handle, "", 0, 0, None, 0), "nothing new"',
    ),
    Mutation(
        "view.py",
        "lines a model read and chose none of are folded, not replaced",
        "        if bridge.last_error is None:",
        "        if False:",
    ),
    Mutation(
        "view.py",
        "a supervisor that is gone is called lost, not running",
        '        return "running" if alive(running) else "lost"',
        '        return "running"',
    ),
    Mutation(
        "view.py",
        "a follow reports the numbers the capture uses",
        "    last = first + view.total - 1",
        "    last = view.total",
    ),
    Mutation(
        "fallback.py",
        "the ends of a slice are numbered where the slice sits",
        "    chosen = {number + first - 1 for number in ends(total, head=HEAD, tail=tail)}",
        "    chosen = ends(total, head=HEAD, tail=tail)",
    ),
    Mutation(
        "cli.py",
        "a background run refuses a timeout rather than dropping it",
        "    if timeout is not None:\n        print(\n"
        '            "sift: --background and --timeout do not go together: nothing is waiting"',
        "    if False:\n        print(\n"
        '            "sift: --background and --timeout do not go together: nothing is waiting"',
    ),
    Mutation(
        "cli.py",
        "what is still running is listed",
        "    for running in store.started():",
        "    for running in []:",
    ),
    # -- Faz 10: what leaves the machine --------------------------------------
    Mutation(
        "privacy.py",
        "a credential is replaced before the question is sent",
        "    if not masking_on():\n        return text",
        "    if True:\n        return text",
    ),
    Mutation(
        "privacy.py",
        "masking is on unless it is switched off",
        'return (os.environ.get("SIFT_MASK") or "1").strip().lower() not in _NO',
        'return (os.environ.get("SIFT_MASK") or "0").strip().lower() not in _NO',
    ),
    Mutation(
        "privacy.py",
        "a switch that says do not send is obeyed",
        'return (os.environ.get("SIFT_NO_MODEL") or "").strip().lower() in _NO',
        "return True",
    ),
    Mutation(
        "privacy.py",
        "the surrounding text survives so the reader can see what was hidden",
        "    return whole[:cut] + REDACTED + whole[cut + len(value) :]",
        "    return REDACTED",
    ),
    Mutation(
        "distill.py",
        "the text a model is shown is masked",
        "        safe = mask(line)",
        "        safe = line",
    ),
    Mutation(
        "distill.py",
        "a secret is masked before the line is shortened",
        "        safe = mask(line)\n"
        '        shown = safe if len(safe) <= cap else safe[:cap] + " …"',
        '        cut = line if len(line) <= cap else line[:cap] + " …"\n'
        "        shown = mask(cut)",
    ),
    Mutation(
        "model.py",
        "nothing is sent when sending is switched off",
        "        if not sending_on():",
        "        if False:",
    ),
    # -- Faz 11: the release ---------------------------------------------------
    Mutation(
        ".github/workflows/release.yml",
        "publishing happens on a tag and nowhere else",
        '    tags: ["v*"]',
        "    branches: [main]",
    ),
    Mutation(
        "__init__.py",
        "the published version is the one the package reports",
        '__version__ = "1.0.0"',
        '__version__ = "0.9.0"',
    ),
    # -- Faz 12: the caller's own say ------------------------------------------
    Mutation(
        "distill.py",
        "a line the caller asked for is shown",
        "    chosen |= always",
        "    chosen |= set()",
    ),
    Mutation(
        "distill.py",
        "a pattern that matched is an answer even when nobody replied",
        "    if not chosen and not always:",
        "    if not chosen:",
    ),
    Mutation(
        "distill.py",
        "a pattern that will not compile is searched for as text",
        "        return {n for n, line in enumerate(lines, first) if keep in line}",
        "        return set()",
    ),
    Mutation(
        "distill.py",
        "a kept pattern is looked for anywhere in the line",
        "    return {n for n, line in enumerate(lines, first) if found.search(line)}",
        "    return {n for n, line in enumerate(lines, first) if found.fullmatch(line)}",
    ),
    Mutation(
        "cli.py",
        "the pattern the caller typed is the pattern that is used",
        '        elif args[0] == "--keep" and len(args) > 1:\n            keep = args[1]',
        '        elif args[0] == "--keep" and len(args) > 1:\n            keep = None',
    ),
    Mutation(
        "cli.py",
        "a command runs where the caller said",
        '        elif args[0] == "--cwd" and len(args) > 1:\n            where = args[1]',
        '        elif args[0] == "--cwd" and len(args) > 1:\n            where = None',
    ),
    # -- Faz 13: a file somebody else produced ---------------------------------
    Mutation(
        "digest.py",
        "a digest asks what happened, not what is declared",
        "        QUESTION,",
        '        "",',
    ),
    Mutation(
        "digest.py",
        "a digest is handled by its path, so peek takes it back",
        "        str(path),\n        bridge,",
        '        "",\n        bridge,',
    ),
    Mutation(
        "view.py",
        "a bug in the digester costs the view and nothing else",
        "    except Exception as exc:  # a bug here must not cost the caller their file",
        "    except ValueError as exc:  # a bug here must not cost the caller their file",
    ),
    # -- Faz 14: the way into a gap --------------------------------------------
    Mutation(
        "peek.py",
        "a search shows the lines around what it matched",
        "        nearby = set(range(max(first, hit - around), min(last, hit + around) + 1))",
        "        nearby = {hit}",
    ),
    Mutation(
        "peek.py",
        "a search that finds nothing returns nothing",
        "    if not chosen:\n"
        '        return Peek(handle, "", first, first, total, len(raw), matched=0)',
        "    if False:\n"
        '        return Peek(handle, "", first, first, total, len(raw), matched=0)',
    ),
    Mutation(
        "peek.py",
        "a pattern that will not compile is searched for as text",
        "        return [n for n in range(first, last + 1) if grep in lines[n - 1]]",
        "        return []",
    ),
    Mutation(
        "peek.py",
        "a search is capped, so a pattern matching everything cannot answer with everything",
        "        if len(chosen | nearby) > cap and chosen:\n            break",
        "        if False:\n            break",
    ),
    Mutation(
        "view.py",
        "a search says how many lines matched, not only how many it shows",
        '    return f"{where} · {found.matched:,} {line} matched"',
        "    return where",
    ),
    # -- Faz 15: several at once -----------------------------------------------
    Mutation(
        "distill.py",
        "every ask passes through the one ceiling",
        "    gate.acquire()",
        "    pass",
    ),
    Mutation(
        "many.py",
        "answers come back in the order the questions were asked",
        "        return list(pool.map(lambda job: job(), jobs))",
        "        return list(reversed(list(pool.map(lambda job: job(), jobs))))",
    ),
    Mutation(
        "background.py",
        "waiting ends as soon as something is said",
        "        if unread(handle)[0]:\n            return True",
        "        if False:\n            return True",
    ),
    Mutation(
        "background.py",
        "a run that has already finished is not waited for",
        "        if running is None or not alive(running):\n            return False",
        "        if False:\n            return False",
    ),
    Mutation(
        "view.py",
        "one unreadable file does not take the others with it",
        "            except OSError as exc:\n"
        '                return path, View(path, "", 0, 0, None, 0), f"unreadable ({exc})"',
        "            except OSError:\n                raise",
    ),
    Mutation(
        "cli.py",
        "following everything answers about every run",
        "    for one in running:\n        _follow([one.handle])",
        "    for one in running[:1]:\n        _follow([one.handle])",
    ),
    # -- Faz 16: what this machine already knows -------------------------------
    Mutation(
        "memory.py",
        "a command that has failed every time it was run here is named",
        "        return self.runs > 0 and self.failures == self.runs",
        "        return False",
    ),
    Mutation(
        "memory.py",
        "a memory narrows to what was asked about",
        "        if term and term not in written:\n            continue",
        "        if False:\n            continue",
    ),
    Mutation(
        "memory.py",
        "runs of the same command are counted together",
        "        seen.setdefault(written, []).append(meta)",
        "        seen[written] = [meta]",
    ),
    Mutation(
        "cli.py",
        "a memory with nothing in it says so rather than printing nothing",
        '        print(f"sift: nothing{where} matches that, out of '
        '{seen:,} runs still on disk.")',
        "        pass",
    ),
    # -- Faz 17: tools that answer without opening the file --------------------
    Mutation(
        "tools.py",
        "whether a tool is here is asked of the machine, not assumed",
        "        return shutil.which(self.binary) is not None",
        "        return True",
    ),
    Mutation(
        "tools.py",
        "a name that is not one of them is refused",
        "    if known is None:\n        return None",
        "    if False:\n        return None",
    ),
    Mutation(
        "cli.py",
        "a tool this machine does not have says what it is called",
        "    if not known.here:\n        print(",
        "    if False:\n        print(",
    ),
    # -- Faz 18: the shell commands a client runs on its own -------------------
    Mutation(
        "hook.py",
        "everything is routed; nothing decides what looks noisy",
        '    if event.get("tool_name") != "Bash":\n        return PASS',
        "    if True:\n        return PASS",
    ),
    Mutation(
        "hook.py",
        "a bug underneath leaves the shell exactly as it was",
        "    except Exception:  # a bug here must not cost the caller their shell\n"
        "        return PASS",
        "    except ValueError:  # a bug here must not cost the caller their shell\n"
        "        return PASS",
    ),
    Mutation(
        "hook.py",
        "an event of a shape nobody expected is carried on from",
        "    if not isinstance(command, str) or not command.strip():\n        return PASS",
        "    if False:\n        return PASS",
    ),
    Mutation(
        "hook.py",
        "the gate can be switched off",
        "    if not wanted():\n        return PASS",
        "    if False:\n        return PASS",
    ),
]


def _run_suite() -> tuple[int, str]:
    """The suite, with the live call switched off so the network cannot decide this."""
    env = dict(os.environ)
    env.pop("SIFT_LIVE", None)
    env[MUTATING] = "1"  # the break below is on purpose; do not repair it
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


def note(mutation: Mutation, original: str, mutated: str) -> None:
    """Say what is about to be broken, before breaking it.

    Both whole texts are written down, not the two lines that differ. The reason
    is in `undo_leftover`, and it was learned by watching the first version of
    this fail.
    """
    JOURNAL.write_text(
        json.dumps(
            {
                "file": mutation.file,
                "rule": mutation.rule,
                "original": original,
                "mutated": mutated,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def forget() -> None:
    """The mutation is undone; the note about it is no longer true."""
    with contextlib.suppress(OSError):
        JOURNAL.unlink()


def undo_leftover() -> str | None:
    """Undo a mutation an earlier run was killed in the middle of.

    The file is compared whole, byte for byte, against the text this battery
    wrote. Nothing is searched for.

    The first version of this did search: it looked for the mutated string and
    refused to act unless it appeared exactly once. The very first mutation in
    this file turns a line into `proc.kill()` -- which `capture.py` already
    contained twice, in the two branches around it. So the count was three, the
    guard said no, the note was cleared, and the break stayed on disk. A recovery
    that quietly declines is worse than none, because it also destroys the record
    that would have let anyone else notice.

    Comparing whole texts cannot pick the wrong occurrence, and cannot fire on a
    file somebody has edited since: if it does not match what was written, this
    is not the situation it was left here for, and it does nothing.
    """
    try:
        left = json.loads(JOURNAL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    where = ROOT / left["file"] if "/" in left["file"] else SOURCE / left["file"]
    try:
        now = where.read_text(encoding="utf-8")
    except OSError:
        forget()
        return None

    if now == left["mutated"]:
        where.write_text(left["original"], encoding="utf-8")
        forget()
        return f"{left['file']}: {left['rule']}"

    forget()
    return None


def _slice_from(given: list[str]) -> tuple[list[str], int, int | None]:
    """Pull `--from N` and `--to M` out of the arguments, leaving the words.

    A range exists because a full battery takes the better part of an hour, and
    an hour is longer than some machines will leave a process alone. Splitting it
    into runs that each finish is the difference between a proof that gets made
    and one that keeps being interrupted at ninety per cent.
    """
    start, stop = 0, None
    rest: list[str] = []
    n = 0
    while n < len(given):
        word = given[n]
        if word in ("--from", "--to") and n + 1 < len(given):
            try:
                number = int(given[n + 1])
            except ValueError:
                rest.append(word)
                n += 1
                continue
            if word == "--from":
                start = number
            else:
                stop = number
            n += 2
            continue
        rest.append(word)
        n += 1
    return rest, start, stop


def main(argv: list[str] | None = None) -> int:
    """Every mutation, or only the ones whose rule contains the given words.

        python test/mutations.py                     # all of them
        python test/mutations.py numbering           # while fixing one escape
        python test/mutations.py --from 0 --to 20    # one slice of the whole

    The filter is for the minutes between finding an escape and fixing it. The
    range is for machines that will not leave an hour-long process alone. A run
    that was filtered or sliced is not a passing battery, and it says so at the
    end.
    """
    given = list(argv if argv is not None else sys.argv[1:])
    given, start, stop = _slice_from(given)
    words = " ".join(given).strip().lower()
    chosen = [m for m in MUTATIONS if words in m.rule.lower()]
    if not chosen:
        print(f"No mutation mentions {words!r}.")
        return 2

    whole = len(chosen)
    chosen = chosen[start:stop]
    if not chosen:
        print(f"No mutation in that range (there are {whole}).")
        return 2

    undone = undo_leftover()
    if undone:
        print(f"undone, left behind by a run that was killed -- {undone}\n")

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
        mutated = original.replace(mutation.before, mutation.after, 1)
        note(mutation, original, mutated)
        try:
            mutation.path.write_text(mutated, encoding="utf-8")
            code, tail = _run_suite()
        finally:
            mutation.path.write_text(original, encoding="utf-8")
            forget()
        if code == 0:
            print(f"ESCAPED    {mutation.rule}  ({tail})")
            escaped.append(mutation)
        else:
            print(f"caught     {mutation.rule}")

    print(f"\n{len(chosen) - len(escaped)}/{len(chosen)} caught")
    if words:
        print(f"(only the {len(chosen)} mutations mentioning {words!r} were run)")
    if (start, stop) != (0, None):
        print(f"(only {start}..{stop if stop is not None else whole} of {whole} were run)")
    if escaped:
        print("An escaped mutation means that rule is unguarded, not that it is unimportant.")
    return 1 if escaped else 0


if __name__ == "__main__":
    raise SystemExit(main())
