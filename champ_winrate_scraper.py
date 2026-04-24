import asyncio
import json

import aiohttp
from bs4 import BeautifulSoup

ALL_CHAMPS: list[str] = [
    "aatrox", "ahri", "akali", "akshan", "alistar", "ambessa", "amumu",
    "anivia", "annie", "aphelios", "ashe", "aurelionsol", "aurora", "azir",
    "bard", "belveth", "blitzcrank", "brand", "braum", "briar", "caitlyn",
    "camille", "cassiopeia", "chogath", "corki", "darius", "diana", "draven",
    "drmundo", "ekko", "elise", "evelynn", "ezreal", "fiddlesticks", "fiora",
    "fizz", "galio", "gangplank", "garen", "gnar", "gragas", "graves",
    "gwen", "hecarim", "heimerdinger", "hwei", "illaoi", "irelia", "ivern",
    "janna", "jarvaniv", "jax", "jayce", "jhin", "jinx", "kaisa", "kalista",
    "karma", "karthus", "kassadin", "katarina", "kayle", "kayn", "kennen",
    "khazix", "kindred", "kled", "kogmaw", "ksante", "leblanc", "leesin",
    "leona", "lillia", "lissandra", "lucian", "lulu", "lux", "malphite",
    "malzahar", "maokai", "masteryi", "mel", "milio", "missfortune", "mordekaiser",
    "morgana", "naafiri", "nami", "nasus", "nautilus", "neeko", "nidalee",
    "nilah", "nocturne", "nunu", "olaf", "orianna", "ornn", "pantheon",
    "poppy", "pyke", "qiyana", "quinn", "rakan", "rammus", "reksai",
    "rell", "renata", "renekton", "rengar", "riven", "rumble", "ryze",
    "samira", "sejuani", "senna", "seraphine", "sett", "shaco", "shen",
    "shyvana", "singed", "sion", "sivir", "skarner", "smolder", "sona",
    "soraka", "swain", "sylas", "syndra", "tahmkench", "taliyah", "talon",
    "taric", "teemo", "thresh", "tristana", "trundle", "tryndamere",
    "twistedfate", "twitch", "udyr", "urgot", "varus", "vayne", "veigar",
    "velkoz", "vex", "vi", "viego", "viktor", "vladimir", "volibear",
    "warwick", "wukong", "xayah", "xerath", "xinzhao", "yasuo", "yone",
    "yorick", "yuumi", "yunara", "zaahen", "zac", "zed", "zeri", "ziggs", "zilean", "zoe",
    "zyra",
]

RANK_MAP: dict[str, str] = {
    "All": "all",
    "Gold+": "gold_plus",
    "Platinum+": "platinum_plus",
    "Emerald+": "emerald_plus",
    "Diamond+": "diamond_plus",
    "Master+": "master_plus",
}

LANE_MAP: dict[str, str] = {
    "Top": "top",
    "Jungle": "jungle",
    "Mid": "middle",
    "Bot": "bottom",
    "Support": "support",
}

_REQUEST_TIMEOUT = 15  # seconds per request

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def makelink(champ: str, picked_champ: str, mylane: str, picked_lane: str, rank: str) -> str:
    """Build the lolalytics matchup URL for champ (in mylane) vs picked_champ (in picked_lane)."""
    rank_param = RANK_MAP[rank]
    lane_param = LANE_MAP[mylane]
    vslane_param = LANE_MAP[picked_lane]
    return (
        f"https://lolalytics.com/lol/{champ}/vs/{picked_champ}/"
        f"?lane={lane_param}&tier={rank_param}&vslane={vslane_param}"
    )

async def get_winrate_from_web(session: aiohttp.ClientSession, url: str) -> float:
    """
    Fetch one lolalytics matchup page and return the win-rate as a float.

    Error behaviour (preserved from original):
      - non-200 response  → 100
      - winrate element missing → 100.0
      - timeout / any exception → 0.0
    """
    try:
        async with session.get(url, headers=_HEADERS,
                               timeout=aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT)) as resp:
            if resp.status != 200:
                return 100
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # lolalytics embeds page data in a Next.js __NEXT_DATA__ script tag.
        # The head-to-head win rate lives at:
        #   props.pageProps.headerData.win / props.pageProps.headerData.games
        # which is also rendered into a visible element with class "WinRate".
        

        # Approach 1 – rendered HTML element
        el = soup.select_one("div.WinRate, span.WinRate, [class*='WinRate']")
        if el:
            text = el.get_text(strip=True).replace("%", "")
            return float(text)

        # Approach 2 – __NEXT_DATA__ JSON (more reliable on SSR pages)
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script and script.string:
            data = json.loads(script.string)
            header = (
                data.get("props", {})
                    .get("pageProps", {})
                    .get("headerData", {})
            )
            if "win" in header and "games" in header and header["games"]:
                return round(header["win"] / header["games"] * 100, 2)

        return 100.0

    except Exception:
        return 0.0

async def winrate_storage(
    session: aiohttp.ClientSession,
    picked_champ: str,
    picked_lane: str,
    mylane: str,
    rank: str,
) -> dict[str, float]:
    """
    For one already-picked champion (in picked_lane), fetch the win-rate of
    every champion in ALL_CHAMPS (playing in mylane) against it, concurrently.

    Returns {champ_name: winrate_float}.
    """
    candidate_champs = [c for c in ALL_CHAMPS if c != picked_champ]
    urls = [makelink(c, picked_champ, mylane, picked_lane, rank) for c in candidate_champs]
    results = await asyncio.gather(*(get_winrate_from_web(session, u) for u in urls))
    return dict(zip(candidate_champs, results))

async def calculate_recommendations(
    mylane: str,
    rank: str,
    picks: dict[str, str],
) -> list[dict]:
    """
    Compute "bad champion" recommendations.

    Parameters
    ----------
    mylane : str
        The lane for which we want recommendations  (e.g. "Top").
    rank : str
        Rank bracket (e.g. "Platinum+").
    picks : dict[str, str]
        {lane_label: champ_name} – only non-empty entries, e.g.
        {"Top": "aatrox", "Jungle": "vi"}.

    Returns
    -------
    list of {"champ": str, "reversed_winrate": float} sorted descending by
    reversed_winrate (= 100 − avg_winrate).  Champions already in *picks* are
    excluded from the results.
    """
    picked_set = set(picks.values())

    async with aiohttp.ClientSession() as session:
        # Gather per-picked-champ winrate maps concurrently
        tasks = [
            winrate_storage(session, champ, lane, mylane, rank)
            for lane, champ in picks.items()
        ]
        all_maps: list[dict[str, float]] = await asyncio.gather(*tasks)

    results: list[dict] = []
    for champ in ALL_CHAMPS:
        if champ in picked_set:
            continue
        wr_values = [wmap[champ] for wmap in all_maps if champ in wmap]
        if not wr_values:
            continue
        avg_wr = sum(wr_values) / len(wr_values)
        reversed_wr = round(100 - avg_wr, 2)
        results.append({"champ": champ, "reversed_winrate": reversed_wr})

    results.sort(key=lambda x: x["reversed_winrate"], reverse=True)
    return results