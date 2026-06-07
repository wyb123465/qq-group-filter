"""Tests for packaging metadata needed by fresh uv installs."""

from pathlib import Path


def test_pyproject_declares_runtime_dependencies():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[project]" in text
    assert 'requires-python = ">=3.10"' in text
    for dependency in [
        "pydantic",
        "pydantic-settings",
        "aiosqlite",
        "httpx",
        "websockets",
        "python-dotenv",
    ]:
        assert dependency in text


def test_pyproject_declares_src_package_build_config():
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[build-system]" in text
    assert 'build-backend = "hatchling.build"' in text
    assert "[tool.hatch.build.targets.wheel]" in text
    assert 'packages = ["src/qq_group_filter"]' in text
