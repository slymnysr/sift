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
