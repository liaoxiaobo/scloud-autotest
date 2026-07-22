"""Compatibility entrypoint for the resource preflight CLI."""

from __future__ import annotations

from sugon_web.tools.preflight.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
