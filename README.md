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

The same question, asked about a file instead of about a command, is a table of
contents:

```
$ sift outline src/parser.rs
pub struct Parser {
pub fn parse(input: &str) -> Result<Ast, Error> {
─ 34 lines not shown · sift peek src/parser.rs for any of them ─
impl Iterator for Tokens {
```

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
endpoint, a nonsense reply — every one of these falls back to rules that need
none of them. The command still runs; you still get its output.

## In an agent

The same three answers are available over MCP, and that is where they pay most:
a tool result is re-sent on every turn that follows it, so a build log kept out
of a transcript goes on staying out of it.

```bash
pip install -e ".[mcp]"        # from a clone; PyPI once the last phase lands
claude mcp add sift -- sift-mcp
```

Any client that speaks stdio will do -- the command is `sift-mcp`. It offers
`run`, `outline` and `peek`, and because a client never sees stderr, the last
line of every result says what you are looking at: which handle, how the command
ended, and whether a model chose the lines or none could be reached.

## Status

Early. Being built in phases; see `notlar/00-PLAN.md` for the arc and
`notlar/` for the decisions behind each one.

## License

MIT.
