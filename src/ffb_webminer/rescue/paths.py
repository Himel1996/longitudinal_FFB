"""Path guards and standard rescue layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PARENT_RELEASE_NAME = "full_sample_v1"
RESCUE_RELEASE_NAME = "full_sample_v1_1_rescue"
FINAL_RESCUE_RELEASE_NAME = "full_sample_v1_1_rescue_final"


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


def assert_not_final_rescue_release(path: Path, *, project_root: Path) -> None:
    """Hard-fail if a write target is inside the frozen cumulative final rescue release."""
    root = project_root.resolve()
    target = path.resolve()
    final = (root / "data" / "releases" / FINAL_RESCUE_RELEASE_NAME).resolve()
    try:
        target.relative_to(final)
    except ValueError:
        return
    raise RuntimeError(
        f"Refusing to write inside frozen final rescue release: {final} (target={target})"
    )


def _resolve_under(root: Path, value: str | Path | None, default: Path) -> Path:
    if value is None or str(value).strip() == "":
        return default
    p = Path(str(value))
    return p if p.is_absolute() else (root / p)


def rescue_layout(project_root: Path, rescue_doc: dict[str, Any] | None = None) -> dict[str, Path]:
    """Build rescue workspace paths.

    When ``rescue_doc`` provides ``paths`` / ``rescue_candidate_file``, those
    override the default 19-firm Phase B layout so isolated runs (e.g. dm final)
    cannot clobber the accepted rescue workspace.
    """
    root = project_root.resolve()
    paths = (rescue_doc or {}).get("paths") or {}
    candidate = (rescue_doc or {}).get("rescue_candidate_file")
    release_name = (rescue_doc or {}).get("release_name") or RESCUE_RELEASE_NAME

    layout = {
        "raw": _resolve_under(root, paths.get("raw_dir"), root / "data" / "raw" / "full_sample_rescue"),
        "interim": _resolve_under(
            root, paths.get("interim_dir"), root / "data" / "interim" / "full_sample_rescue"
        ),
        "processed": _resolve_under(
            root, paths.get("processed_dir"), root / "data" / "processed" / "full_sample_rescue"
        ),
        "processed_output": _resolve_under(
            root,
            paths.get("processed_output_dir"),
            root / "data" / "processed" / "full_sample_rescue" / "output",
        ),
        "release": _resolve_under(
            root, paths.get("release_dir"), root / "data" / "releases" / str(release_name)
        ),
        "reports": _resolve_under(
            root, paths.get("reports_dir"), root / "reports" / "full_sample_rescue"
        ),
        "parent_release": _resolve_under(
            root, paths.get("parent_release_dir"), root / "data" / "releases" / PARENT_RELEASE_NAME
        ),
        "parent_data": root / "data" / "releases" / PARENT_RELEASE_NAME / "data",
        "candidate_csv": _resolve_under(
            root,
            candidate,
            root / "data" / "input" / "full_sample_url_rescue_candidates.csv",
        ),
        "rescue_config": root / "config" / "full_sample_rescue.yaml",
        "full_sample_config": root / "config" / "full_sample.yaml",
    }
    parent_override = paths.get("parent_release_dir")
    if parent_override:
        layout["parent_release"] = _resolve_under(root, parent_override, layout["parent_release"])
        layout["parent_data"] = layout["parent_release"] / "data"
    return layout


def ensure_workspace_dirs(layout: dict[str, Path], *, create: bool = True) -> None:
    if not create:
        return
    for key in ("raw", "interim", "processed", "processed_output", "reports"):
        layout[key].mkdir(parents=True, exist_ok=True)
    (layout["interim"] / "html").mkdir(parents=True, exist_ok=True)
    (layout["interim"] / "state").mkdir(parents=True, exist_ok=True)
