"""`python -m sift`, which is what somebody types when the command is not on PATH.

A console script needs an install that put it somewhere; a module needs the
package and nothing else. That is the difference between a virtual environment
somebody activated, a CI job, a `PYTHONPATH` pointed at a checkout -- and a
machine where `sift` is on PATH. All four should be able to run this.
"""

from __future__ import annotations

from sift.cli import main

raise SystemExit(main())
