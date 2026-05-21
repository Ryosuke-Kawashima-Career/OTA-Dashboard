"""Repo-wide pytest fixtures + teardown hygiene.

Loaded automatically by pytest because it sits at the project root.
"""
from __future__ import annotations

import logging


def pytest_configure(config):  # noqa: ARG001 — pytest hook signature
    """Silence the trailing 'Logging error' tracebacks from Prefect.

    Each `@prefect.flow` call boots a temporary `SubprocessASGIServer`,
    and its shutdown step logs "Stopping temporary server on …" via a
    Rich-backed handler bound to `sys.stdout`. By the time that log
    fires during pytest teardown, pytest has already closed the stdout
    it had captured, so the handler raises
    `ValueError: I/O operation on closed file`. Python's `logging`
    module then prints a `--- Logging error ---` traceback to stderr.

    The tests themselves are unaffected — this is pure cleanup noise.
    Setting `logging.raiseExceptions = False` is the documented switch
    that tells the logging module to swallow handler failures silently
    (the exact use-case it was designed for: production environments
    where a broken logging sink should not corrupt program output).

    Scoping the change to `pytest_configure` keeps it test-only — the
    real ingestion runtime keeps full logging-error visibility.
    """
    logging.raiseExceptions = False
