# sift

Runs your command, then gives the model only the lines that matter.

A test suite prints 4,000 lines and eleven of them are the failure. A build
prints a progress bar that redraws 900 times. An install lists every package it
touched. All of it lands in the conversation, and — this is the part that costs
— it is re-sent in full on every turn that follows.

`sift` runs the command itself, keeps every byte on disk, and hands the model a
view: the failures, the summary, the lines a reader would actually stop on. The
rest is marked, not deleted.

```
$ sift run -- pytest
FAILED test/test_auth.py::test_expired_token - assert 401 == 200
  ...
─ 3,914 lines not shown · sift peek 9f2c41ab for any of them ─
=== 1 failed, 212 passed in 18.4s ===
```

A file you did not produce — a log, a saved CI transcript, a crash dump — gets
the same treatment without being run:

```
$ sift digest ci-run-8812.log
2026-09-02T04:11:07 Building 214 targets
─ 38,904 lines not shown · sift peek ci-run-8812.log for any of them ─
ERROR: //src/parser:parse_test failed in 4.1s
─ 1,022 lines not shown · sift peek ci-run-8812.log for any of them ─
FAILED: 1 of 214 targets
```

A list is not read in lines. A JSON array written for a machine often has no
newlines at all, and there is nothing in a line of one worth choosing, so the
record becomes the unit and the same rules hold:

```
$ sift digest export.json
{"id": 3, "status": "failed", "error": "connection refused"}
─ 412 records not shown · sift peek export.json for the text they came from ─
{"id": 416, "status": "ok"}
```

The same question, asked about source code instead, is a table of
contents:

```
$ sift outline src/parser.rs
pub struct Parser {
pub fn parse(input: &str) -> Result<Ast, Error> {
─ 34 lines not shown · sift peek src/parser.rs for any of them ─
impl Iterator for Tokens {
```

And a command that does not end — a dev server, a log tail, a build you want to
keep working during — is started and then read a slice at a time:

```
$ sift run --background -- cargo build --release
9f2c41ab
$ sift follow 9f2c41ab
   warning: unused import: `std::fmt`
─ 212 lines not shown · sift peek 9f2c41ab for any of them ─
   error[E0308]: mismatched types
sift 9f2c41ab · running · new lines 1-247 · 2 shown · nemotron
$ sift follow 9f2c41ab          # only what has arrived since
$ sift follow --all --wait 30   # every run at once, holding for something new
$ sift stop 9f2c41ab            # ends it, and everything it started
```

Nothing is shown twice, and the numbers are the run's own: line 247 stays line
247 in `sift peek` for as long as the capture exists.

## What decides

A free model does. `sift` sends it the numbered lines and asks one question:
*which numbers matter?* It answers with numbers, and nothing else it says is
used — the text you read above is printed from the local capture, byte for byte.

That is the whole trick, and it is why this is not a summariser. A summariser
can be wrong about what a line said. `sift` cannot be: it never writes a line,
it only chooses one.

It also means language coverage is not a list. A model reads Turkish, Japanese,
Arabic and Hindi; it reads Rust, COBOL, Mojo and a language released last week.
Nothing here enumerates them, so nothing here can be missing one.

## Three rules

**Nothing shown is invented.** The judge returns line numbers. Text always comes
from the local file.

**Nothing is thrown away.** `sift peek <handle>` returns the raw capture,
unchanged. Every gap in a view says how many lines it covers.

**Nothing can break your command.** No API key, no network, an overloaded
endpoint, a nonsense reply, a bug in the distiller, or a decision that nothing
may leave this machine — every one of these falls back to rules that need none
of them. The command still runs; you still get its output; you get its exit
code.

## What leaves the machine

One thing: the text of a question. Before it is sent, anything credential-shaped
is replaced — tokens with a known prefix, JWTs, authorization headers, passwords
in connection strings, the body of a PEM block.

That costs you nothing to read. The model is only ever asked for line numbers,
and the lines are printed from your own file, so **a line masked on the way out
is still shown to you in full**.

Three switches:

```bash
SIFT_NO_MODEL=1   # never send anything; use the deterministic view
SIFT_MASK=0       # send unmasked
SIFT_CACHE=0      # ask again, even about text already answered
```

Masking is not complete and does not claim to be: a bare secret shaped like
nothing in particular gets through. `SIFT_NO_MODEL` is the one that guarantees.

The third is about not paying twice. An answer already given for exactly these
bytes and exactly this question is used again instead of bought again — and what
is kept is the numbers, never the view, so the text is still rendered from your
own file and the gap still names your own capture. A view that cost no request
says `(remembered)` where it would otherwise name the model.

Captured bytes never leave `$SIFT_HOME` (`~/.cache/sift` by default). Nothing is
uploaded, nothing is logged elsewhere, and removing a capture directory removes
everything that was ever kept about it.

They also never go away on their own. Nothing here sweeps, expires or tidies in
the background: `sift gc [DAYS]` is the only thing that deletes a capture, and
it deletes when you type it and not before. What it leaves is one line per
handle — when it went and how big it was, never the command — so that a gap
marker read a fortnight later gets *"removed on the 8th"* instead of the answer
it would give for a handle you made up.

## Commands

