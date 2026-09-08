"""What leaves this machine, and what is held back.

Everything else here is about what a reader is shown. This module is about the
other direction. Exactly one thing ever leaves: the text of a question. This
decides what that text may contain, and whether it is sent at all.

Two switches and one rule.

**`SIFT_NO_MODEL`** turns sending off entirely. Nothing is asked and every view
falls back to the deterministic one -- worse, and offered honestly as worse. A
tool that cannot be told "not from this machine" is a tool that cannot be used
on the machines where it would help most.

**`SIFT_MASK=0`** turns masking off, for someone who has decided their output
holds nothing worth hiding and would rather a model saw all of it.

And the rule: **a credential is replaced on the way out, and never in what is
shown.** The second half is what makes this cheap. A model is only ever asked
for line numbers; the lines are printed from the local file, byte for byte. So a
line masked on the way out is still shown to the reader in full. Masking costs
the model a little context and costs the reader nothing, which is why it is on
by default.

This is the one place in this project where patterns are allowed, and `fallback`
refuses them in the strongest terms, so the difference is worth stating. There a
pattern would be *judging* -- deciding which lines matter, in languages it half
knows, and being confidently wrong. Here nothing is judged. A pattern that fires
wrongly costs a masked token in a prompt; a pattern that fails to fire leaks a
key. Those two mistakes are not comparable, so the rule is: when in doubt, mask.

What is **not** masked matters just as much. Long is not the same as secret. A
commit hash, a checksum, a base64 payload in a build log are all long, all high
entropy, and all harmless; a tool that redacted every one of them would hand the
model a page of `[redacted]` and call it privacy. So what is matched here is the
shape credentials actually have, and a bare secret shaped like nothing in
particular will get through. That is a real limit, stated rather than papered
over: masking reduces what leaks by accident, and `SIFT_NO_MODEL` is the switch
that guarantees nothing leaves at all.
"""

from __future__ import annotations

import os
import re

# Short, plain, and obviously not a value. It travels in a prompt, so it costs
# the model a token and tells it that something was there.
REDACTED = "[redacted]"

_NO = {"0", "false", "no", "off", ""}


def sending_on() -> bool:
    """Whether a model may be asked anything at all.

    Off is the easy state to reach: `SIFT_NO_MODEL` set to anything except a
    plain no means no sending. A privacy switch that only works when spelled
    exactly right is a switch that fails open, and this one has to fail closed.
    """
    return (os.environ.get("SIFT_NO_MODEL") or "").strip().lower() in _NO


def masking_on() -> bool:
    """Whether credentials are replaced before a question is sent.

    On unless switched off, and here a value nobody recognises leaves it on.
    Both defaults point the same way: towards less leaving the machine.
    """
    return (os.environ.get("SIFT_MASK") or "1").strip().lower() not in _NO


# Each rule is a pattern and which group of it holds the secret. Group 0 means
# the whole match is the secret; a numbered group keeps the surrounding text,
# which is what tells a reader -- and a model -- what was hidden and where.
_RULES: list[tuple[re.Pattern[str], int]] = [
    # A JSON Web Token. The first segment always begins this way, because it is
    # base64 of a JSON object that opens with a quoted key.
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), 0),
    # Tokens that carry their own prefix. Nothing else looks like these, so
    # matching them costs nothing and missing them costs a key.
    (re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[A-Z0-9]{16}\b"), 0),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), 0),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), 0),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), 0),
    (re.compile(r"\bnvapi-[A-Za-z0-9_-]{20,}\b"), 0),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35,}"), 0),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), 0),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), 0),
    # An authorization header, whatever scheme it names.
    (re.compile(r"(?i)\b(?:bearer|basic|token)\s+([A-Za-z0-9+/=._~-]{12,})"), 1),
    # A password inside a connection string: scheme://user:secret@host
    (re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s:/@]+:([^\s@/]{3,})@"), 1),
    # An assignment whose name says what it holds. The names are English because
    # configuration and protocols are, whatever language the project around them
    # is written in -- but this rule is a bonus rather than the floor, and cannot
    # be complete. The shapes above are what this module actually rests on.
    (
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key"
            r"|client[_-]?secret|auth[_-]?token|credential)s?[\"']?\s*[:=]\s*"
            r"[\"']?([^\s\"',;)]{4,})"
        ),
        1,
    ),
    # A line that is nothing but base64: the body of a PEM block. Three things
    # narrow it, and each was earned. Anchored to the whole line, because a long
    # base64 run *inside* a sentence is a payload someone is debugging and
    # masking it would help nobody. And mixed case with a digit, because
    # "x" * 5000 is a line of x's -- a test in this project produces exactly
    # that, and an earlier version of this rule redacted it. Long is not the
    # same as dense, and neither is the same as secret.
    (
        re.compile(
            r"^(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[0-9])"
            r"[A-Za-z0-9+/]{40,}={0,2}$"
        ),
        0,
    ),
]


def mask(text: str) -> str:
    """The same text with anything credential-shaped replaced.

    Applied to one line at a time by its caller, and that is deliberate: a
    replacement that spanned lines would take the line numbers with it, and the
    numbers are the only thing a model is ever asked to give back.
    """
    if not masking_on():
        return text
    for pattern, group in _RULES:
        text = pattern.sub(lambda found, g=group: _hidden(found, g), text)
    return text


def _hidden(found: re.Match[str], group: int) -> str:
    """The match with its secret part replaced and the rest of it left alone."""
    whole = found.group(0)
    if group == 0:
        return REDACTED
    value = found.group(group)
    if not value:
        return whole
    cut = found.start(group) - found.start(0)
    return whole[:cut] + REDACTED + whole[cut + len(value) :]
