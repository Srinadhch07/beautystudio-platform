"""Operational command-line tools.

Each module is run directly, e.g. ``python -m app.cli.create_admin``. Nothing in
this package is imported by the application at runtime, so importing the app can
never start a provisioning flow by accident.
"""

__all__: list[str] = []
