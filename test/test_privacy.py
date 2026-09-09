"""Faz 10 -- what leaves this machine.

Two promises are defended here and they pull in opposite directions, which is
why they are tested together.

A credential must not reach a model. And a reader must be shown their output
exactly as the command produced it -- masking is not allowed to touch that, ever,
because the whole tool rests on the line you were shown being the line that is
there.

Both hold at once only because of where the masking sits: on the way out, in the
one function that turns capture text into a question.
"""

from __future__ import annotations

import sys

import pytest

from sift import capture, cli, privacy, view
from sift.distill import rows
from test_model import _bridge, _Fake, _ok

SECRET = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFT_HOME", str(tmp_path / "sift"))
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("SIFT_API_KEY", "NVIDIA_API_KEY", "SIFT_MASK", "SIFT_NO_MODEL"):
        monkeypatch.delenv(name, raising=False)


# -- what is masked ----------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.dBjftJeZ4CVP",
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
        f"git remote add origin https://{SECRET}@github.com/x/y.git",
        "SLACK=xoxb-1234567890-abcdefghijkl",
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz012345",
        "SIFT_API_KEY=nvapi-abcdefghijklmnopqrstuvwxyz012345",
        "GOOGLE=AIzaSyA1234567890abcdefghijklmnopqrstuvw",
        "GITLAB=glpat-abcdefghijklmnopqrst",
        "HF=hf_abcdefghijklmnopqrstuvwxyz01",
        "Authorization: Basic YWxhZGRpbjpvcGVuc2VzYW1l",
        "postgres://app:hunter2plus@db.internal:5432/prod",
        "password: correct-horse-battery",
        "  api_key = 'abcdefghijklmnop'",
        "MTIzNDU2Nzg5MGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6QUJDREVG",
    ],
)
def test_a_credential_shaped_thing_does_not_leave(line):
    masked = privacy.mask(line)
    assert privacy.REDACTED in masked, f"nothing was hidden in {line!r}"


@pytest.mark.parametrize(
    "line",
    [
        "commit 9f2c1ab4de5f6789012345678901234567890abc",
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "  at com.example.Thing.method(Thing.java:412)",
        "Downloading numpy-2.1.3-cp312-cp312-manylinux_2_17_x86_64.whl (16.3 MB)",
        "  ✓ 412 tests passed in 8.31s",
        "ERROR: could not find a version that satisfies the requirement",
    ],
)
def test_long_is_not_the_same_as_secret(line):
    """A tool that redacted every high-entropy run would redact the whole log.

    A commit hash and a checksum are long, dense and completely harmless. If
    these were masked the model would be handed a page of `[redacted]` and told
    to find what mattered in it.
    """
    assert privacy.mask(line) == line


def test_masking_can_be_switched_off_by_someone_who_means_it(monkeypatch):
    monkeypatch.setenv("SIFT_MASK", "0")
    assert privacy.mask(f"token={SECRET}") == f"token={SECRET}"


def test_a_value_nobody_recognises_leaves_masking_on(monkeypatch):
    """Both switches default towards less leaving the machine."""
    monkeypatch.setenv("SIFT_MASK", "belki")
    assert privacy.REDACTED in privacy.mask(f"token={SECRET}")


# -- and what masking is never allowed to touch ------------------------------


def test_the_model_is_shown_the_mask_and_the_reader_is_shown_the_line():
    """The promise this whole module has to fit inside.

    A masked line is still printed to the reader byte for byte, because the
    model was only ever asked which numbers mattered and the text comes from the
    file. Privacy costs the model some context here; it costs the reader nothing.
    """
    got = capture.run([sys.executable, "-c", f"print('key={SECRET}')"])

    asked = rows([(1, got.text().rstrip("\n"))])
    assert SECRET not in asked
    assert privacy.REDACTED in asked

    assert SECRET in got.text(), "the capture on disk was altered"


def test_a_secret_is_masked_before_the_line_is_shortened():
    """Order matters here, and only one of the two orders is safe.

    A long line is cut down before it is sent. Cut first and a credential that
    straddles the limit arrives half-length, too short for any pattern to
    recognise -- and the half that is left is still a leak. Masked first, there
    is nothing left to cut.
    """
    out = rows([(1, "x" * 29 + " " + SECRET)], cap=40)

    assert "ghp_" not in out
    assert privacy.REDACTED in out


def test_masking_never_changes_a_line_number(monkeypatch):
    """A replacement that spanned lines would take the numbering with it.

    The numbers are the only thing a model gives back, so a mask that moved one
    would send a reader to the wrong line -- the exact failure this project
    exists to make impossible.
    """
    lines = [(4, "bir"), (5, f"token={SECRET}"), (6, "uc")]
    out = rows(lines).splitlines()

    assert len(out) == 3
    assert [row.split("|")[0] for row in out] == ["4", "5", "6"]


# -- and whether anything is sent at all -------------------------------------


def test_sending_can_be_switched_off_and_then_nothing_is_asked(monkeypatch):
    monkeypatch.setenv("SIFT_NO_MODEL", "1")
    fake = _Fake(_ok())
    bridge = _bridge(fake, api_key="x")

    assert bridge.ask("soru", "metin") is None
    assert fake.asked == [], "a request was made with sending switched off"
    assert "switched off" in (bridge.last_error or "")


def test_switching_sending_off_costs_the_model_and_not_the_output(capsys, monkeypatch):
    """The third rule again, from the one direction that had not been tried.

    No key, no network and a bug in the distiller were each proved not to cost
    the caller their output. A user who has decided nothing may leave this
    machine is owed the same.
    """
    monkeypatch.setenv("SIFT_NO_MODEL", "1")

    code = "for n in range(5): print(f'satir {n}')"
    assert cli.main(["run", "--", sys.executable, "-c", code]) == 0

    said = capsys.readouterr()
    assert "satir 0" in said.out
    assert "satir 4" in said.out
    assert "switched off" in said.err


def test_a_view_built_with_sending_off_says_so_rather_than_claiming_a_model(monkeypatch):
    monkeypatch.setenv("SIFT_NO_MODEL", "1")
    got = capture.run([sys.executable, "-c", "print('bir')"])

    built, who = view.best_view(got)

    assert built.model is None
    assert "switched off" in who


def test_only_the_secret_is_replaced_and_the_line_around_it_survives():
    """Masking is a replacement, not a deletion.

    A line reduced to the word `REDACTED` is a line the model cannot use: what
    was being fetched, which header carried it, what came after -- all of that
    is the context the question is about, and none of it is the secret. Every
    test here checked that the secret was gone; none checked that anything else
    was still there, and the mutation battery said so.
    """
    # The words have to sit *inside the match* for this to mean anything. A
    # first version of this test kept its landmarks outside it -- `re.sub`
    # replaces only what matched, so they survived either way and the mutation
    # walked past. `bearer` and the scheme of a connection string are inside.
    line = f"Authorization: Bearer {SECRET} -> 401"
    linked = "postgres://reader:hunter2000@db.internal:5432/app"

    masked = privacy.mask(line)
    masked_link = privacy.mask(linked)

    assert SECRET not in masked
    assert privacy.REDACTED in masked
    assert "Bearer" in masked, "eslesmenin icindeki sema adi da silinmis"

    assert "hunter2000" not in masked_link
    assert "postgres://reader:" in masked_link, "kullanici ve sema da silinmis"
    assert "@db.internal" in masked_link, "sunucu adi da silinmis"
