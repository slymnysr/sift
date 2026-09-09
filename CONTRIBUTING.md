# Contributing

The unusual things about this repository are worth knowing before you spend an
hour on it. None of them are preferences; each one is there because something
went wrong without it.

## Two languages, on purpose

**The notes are in Turkish. The code, the comments and the tests are in
English.** `notlar/`, `tanitim/` and `gelistirme/` are written for the person
whose project this is; everything a stranger reads while working — module
docstrings, comments, test names, commit subjects' meaning — is in English.

You do not need Turkish to contribute. Read `README.md` and the docstrings; they
are the design document.

## Three rules that do not bend

Every change is measured against these. A pull request that improves something
by weakening one of them will be declined, and the reason will be this list.

1. **Nothing shown is invented.** The model returns line numbers. Text always
   comes from the local file, byte for byte.
2. **Nothing is thrown away.** `peek` returns the raw capture. Every gap says
   how many lines it stands for.
3. **Nothing can break the command.** No key, no network, a nonsense reply, a
   bug in the distiller — each falls back to something that needs none of them.
   The command still runs, and its exit code is still its own.

## Every rule gets a mutation

A green test suite says the tests did not object to this version of the code. It
does not say they would object to a worse one. Twice in this project a test
passed while proving nothing, and both times looked exactly like the tests
around them.

So `test/mutations.py` breaks each rule deliberately, one at a time, and the
suite has to notice:

```bash
uv run python test/mutations.py                 # all of them, ~3.5 hours
uv run python test/mutations.py "some words"    # only the rules that mention them
```

**A change that adds a rule adds a line there.** If your mutation escapes, the
rule is unguarded — that is a finding, not a formality, and the fix is usually a
test rather than an argument.

Three times during this project the battery found that a *test* proved nothing:
a command that finished before the thing being tested happened, a query that
matched itself, an input too small to reach the branch. Expect it to find yours.

If a rule cannot be broken from here — a Windows-only path, say — do not add a
mutation that will escape every run. Say in a comment which leg of CI guards it.

## Running things

```bash
uv sync --all-extras --dev
uv run pytest -q                 # about a minute
uv run ruff check .              # must be clean
uv run python test/budget.py     # what a ceiling costs, against the corpus (spends requests)
uv run python test/kazanc.py     # what a view saves, by the endpoint's own count
```

The suite reaches no network and finds no key: `test/conftest.py` moves `HOME`,
deletes the key variables and sets `SIFT_NO_MODEL=1`. That is not tidiness —
before it existed, tests were spending the developer's own quota and one of them
swept the real capture store.

The measurement scripts do spend requests, which is why they are scripts and not
tests.

## Numbers

**Do not write a number you did not measure.** Not in the README, not in a
comment, not in a note. Where a number appears, say what measured it: the
endpoint's own token count, this tool's arithmetic over bytes it holds, a run of
`test/budget.py` against the corpus.

Bytes divided by four is not a token count. This tool is pointed at Japanese, at
Turkish, at base64 and at stack traces, where that rule of thumb is wrong by a
factor rather than a margin — and `stats` refuses it explicitly.

## Commits and phases

Work lands one phase at a time: code, tests, a mutation, a note in the matching
folder, and one commit. A commit message here says *what was wrong and why the
change is the answer* — not what the diff already shows.

`notlar/` is the tool's own history, `tanitim/` is about being findable,
`gelistirme/` is about being better. A phase that decided **not** to do
something gets a note too, with the measurement that decided it.

## Reporting

Bugs and ideas: <https://github.com/slymnysr/sift/issues>.
Anything security-shaped: `SECURITY.md`.
