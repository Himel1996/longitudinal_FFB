"""Phase B rescue package — orchestration only; core extraction rules unchanged."""

from ffb_webminer.rescue.candidates import (
    NormalizedCandidate,
    build_alias_map,
    expand_seed_variants,
    load_raw_candidates,
    normalize_candidates,
)
from ffb_webminer.rescue.compare import decide_rescue
from ffb_webminer.rescue.runner import RescuePipelineRunner

__all__ = [
    "NormalizedCandidate",
    "RescuePipelineRunner",
    "build_alias_map",
    "decide_rescue",
    "expand_seed_variants",
    "load_raw_candidates",
    "normalize_candidates",
]
