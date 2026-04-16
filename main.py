import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from champ_winrate_scraper import calculate_recommendations, RANK_MAP, LANE_MAP

app = FastAPI(title="Champ Recommendation API")

# CORS wide-open (OK per your plan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Simple in-memory cache (30 minutes)
# Keyed by full input set (rank, mylane, and the 5 lane champs)
# ---------------------------------------------------------------------------
CACHE_SECONDS = 30 * 60
_cache: dict[tuple, dict] = {}


def _cache_get(key: tuple) -> Optional[dict]:
    entry = _cache.get(key)
    if not entry:
        return None
    if time.time() - entry["cached_at"] > CACHE_SECONDS:
        # expired
        _cache.pop(key, None)
        return None
    return entry["data"]


def _cache_set(key: tuple, data: dict) -> None:
    _cache[key] = {"cached_at": time.time(), "data": data}


@app.get("/api/recommendations")
async def api_recommendations(
    rank: str = Query(..., description="One of: All, Gold+, Platinum+, Emerald+, Diamond+, Master+"),
    mylane: str = Query(..., description="One of: Top, Jungle, Mid, Bot, Support"),
    top: str = Query("", description="Lowercase champ name or empty"),
    jungle: str = Query("", description="Lowercase champ name or empty"),
    middle: str = Query("", description="Lowercase champ name or empty"),
    bottom: str = Query("", description="Lowercase champ name or empty"),
    support: str = Query("", description="Lowercase champ name or empty"),
):
    # Keep behavior simple: validate ONLY rank/mylane labels because otherwise makelink() will KeyError
    if rank not in RANK_MAP:
        raise HTTPException(status_code=400, detail="Invalid rank value.")
    if mylane not in LANE_MAP:
        raise HTTPException(status_code=400, detail="Invalid mylane value.")

    picks = {
        "Top": top.strip(),
        "Jungle": jungle.strip(),
        "Mid": middle.strip(),
        "Bot": bottom.strip(),
        "Support": support.strip(),
    }
    # Remove empty champs (same idea as your Tkinter get_pickedchamp ignoring empty)
    picks = {lane: champ for lane, champ in picks.items() if champ != ""}

    if not picks:
        raise HTTPException(status_code=400, detail="Please enter at least one champion.")

    cache_key = (rank, mylane, top, jungle, middle, bottom, support)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    started = time.time()
    results = await calculate_recommendations(mylane=mylane, rank=rank, picks=picks)
    elapsed = round(time.time() - started, 3)

    response = {
        "rank": rank,
        "mylane": mylane,
        "picks": picks,
        "count": len(results),
        "seconds_taken": elapsed,
        "results": results,  # list of {"champ": str, "reversed_winrate": float}
    }

    _cache_set(cache_key, response)
    return response
