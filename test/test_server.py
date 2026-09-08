"""Faz 7 -- the same three answers over a wire, to a reader with no eyes.

Two things change when the reader is a model instead of a person, and both are
ways of losing something quietly rather than loudly:

There is no stderr. Everything the command line writes beside the view -- which
handle this was, how the command ended, whether a model chose the lines at all
-- has nowhere to go unless it travels inside the result. A view that arrives
without it looks exactly like a view a model chose, and the caller has no way to
find out otherwise.

There is no exception either. A tool that raises hands the caller nothing, which
is the one outcome the third rule exists to prevent. So a file that cannot be
read comes back as a sentence, not as a stack.

Everything here runs with no key and no network, so what is measured is the
floor: what the server gives back when no model can be reached. What a model
adds is measured in `test/outlines.py`, live.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pytest
from mcp import Client, StdioServerParameters

from sift import server as s
from sift import store, view

MARKER = re.compile(r"^─ ([\d,]+) lines? not shown · sift peek (\S+) for any of them ─$")

OFFLINE = ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MODELS", "SIFT_BASE_URL")

TOOLS = {"run", "outline", "peek", "follow", "digest", "digest_many", "tool"}


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    """No key, no stored key, and a store of its own."""
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in OFFLINE:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def counting(tmp_path):
    """A command that prints 400 lines and then says it finished."""
    script = tmp_path / "say.py"
    script.write_text(
        "for i in range(1, 401):\n    print(i)\nprint('done')\n", encoding="utf-8"
    )
    return f'"{sys.executable}" "{script}"'


def _note(answer: str) -> str:
    """The last line, which is the one that says what the rest of it is."""
    return answer.strip().splitlines()[-1]


def _handle(answer: str) -> str:
    return _note(answer).split()[1]


def _shown(answer: str) -> list[str]:
    """The lines of the view itself: not the note, not the gap markers."""
    body = answer.strip().splitlines()[:-1]
    return [line for line in body if line and not MARKER.match(line)]


# -- the contract ------------------------------------------------------------


async def test_every_tool_answers_about_a_run_the_caller_started():
    """The line that decides what may be on offer, and it has not moved.

    `follow` joins the first three because it answers about one handle, and the
    only way to have that handle is to have started that run through `run`. It
    adds a promise about a command the caller already owns.

    `list` and `stats` are still not here, and not because they are unfinished.
    They would hand a model every command lately run on this machine, including
    the ones it never asked about -- a question about what leaves the machine
    rather than about what a caller is owed, so it waits for the phase that is
    about that.
    """
    tools = await s.server.list_tools()

    assert {tool.name for tool in tools} == TOOLS
    assert all(tool.description for tool in tools)


async def test_the_instructions_account_for_every_tool_on_offer():
    """The instructions are the only documentation the calling model reads.

    A tool nobody was told about is a tool nobody calls, so adding one without a
    word here is the same as not adding it.
    """
    tools = await s.server.list_tools()

    for tool in tools:
        assert f"`{tool.name}`" in s.INSTRUCTIONS


# -- what stderr used to carry ----------------------------------------------


def test_the_note_travels_inside_the_result(counting):
    answer = s.run(counting)

    assert _note(answer).startswith("sift ")
    assert "exit 0" in _note(answer)
    assert "401 lines" in _note(answer)


def test_the_caller_is_told_when_no_model_chose_the_lines(counting):
    """The difference the reader cannot see for themselves, and must be told."""
    answer = s.run(counting)

    assert "no model" in _note(answer)


def test_the_note_names_the_model_when_there_was_one(counting, monkeypatch):
    monkeypatch.setattr(
        view,
        "distill",
        lambda capture, bridge=None, budget=None, keep=None: view.View(
            capture.handle, "bir", 1, 9, "a-model", 1
        ),
    )
    answer = s.run(counting)

    assert "a-model" in _note(answer)
    assert "1/9 lines" in _note(answer)


def test_a_command_that_failed_says_so(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("import sys\nprint('bir')\nsys.exit(3)\n", encoding="utf-8")

    assert "exit 3" in _note(s.run(f'"{sys.executable}" "{script}"'))


# -- the promises the command line already makes -----------------------------


def test_no_line_in_a_result_was_invented(counting):
    answer = s.run(counting)
    kept = set(s.peek(_handle(answer)).splitlines())

    for line in _shown(answer):
        assert line in kept


def test_the_server_climbs_the_same_ladder_as_the_command_line(counting, monkeypatch):
    """The proof that this module holds no second copy of anything.

    Break the distiller in `view.py` -- the only place it is called from -- and
    the server has to fall back exactly as the terminal does. If it had its own
    ladder, this test would pass while the real one rotted.
    """

    def explode(capture, bridge=None, budget=None, keep=None):
        raise RuntimeError("damitici kirildi")

    monkeypatch.setattr(view, "distill", explode)
    answer = s.run(counting)

    assert "RuntimeError: damitici kirildi" in _note(answer)
    assert _shown(answer)


def test_the_loop_closes_from_a_result_back_to_the_bytes(counting):
    answer = s.run(counting)

    assert s.peek(_handle(answer), 200, 202).splitlines()[:3] == ["200", "201", "202"]


def test_an_outline_is_the_file_byte_for_byte(tmp_path):
    source = tmp_path / "kaynak"
    source.write_text(
        "def bir():\n    return 1\n\n\ndef iki():\n    return 2\n", encoding="utf-8"
    )
    answer = s.outline(str(source))

    for line in _shown(answer):
        assert line in source.read_text(encoding="utf-8").split("\n")


# -- nothing raises ----------------------------------------------------------


def test_a_file_that_cannot_be_read_is_said_rather_than_raised(tmp_path):
    answer = s.outline(str(tmp_path / "yok"))

    assert answer.startswith("sift: ")


def test_a_handle_that_never_existed_is_said_rather_than_raised():
    answer = s.peek("yokboyle")

    assert answer.startswith("sift: ")


def test_a_command_that_cannot_be_started_is_said_rather_than_raised(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("calistirilamadi")

    monkeypatch.setattr(s, "run_command", refuse)

    assert s.run("herhangi") == "sift: calistirilamadi"


# -- the package without the server package ----------------------------------

_BLOCK = (
    "import sys\n"
    "class NoMcp:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'mcp' or name.startswith('mcp.'):\n"
    "            raise ImportError('mcp is not installed')\n"
    "        return None\n"
    "sys.meta_path.insert(0, NoMcp())\n"
)


def _without_mcp(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _BLOCK + code],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_tool_still_works_for_someone_who_never_installed_mcp():
    """`pip install sift-cli` brings nothing with it, and has to keep working.

    The server is an extra. Someone who wants the command and not the protocol
    should not be made to carry a web framework to get it.
    """
    finished = _without_mcp("import sift, sift.cli, sift.view\nprint('ok')\n")

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout.strip() == "ok"


def test_and_the_test_above_would_have_noticed():
    """Teeth: the block has to be able to block, or the test above proves nothing.

    What comes out is also the second thing being checked. `pip install
    sift-cli` and then `claude mcp add` is an ordinary thing to do wrong, and
    what the client shows for it used to be a `ModuleNotFoundError` traceback
    pointing into somebody else's site-packages. A sentence naming the one
    command that fixes it is worth more than a stack that names the cause.
    """
    finished = _without_mcp("import sift.server\n")

    assert finished.returncode != 0
    assert 'pip install "sift-cli[mcp]"' in finished.stderr
    assert "Traceback" not in finished.stderr
    assert "`sift`) is already installed" in finished.stderr


# -- over the real transport -------------------------------------------------

SCRIPT = shutil.which("sift-mcp")


def _parameters(home) -> StdioServerParameters:
    env = {k: v for k, v in os.environ.items() if k not in OFFLINE}
    env["SIFT_HOME"] = str(home / "sift")
    return StdioServerParameters(
        command=SCRIPT or sys.executable,
        args=[] if SCRIPT else ["-m", "sift.server"],
        env=env,
    )


def _text(result) -> str:
    return "\n".join(b.text for b in result.content if b.type == "text")


async def test_the_installed_server_answers_over_stdio(tmp_path):
    """The one test that runs the packaged thing the way a client will.

    Every other test in this file imports the module. If the entry point, the
    packaging or an import is wrong, this is the only one that finds out.
    """
    async with Client(_parameters(tmp_path)) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}

    assert tools == TOOLS


async def test_a_real_client_can_run_and_then_recover_what_was_left_out(tmp_path, counting):
    async with Client(_parameters(tmp_path)) as client:
        answer = _text(await client.call_tool("run", {"command": counting}))
        back = _text(await client.call_tool("peek", {"handle": _handle(answer), "first": 200,
                                                     "last": 202}))

    assert "done" in answer
    assert "401 lines" in _note(answer)
    assert back.splitlines()[:3] == ["200", "201", "202"]


async def test_a_real_client_is_given_a_sentence_and_not_a_crash(tmp_path):
    async with Client(_parameters(tmp_path)) as client:
        answer = _text(await client.call_tool("outline", {"path": str(tmp_path / "yok")}))

    assert answer.startswith("sift: ")


def test_a_run_over_the_wire_is_billed_the_way_one_at_a_terminal_is(counting):
    """Faz 8's report counts both front ends or it is not about the tool.

    The bill is drawn in `view.py`, beside the ladder, so a client's run turns up
    in `sift stats` next to a person's without either front end being asked to
    remember. Neither of them mentions the store at all.
    """
    saving = store.load_saving(_handle(s.run(counting)))

    assert saving is not None
    assert saving.total == 401
    assert saving.shown_bytes < saving.raw_bytes
