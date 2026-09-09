"""Faz 0 -- the skeleton stands up.

A test that only imports looks like a formality, and mostly it is. It earns its
place by failing loudly on the two setup mistakes that are otherwise found much
later: a `src` layout that was never installed, and a version that drifts from
the one the packaging metadata publishes.
"""

import tomllib
from pathlib import Path

import sift

KOK = Path(__file__).resolve().parent.parent


def test_the_package_imports_from_the_src_layout():
    assert sift.__version__


def test_the_published_version_is_the_one_the_package_reports():
    veri = tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))
    assert veri["project"]["version"] == sift.__version__


def test_a_command_is_named_after_the_package_itself():
    """`uvx sift-cli` has to start something.

    What an MCP registry entry can name is the package, and what `uvx` runs is a
    command of that same name -- so a client building a command from the entry
    alone types `sift-cli`, and until this existed it got "an executable named
    `sift-cli` is not provided by package `sift-cli`". The names differ because
    `sift` was taken on PyPI, which is nobody's fault and still the user's
    problem.
    """
    veri = tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = veri["project"]["scripts"]
    ad = veri["project"]["name"]

    assert ad in scripts, f"{ad} adinda bir komut yok; uvx {ad} calismaz"
    assert scripts[ad] == scripts["sift"], "paketin adi komut satirini baslatmali"


def test_notes_and_tests_live_in_their_own_folders():
    """The layout the project promised: notes in notlar/, tests in test/.

    Checked rather than trusted, because it is the one thing that cannot be
    fixed cheaply at the end -- which is exactly why it was asked for up front.
    """
    assert (KOK / "notlar").is_dir()
    assert (KOK / "test").is_dir()
    assert list((KOK / "notlar").glob("*.md")), "notlar/ bos olmamali"
    assert not list(KOK.glob("test_*.py")), "test dosyalari kokte durmamali"
    assert not list((KOK / "src" / "sift").glob("test_*.py")), "test kodun icinde durmamali"

# -- Faz 11: the front door --------------------------------------------------


def _readme() -> str:
    return (KOK / "README.md").read_text(encoding="utf-8")


def test_the_readme_names_every_command_the_tool_answers_to():
    """The front door has to list the rooms.

    A command nobody was told about is a command nobody runs, and the usage text
    and the README are written months apart by someone who has forgotten one of
    them. So they are compared rather than kept in step by hand.
    """
    from sift import cli

    words = {
        line.strip().split()[1]
        for line in cli.USAGE.splitlines()
        if line.strip().startswith("sift ")
    }
    assert words, "usage metninden komut cikarilamadi"

    readme = _readme()
    missing = [word for word in sorted(words) if f"sift {word}" not in readme]
    assert not missing, f"README bu komutlardan hic bahsetmiyor: {missing}"


def test_the_readme_names_every_tool_the_server_offers():
    """And promises no tool that is not there.

    Both directions matter. A tool left out of the README is a tool nobody
    calls; a tool promised and not offered is a caller told to use something
    that will fail.
    """
    from test_server import TOOLS

    readme = _readme()
    for name in sorted(TOOLS):
        assert f"`{name}`" in readme, f"README {name!r} aracindan bahsetmiyor"

    # Boslugu duzlestirerek: bir iddia, README'nin satir sonlarina bagli olmamali.
    flat = " ".join(readme.split())
    assert "`list` and `stats` are deliberately not offered" in flat


def test_publishing_happens_on_a_tag_and_nowhere_else():
    """A version that exists on PyPI cannot be taken back.

    So the difference between merged and released has to be a deliberate act.
    This is checked rather than trusted because the mistake it prevents is one
    that can only be made once.
    """
    release = (KOK / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'tags: ["v*"]' in release
    assert "branches:" not in release, "yayin bir dala baglanmis"
    assert "id-token: write" in release, "guvenilir yayinlama acik degil"
