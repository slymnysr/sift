# The corpus

Real-shaped output from real toolchains, in the languages people actually work
in. It exists to answer one question with a number instead of a claim: does
`sift` choose as well in Vietnamese, Hebrew and Swahili as it does in English?

Nothing in `src/` knows this folder is here. That is the point. If choosing
required a list of languages, adding a sample in a language nobody thought of
would break something — and adding one is how you find out.

## What a sample is

Two files with the same stem:

    <name>.txt     the output of a command, byte for byte
    <name>.json    what is known about it

The labels:

| field       | meaning                                                       |
|-------------|---------------------------------------------------------------|
| `tool`      | the program that wrote it                                     |
| `language`  | the human language in it, ISO 639-1                           |
| `script`    | `latin`, `cyrillic`, `arabic`, `devanagari`, `cjk`, `hebrew`  |
| `failed`    | whether the run ended badly                                   |
| `lines`     | how many lines it has                                         |
| `must_show` | the lines a view is wrong without                             |
| `noise`     | ranges that could all be folded away and cost nothing         |
| `note`      | why this sample is in the corpus                              |

A line in neither list is **context**: helpful, not required, not penalised.

## When a line is required

> A line is required only if a person could not reach the right conclusion
> without it.

That rule is narrow on purpose. It is tempting to mark the whole error block,
but demanding that an underline, a `|`, a bare `Failures:` header or an
interactive `Enter file name:` prompt be shown does not make the measurement
stricter — it makes it wrong, and a wrong ruler flatters nothing. Marked lines
are the ones that carry the information: the message, the location, the values,
the final result.

Fifteen labels were corrected this way after the first measurement, and it is
worth being clear about why that is not cheating: the rule was applied to every
sample at once, including samples that were already scoring full marks, and it
was applied to the lines rather than to the scores.

## Reading the files

Read them as **bytes**, then decode. `read_text()` turns on universal newlines,
which rewrites every carriage return into a newline. `ansi-progress.txt`
contains a progress bar that redraws itself six times; read as text it grows six
lines that were never written and every label below them points somewhere else.
`test/korpus_reader.py` does this correctly, and `sift` reads captures as bytes
for the same reason.

## Adding a sample

Write the two files by hand, or copy real output you have. Then:

    uv run pytest test/test_korpus.py      # is it well formed?
    uv run python test/languages.py NAME   # how well is it chosen? (needs a key)

The first runs everywhere and on every commit. The second needs a model and is
run on purpose.

## What is here

22 samples · 19 human languages · 6 scripts · 22 toolchains · 3 of them runs
that succeeded, because a tool that only works when something is broken is not
finished.
