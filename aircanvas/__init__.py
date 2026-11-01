"""AirCanvas shared core package.

The package is intentionally UI-agnostic.  PySide6 and FastAPI front-ends both
consume the same camera-independent interaction session, drawing engine,
gesture recogniser, navigation state machine and tracker.
"""

__version__ = "1.0.0"
__app_name__ = "AirCanvas"
__tagline__ = "Touch the air. Draw the world."
