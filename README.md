# sift

<!-- mcp-name: io.github.slymnysr/sift -->

Runs your command, then gives the model only the lines that matter.

A test suite prints 4,000 lines and eleven of them are the failure. A build
prints a progress bar that redraws 900 times. An install lists every package it
touched. All of it lands in the context window, and — this is the part that
costs — it is re-sent in full on every turn that follows.

`sift` is an MCP server and a command line for that problem. It runs the command
itself, keeps every byte on disk, and hands the model a view: the failures, the
summary, the lines a reader would actually stop on. The rest is marked, not
deleted.

Two numbers, both measured, both reproducible from this repository. Running this
project's own test suite prints 652 lines — 21,392 tokens, as the model's own
tokenizer counts them. What comes back is 8 lines and 208 tokens: **99% fewer**
(`python test/kazanc.py`). Removing almost everything is the easy half. Over a
22-sample corpus of real build and test output, the default budget keeps **138
of the 140 lines a reader could not do without** (`python test/budget.py`).

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
SIFT_BASE_URL=... # ask your own endpoint instead, and no key is wanted
SIFT_MODELS=a,b   # which models to ask there, best first
SIFT_NO_MODEL=1   # never send anything; use the deterministic view
SIFT_MASK=0       # send unmasked
SIFT_CACHE=0      # ask again, even about text already answered
SIFT_EFFORT=low   # let the model think less, and lose some of what matters
SIFT_PATIENCE=0   # one quick pass only; do not wait out a busy hour
```

Masking is not complete and does not claim to be: a bare secret shaped like
nothing in particular gets through. `SIFT_NO_MODEL` is the one that guarantees.

The fourth is a measured trade and is off by default. Asked which lines matter
in a 404-line build, the model writes about 900 tokens of reasoning to produce a
twelve-token answer, and you wait 15 seconds for it. At `SIFT_EFFORT=low` the
same question takes 2.4 seconds — and over the corpus it loses 7.8% of the lines
a reader could not do without, in exactly the places this tool exists for: a
mainframe job's return code, a crash loop's diagnosis. Speed is available; it is
not the default, and the price is written down.

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
sift outline PATH|-       what a file declares, without its bodies
sift digest PATH...|-     what is in files somebody else produced
sift peek HANDLE|PATH [FIRST] [LAST]
sift hook                 answer one shell-command event on stdin
sift mcp                  speak the protocol on stdin, for a client
sift tools                which dense tools this machine has
sift tool NAME [ARGS...]  run one of them, distilled
sift memory [TERM]        what has been run here before, and how it went
sift list [COUNT]         what is running, and what has been run
sift stats [COUNT]        what the shortening cost, and what it saved
sift gc [DAYS]            remove captures older than that, and say what went
```

A path of `-` reads standard input, which is the other way somebody else's
output turns up:

```
$ journalctl -u nginx --since yesterday | sift digest -
Sep 08 04:11:07 nginx[2114]: worker process 2119 exited on signal 11
─ 8,204 lines not shown · sift peek 7c1a04e9 for any of them ─
Sep 09 01:02:55 nginx[2114]: signal 15 (SIGTERM) received, exiting
```

What arrives on a pipe has no path anybody could type again, so it is kept as a
capture of its own and the gap marker names that instead. The second rule is
why: a view that left lines out and pointed at a scratch file would be pointing
at nothing by the time somebody read it.

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

It is the part of this that pays most and the only part you have to turn on, so
it offers itself rather than waiting to be found:

```bash
sift hook --install      # says what it gives and what it costs, then asks
sift hook --uninstall    # and takes it back out
```

It writes one line into your client's settings, keeps a copy of the file as it
was, and touches nothing else that is in there. `sift run` mentions it once,
ever, and then stops.

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
uv tool install "sift-cli[mcp]"   # or pipx; see Installing
claude mcp add --scope user sift -- sift-mcp
```

The key is read from `~/.config/nvidia/api_key`, so it does not have to be in
the environment and does not have to be pasted anywhere. `--scope user` puts the
server in every project rather than the one you happen to be in.

Then **restart the client**. MCP servers are connected when a session starts, so
the session you ran that command in will not see this one.

Without a key the server starts and every tool that would need a model declines
with an explanation, so the agent falls back to its own shell rather than being
handed a worse answer it cannot tell apart from a good one.

Any client that speaks stdio will do. The command is `sift-mcp`, and `sift mcp`
starts the same server — one word for a client that would rather run the package
by its own name (`uvx --from "sift-cli[mcp]" sift-cli mcp`, which is what the MCP
registry entry says). It offers
`run`, `follow`, `outline`, `digest`, `digest_many`, `tool` and `peek`. `list`
and `stats` are deliberately not offered: they would hand a model every command lately run on this machine,
including the ones it never asked about, and the person at a terminal already
has that access while a model connecting over a socket does not.

Because a client never sees stderr, the last line of every result says what you
are looking at: which handle, how the command ended, and whether a model chose
the lines or none could be reached.

## Installing

```bash
uv tool install sift-cli            # the command line, no dependencies at all
uv tool install "sift-cli[mcp]"     # and the MCP server
```

`pipx install` does the same thing. Either puts `sift` and `sift-mcp` on your
PATH in an environment of their own, which is what you want for a command-line
tool: nothing here belongs in the Python you build with.

Plain `pip install sift-cli` works inside a virtualenv you have already
activated. It does **not** work against the system Python on Debian, Ubuntu, or
WSL — those ship a `EXTERNALLY-MANAGED` marker and pip refuses, by design:

```
error: externally-managed-environment
× This environment is externally managed
```

That refusal is right and the answer is not `--break-system-packages`. Use `uv
tool` or `pipx`.

The package is `sift-cli` and the commands are `sift` and `sift-mcp`. The names
differ because `sift-mcp` on PyPI belongs to somebody else's project — an
unrelated MCP server about authorising agent actions. Nothing here is theirs and
nothing there is this.

Python 3.12 or newer, and no dependencies for the command line.

### You need a model — a key, or one of your own

`sift` asks a model which lines matter. There are two ways to give it one and
you need exactly one of them.

#### A free key

**Not shipped, and not shareable.** The key has to be yours. It is free, and it
takes a minute:

1. Get a key at **<https://build.nvidia.com>**
2. Put it anywhere `sift` looks:

```bash
export SIFT_API_KEY=nvapi-...            # or NVIDIA_API_KEY
# or, once and for good:
mkdir -p ~/.config/nvidia && echo 'nvapi-...' > ~/.config/nvidia/api_key
```

#### Or a model of your own, and no key at all

Point `sift` somewhere and it asks there instead. Nothing about the question
changes; the endpoint is asked the ordinary OpenAI-shaped way, and no
`Authorization` header is sent when there is no key to put in it.

```bash
export SIFT_BASE_URL=http://localhost:11434/v1   # Ollama
export SIFT_MODELS=qwen3:8b                      # what to ask, best first
```

The same two lines fit llama.cpp (`--api`), vLLM, LM Studio, LocalAI, a company
gateway, or any other endpoint that speaks `POST /v1/chat/completions`.
`SIFT_MODELS` takes a comma-separated ladder and is asked in order.

An address you typed is treated as a decision: nothing warns you about a missing
key, and the MCP server does not decline. What that endpoint wants for
credentials is between you and it.

> Tested here as a shape rather than as a list: the suite proves that an
> endpoint of your own is asked, and asked without a key. Which local servers
> answer *well* is a question about the model you run, and the corpus in
> `test/budget.py` is how you can settle it for yours.

#### Without either of them

The two callers are answered differently, on purpose:

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