```
sift run [--timeout SECONDS] [--shell] [--background] [--cwd DIR]
         [--budget LINES] [--keep PATTERN] [--] COMMAND...
sift follow [HANDLE] [--all] [--wait N]
                          what a background run has said since you last looked
sift stop [HANDLE]        end it, and everything it started
sift outline PATH         what a file declares, without its bodies
sift digest PATH...       what is in files somebody else produced
sift peek HANDLE|PATH [FIRST] [LAST]
sift hook                 answer one shell-command event on stdin
sift tools                which dense tools this machine has
sift tool NAME [ARGS...]  run one of them, distilled
sift memory [TERM]        what has been run here before, and how it went
sift list [COUNT]         what is running, and what has been run
sift stats [COUNT]        what the shortening cost, and what it saved
sift gc [DAYS]            remove captures older than that, and say what went
```

Several paths given to `digest` are asked about at the same time, and `--all`
follows every running command in one go. Both are the same idea: the waiting is
the cost, so do it once. `--wait N` holds until a run actually says something
instead of answering that nothing has happened yet.

`sift hook` is the way to catch the shell commands a client runs on its own,
without a proxy: point the client's pre-tool hook at it and every shell command
comes here first. **Everything is routed** — nothing here guesses which commands
are worth catching, because a list of those is a list of tools in disguise and
how much a command prints is not knowable before it runs. Routing everything
costs nothing: a view of twelve lines is twelve lines. It fails open, so a bug
in it leaves your shell exactly as it was, and `SIFT_HOOK=0` switches it off.

`sift tool` runs one of three programs that answer a question *without opening
the file* — `sg` (ast-grep) for structural search, `diff` (difftastic) for a diff
that can tell a reindent from a change, `loc` (scc) for the size of a tree. Their
output is large by nature, which is exactly why they belong here. **No binaries
ship with this package**: `sift tools` says which of them this machine has and
what each is called, and installing one stays your decision.

`sift memory` asks no model at all. The question is counting — how often, how it
went, which command has never once worked here — and a model asked to count is
slower, costs a request and is sometimes wrong. The model decides what cannot be
computed, and nothing else.

`sift stats` says what the shortening saved and what it cost, and keeps those
two apart: the share is this tool's own arithmetic over bytes it holds, so it is
exact, while the cost is the endpoint's count of its own tokens, so it is
measured. A run the endpoint did not count is left out and said so, rather than
filled in with bytes divided by four.

`--keep PATTERN` shows every line matching it whatever else was chosen and
whatever the budget says. It is your pattern, not one this tool guessed at —
the only place a pattern decides anything here, and it decides nothing until
you type it. `--budget LINES` is the ceiling for one view.

## In an agent

The same answers are available over MCP, and that is where they pay most: a tool
result is re-sent on every turn that follows it, so a build log kept out of a
transcript goes on staying out of it.

```bash
pip install "sift-mcp[mcp]"
export SIFT_API_KEY=nvapi-...     # yours; see Installing
claude mcp add sift -- sift-mcp
```

Without a key the server starts and every tool that would need a model declines
with an explanation, so the agent falls back to its own shell rather than being
handed a worse answer it cannot tell apart from a good one.

Any client that speaks stdio will do — the command is `sift-mcp`. It offers
`run`, `follow`, `outline`, `digest`, `digest_many`, `tool` and `peek`. `list`
and `stats` are deliberately not offered: they would hand a model every command lately run on this machine,
including the ones it never asked about, and the person at a terminal already
has that access while a model connecting over a socket does not.

Because a client never sees stderr, the last line of every result says what you
are looking at: which handle, how the command ended, and whether a model chose
the lines or none could be reached.

## Installing

```bash
pip install sift-mcp            # the command line, no dependencies at all
pip install "sift-mcp[mcp]"     # and the MCP server
```

Python 3.12 or newer, and no dependencies for the command line.

### You need your own key

**This is not optional and it is not shipped.** `sift` asks a free NVIDIA model
which lines matter, and that key has to be yours — one cannot be bundled and one
cannot be shared. It is free, and it takes a minute:

1. Get a key at **<https://build.nvidia.com>**
2. Put it anywhere `sift` looks:

```bash
export SIFT_API_KEY=nvapi-...            # or NVIDIA_API_KEY
# or, once and for good:
mkdir -p ~/.config/nvidia && echo 'nvapi-...' > ~/.config/nvidia/api_key
```

Without it the two callers are answered differently, on purpose:

- **At a terminal** everything still runs — the command, the bytes, the exit
  code, the third rule — and a loud banner says no model chose these lines and
  that you are looking at the ends of the output.
- **Over MCP** the tools decline and say why, and tell the agent to use its own
  shell instead. A person can see a degraded view and judge it; a model is handed
  a short text with a footer it has no reason to distrust, and quietly worse is
  the one thing this will not do to a reader who cannot check.

If you *want* to run without a model, say so with `SIFT_NO_MODEL=1`. That is a
decision rather than an oversight, everything works, and nothing lectures you.

## How it was built

Twenty-four phases, each one closed before the next began, each with a note in
`notlar/` saying what was decided and what it cost. `notlar/00-PLAN.md` is the
arc, including the things that were deliberately not built and why.

The tests are in `test/`. Beside them is `test/mutations.py`, which breaks each
rule the code follows — 162 of them, one at a time — and checks that the suite
notices. A green suite says the tests did not object to *this* version of the
code, not that they would object to a worse one.

It also says what happens when that battery is interrupted, because it was: a
break left on disk survived every ordinary test run and took the machine down
six times before anybody looked. `test/conftest.py` repairs one now, and the
rule it was breaking is kept twice over, so that no single edit anywhere can
turn `sift stop` into a signal to everything you own. That is `notlar/19`.

## License

MIT.
