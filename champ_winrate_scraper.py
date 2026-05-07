from bs4 import BeautifulSoup
import aiohttp
import asyncio

from fastapi import FastAPI, HTTPException, Query

lane_mapping = {
    "Top": "vslane=top",
    "Jungle": "vslane=jungle",
    "Mid": "vslane=middle",
    "Bot": "vslane=bottom",
    "Support": "vslane=support"
}

rank_mapping = {
    "All": "tier=all&",
    "Gold+": "tier=gold_plus&",
    "Platinum+": "tier=platinum_plus&",
    "Emerald+": "tier=emerald_plus&",
    "Diamond+": "tier=diamond_plus&",
    "Master+": "tier=master_plus&"
}


def get_pickedchamp(top: str, jungle: str, middle: str, bottom: str, support: str):
    champs = [top, jungle, middle, bottom, support]
    champs = [champ.strip() for champ in champs if champ.strip() != ""]
    return champs


def get_lane_for_champ(champ: str, top: str, jungle: str, middle: str, bottom: str, support: str):
    if top.strip() == champ:
        return "top"
    if jungle.strip() == champ:
        return "jungle"
    if middle.strip() == champ:
        return "middle"
    if bottom.strip() == champ:
        return "bottom"
    if support.strip() == champ:
        return "support"
    return None


async def calculate_winrates(rank: str, mylane: str, top: str, jungle: str, middle: str, bottom: str, support: str):
    pickedchamps = get_pickedchamp(top, jungle, middle, bottom, support)

    if not pickedchamps:
        raise HTTPException(status_code=400, detail="Please enter at least one champion.")

    if rank not in rank_mapping:
        raise HTTPException(status_code=400, detail="Invalid rank value.")
    if mylane not in lane_mapping:
        raise HTTPException(status_code=400, detail="Invalid mylane value.")

    winrates = {}

    for champ in pickedchamps:
        lane = get_lane_for_champ(champ, top, jungle, middle, bottom, support)
        if lane:
            champ_winrates = await winrate_storage(champ, {}, lane, all_champs, mylane, rank)
            for enemy, winrate in champ_winrates.items():
                if enemy in winrates:
                    winrates[enemy] = (winrates[enemy] + winrate) / 2
                else:
                    winrates[enemy] = winrate

    sorted_winrate = sorted(winrates.items(), key=lambda item: item[1], reverse=False)
    result = []
    for champ, rate in sorted_winrate:
        reversed_winrate = 100 - rate
        result.append({"champ": champ, "reversed_winrate": round(reversed_winrate, 2)})
    return result


async def get_winrate_from_web(session, pickedchamp, champ, entry, mylane, rank):
    url = makelink(pickedchamp, champ, entry, mylane, rank)

    try:
        async with session.get(url, timeout=30) as response:
            if response.status != 200:
                print(f"Failed to fetch {url}: Status {response.status}")
                return 100

            html = await response.text()
            soup = BeautifulSoup(html, "lxml")
            winrate_element = soup.find("div", class_="mb-1 font-bold")

            if winrate_element:
                winrate_text = winrate_element.get_text().strip("%")
                print(f"Successfully fetched {url} wr={winrate_text}")
                return float(winrate_text)
            else:
                print(f"Winrate not found: {url}")
                return 100.0

    except asyncio.TimeoutError:
        print(f"Timeout error fetching {url}")
        return 0.0
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return 0.0


all_champs = [
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
    "yorick", "yuumi", "yunara", "zaahen", "zac", "zed", "zeri", "ziggs",
    "zilean", "zoe", "zyra",
]


async def winrate_storage(pickedchamp, winrate, entry, all_champs, mylane, rank):
    count = {}
    winrate = {}

    async with aiohttp.ClientSession() as session:
        tasks = [
            get_winrate_from_web(session, pickedchamp, champ, entry, mylane, rank)
            for champ in all_champs
            if champ != pickedchamp
        ]
        results = await asyncio.gather(*tasks)

    idx = 0
    for champ in all_champs:
        if champ != pickedchamp:
            winrate_value = results[idx]
            idx += 1

            if champ in winrate:
                winrate[champ] = (winrate[champ] * count[champ] + winrate_value) / (count[champ] + 1)
                count[champ] += 1
            else:
                winrate[champ] = winrate_value
                count[champ] = 1

    return winrate


def makelink(pickedchamp, champ, entry, mylane, rank):
    userlane = lane_mapping[mylane]
    rank_value = rank_mapping[rank]
    lane = entry

    champlink = "https://lolalytics.com/lol/"
    champlink += str(pickedchamp)
    champlink += "/vs/"
    champlink += str(champ)
    champlink += "/build/?"
    champlink += f"lane={lane}&" if lane else ""
    champlink += rank_value if rank_value else ""
    champlink += userlane if userlane else ""
    return champlink


app = FastAPI(title="Bad Champ Recommendation API")


@app.get("/api/recommendations")
async def recommendations(
    rank: str = Query("Platinum+"),
    mylane: str = Query("Top"),
    top: str = Query(""),
    jungle: str = Query(""),
    middle: str = Query(""),
    bottom: str = Query(""),
    support: str = Query(""),
):
    results = await calculate_winrates(rank, mylane, top, jungle, middle, bottom, support)
    return {
        "rank": rank,
        "mylane": mylane,
        "picks": {
            "top": top.strip(),
            "jungle": jungle.strip(),
            "middle": middle.strip(),
            "bottom": bottom.strip(),
            "support": support.strip(),
        },
        "count": len(results),
        "results": results,
    }