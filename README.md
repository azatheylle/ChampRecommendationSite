# ChampRecommendationSite — Backend API

FastAPI backend for the LoL Bad Champion Recommendation project.  
Exposes a single endpoint: `GET /api/recommendations`.

> **Note:** `basicinfo()` was removed entirely — it depended on an unused
> Riot API key and was not part of the recommendation flow.

---

## Endpoint

```
GET /api/recommendations
```

### Query parameters

| Parameter | Required | Values |
|-----------|----------|--------|
| `rank`    | no (default `Platinum+`) | `All`, `Gold+`, `Platinum+`, `Emerald+`, `Diamond+`, `Master+` |
| `mylane`  | no (default `Top`) | `Top`, `Jungle`, `Mid`, `Bot`, `Support` |
| `top`     | optional | lowercase champion name |
| `jungle`  | optional | lowercase champion name |
| `middle`  | optional | lowercase champion name |
| `bottom`  | optional | lowercase champion name |
| `support` | optional | lowercase champion name |

At least one champion must be provided; otherwise HTTP 400 is returned.

### Example request

```
GET /api/recommendations?rank=Platinum%2B&mylane=Top&top=aatrox
```

### Example response

```json
[
  { "champ": "teemo",   "reversed_winrate": 55.12 },
  { "champ": "singed",  "reversed_winrate": 54.78 },
  ...
]
```

`reversed_winrate = 100 − avg_winrate` — higher value means the champion
loses more often against your team, making them a "bad pick" for the enemy.

Responses are cached for **30 minutes** keyed by the full set of inputs.

---

## Local run (Windows)

1. Clone the repository and enter it:

   ```cmd
   git clone https://github.com/azatheylle/ChampRecommendationSite.git
   cd ChampRecommendationSite
   ```

2. (Recommended) create a virtual environment:

   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```cmd
   pip install -r requirements.txt
   ```

4. Start the server:

   ```cmd
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. Open the interactive docs at <http://127.0.0.1:8000/docs> or call the API directly:

   ```
   http://127.0.0.1:8000/api/recommendations?rank=Platinum%2B&mylane=Top&top=aatrox
   ```

---

## Deploy to Render (free tier)

1. Push this repository to GitHub (already done).
2. Go to <https://render.com> → **New** → **Web Service** → connect your repo.
3. Set the following in the Render dashboard:
   - **Environment:** `Python 3`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Click **Deploy**.

The service URL will look like `https://your-service.onrender.com`.  
Your GitHub Pages frontend should call `https://your-service.onrender.com/api/recommendations`.

---

## Project layout

```
ChampRecommendationSite/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, CORS, cache, /api/recommendations
│   └── recommender.py   # Scraping logic (no Tkinter)
├── requirements.txt
└── README.md
```
