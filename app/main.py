"""
FastAPI application — single endpoint: GET /api/recommendations

Caching: full responses are cached for 30 minutes, keyed by the complete
set of query inputs (rank + mylane + all five lane inputs).
"""

import time
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.recommender import LANE_MAP, RANK_MAP, calculate_recommendations

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="LoL Bad Champ Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory response cache  {cache_key: (timestamp, response_payload)}
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, list]] = {}
_CACHE_TTL = 30 * 60  # 30 minutes in seconds


def _cache_key(rank: str, mylane: str, top: str, jungle: str,
               middle: str, bottom: str, support: str) -> str:
    return f"{rank}|{mylane}|{top}|{jungle}|{middle}|{bottom}|{support}"


def _get_cached(key: str) -> list | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, payload = entry
    if time.time() - ts > _CACHE_TTL:
        del _CACHE[key]
        return None
    return payload


def _set_cache(key: str, payload: list) -> None:
    _CACHE[key] = (time.time(), payload)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

VALID_RANKS = list(RANK_MAP.keys())
VALID_LANES = list(LANE_MAP.keys())


@app.get("/api/recommendations")
async def recommendations(
    rank: Annotated[str, Query(description="Rank bracket")] = "Platinum+",
    mylane: Annotated[str, Query(description="Your lane")] = "Top",
    top: Annotated[str, Query(description="Enemy top-lane champion (lowercase)")] = "",
    jungle: Annotated[str, Query(description="Enemy jungle champion (lowercase)")] = "",
    middle: Annotated[str, Query(description="Enemy mid champion (lowercase)")] = "",
    bottom: Annotated[str, Query(description="Enemy bot champion (lowercase)")] = "",
    support: Annotated[str, Query(description="Enemy support champion (lowercase)")] = "",
):
    # ── Validation ──────────────────────────────────────────────────────────
    if rank not in VALID_RANKS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid rank. Must be one of: {', '.join(VALID_RANKS)}"},
        )
    if mylane not in VALID_LANES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid mylane. Must be one of: {', '.join(VALID_LANES)}"},
        )

    # Build picks dict – keep only non-empty entries; values stay lowercase
    picks: dict[str, str] = {}
    lane_inputs = {
        "Top": top.strip(),
        "Jungle": jungle.strip(),
        "Mid": middle.strip(),
        "Bot": bottom.strip(),
        "Support": support.strip(),
    }
    for lane, champ in lane_inputs.items():
        if champ:
            picks[lane] = champ

    if not picks:
        return JSONResponse(
            status_code=400,
            content={"error": "At least one champion must be provided."},
        )

    # ── Cache lookup ─────────────────────────────────────────────────────────
    key = _cache_key(rank, mylane, top.strip(), jungle.strip(),
                     middle.strip(), bottom.strip(), support.strip())
    cached = _get_cached(key)
    if cached is not None:
        return cached

    # ── Compute ───────────────────────────────────────────────────────────────
    result = await calculate_recommendations(mylane, rank, picks)

    _set_cache(key, result)
    return result
