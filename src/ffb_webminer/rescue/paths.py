"""Path guards and standard rescue layout."""

from __future__ import annotations

from pathlib import Path

PARENT_RELEASE_NAME = "full_sample_v1"
RESCUE_RELEASE_NAME = "full_sample_v1_1_rescue"


def assert_not_parent_release(path: Path, *, project_root: Path) -> None:
    """Hard-fail if a write target is inside the frozen parent release."""
    root = project_root.resolve()
    target = path.resolve()
    parent = (root / "data" / "releases" / PARENT_RELEASE_NAME).resolve()
    try:
        target.relative_to(parent)
    except ValueError:
        return
    raise RuntimeError(
        f"Refusing to write inside frozen parent release: {parent} (target={target})"
    )


def rescue_layout(project_root: Path) -> dict[str, Path]:
    root = project_root.resolve()
    return {
        "raw": root / "data" / "raw" / "full_sample_rescue",
        "interim": root / "data" / "interim" / "full_sample_rescue",
        "processed": root / "data" / "processed" / "full_sample_rescue",
        "processed_output": root / "data" / "processed" / "full_sample_rescue" / "output",
        "release": root / "data" / "releases" / RESCUE_RELEASE_NAME,
        "reports": root / "reports" / "full_sample_rescue",
        "parent_release": root / "data" / "releases" / PARENT_RELEASE_NAME,
        "parent_data": root / "data" / "releases" / PARENT_RELEASE_NAME / "data",
        "candidate_csv": root / "data" / "input" / "full_sample_url_rescue_candidates.csv",
        "rescue_config": root / "config" / "full_sample_rescue.yaml",
        "full_sample_config": root / "config" / "full_sample.yaml",
    }


def ensure_workspace_dirs(layout: dict[str, Path], *, create: bool = True) -> None:
    if not create:
        return
    for key in ("raw", "interim", "processed", "processed_output", "reports"):
        layout[key].mkdir(parents=True, exist_ok=True)
    (layout["interim"] / "html").mkdir(parents=True, exist_ok=True)
    (layout["interim"] / "state").mkdir(parents=True, exist_ok=True)
