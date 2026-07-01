"""Unit tests for the package's __init__ files so coverage sees imports."""

from __future__ import annotations


def test_imports():
    import app.drivers  # noqa: F401
    import app.models  # noqa: F401
    import app.schemas.config_file  # noqa: F401
    import app.schemas.device  # noqa: F401
    import app.schemas.job  # noqa: F401
    import app.schemas.share  # noqa: F401
    import app.schemas.user  # noqa: F401
