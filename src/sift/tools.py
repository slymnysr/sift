"""Tools that answer a question without opening the file.

Three commands worth knowing about, and the reason they are here rather than
left to the caller: each of them replaces *reading*, which is the expensive
thing this project exists to avoid.

    ast-grep      where does this shape occur -- instead of opening the
                  candidates one by one to find out
    difftastic    what actually changed -- instead of a line diff that calls a
                  reindent a change and buries the one line that moved
    scc           how big is this tree -- instead of guessing, or listing it

Their output is large by nature, which is why they belong to `sift` at all: a
4,000-line structural search costs a screenful here and stays whole on disk.

**No binaries ship with this package.** The list below is a list of programs a
machine may or may not have, not a dependency. Nothing is downloaded, nothing is
installed behind anyone's back; if a tool is missing, this says so and says what
it is called, and the decision stays with the person whose machine it is.

The list is short and it is meant to stay short. It is not a table of languages
wearing a different hat -- those three entries are the same three whatever
language the project is written in, and a fourth would have to earn its place by
replacing reading too.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class Dense:
    """One program, what it replaces, and what it is called on a package manager."""

    name: str
    binary: str
    replaces: str
    known_as: str

    @property
    def here(self) -> bool:
        return shutil.which(self.binary) is not None


KNOWN: tuple[Dense, ...] = (
    Dense(
        name="sg",
        binary="ast-grep",
        replaces="opening candidate files to find where a shape occurs",
        known_as="ast-grep",
    ),
    Dense(
        name="diff",
        binary="difft",
        replaces="a line diff that cannot tell a reindent from a change",
        known_as="difftastic",
    ),
    Dense(
        name="loc",
        binary="scc",
        replaces="guessing how large a tree is, or listing it to find out",
        known_as="scc",
    ),
)

BY_NAME = {one.name: one for one in KNOWN}


def command_for(name: str, args: list[str]) -> list[str] | None:
    """The command line for one of these, or nothing if this is not one of them."""
    known = BY_NAME.get(name)
    if known is None:
        return None
    return [known.binary, *args]
