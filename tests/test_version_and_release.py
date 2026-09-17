"""Tests for version integrity, packaging artifacts, and release readiness."""

from __future__ import annotations

import tomllib
from pathlib import Path
import pytest

import secnorm
from secnorm import PIPELINE_VERSION, __version__
from secnorm.cli import main as cli_main


def test_version_consistency() -> None:
    """Verify that __version__ and PIPELINE_VERSION match pyproject.toml version."""
    assert __version__ == "1.0.0"
    assert PIPELINE_VERSION == "1.0.0"

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.is_file(), "pyproject.toml not found"

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    project_version = data["project"]["version"]
    assert project_version == __version__
    assert project_version == PIPELINE_VERSION


def test_py_typed_presence() -> None:
    """Verify that py.typed marker is present in the package directory."""
    pkg_dir = Path(secnorm.__file__).resolve().parent
    marker = pkg_dir / "py.typed"
    assert marker.is_file(), "py.typed missing in secnorm package"


def test_normalization_result_reports_correct_version() -> None:
    """Ensure NormalizationResult records the 1.0.0 pipeline version."""
    res = secnorm.normalize("Test text", preset="minimal")
    assert res.pipeline_version == "1.0.0"


def test_cli_version_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `secnorm --version` prints the release version string."""
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    output = captured.out or captured.err
    assert "secnorm 1.0.0" in output


def test_all_contains_version_exports() -> None:
    """Ensure __version__ and PIPELINE_VERSION are in __all__ and importable."""
    assert "__version__" in secnorm.__all__
    assert "PIPELINE_VERSION" in secnorm.__all__
    assert getattr(secnorm, "__version__") == "1.0.0"
    assert getattr(secnorm, "PIPELINE_VERSION") == "1.0.0"
