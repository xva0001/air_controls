#!/usr/bin/env python
"""Launch the AirCanvas browser interface (FastAPI + static web client)."""

from aircanvas.web.server import main

if __name__ == "__main__":
    raise SystemExit(main())
