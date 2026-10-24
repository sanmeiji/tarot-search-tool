import json
import hashlib
import os
import re
import sqlite3
import threading
import time
import secrets
import requests
from flask import Flask, render_template, request, jsonify, redirect

app = Flask(__name__)

DATA_PATH  = os.path.join(os.path.dirname(__file__), "data", "tarot.json")
STATS_DB   = os.path.join(os.path.dirname(__file__), "data", "stats.db")
TRACK_PATHS = {'/', '/draw', '/draw/about', '/about'}
VIEW_DEDUP_SECONDS = 30 * 60
BOT_UA_RE = re.compile(
    r"bot|crawler|spider|slurp|bingpreview|facebookexternalhit|"
    r"bytespider|petalbot|headless|phantomjs|python-requests|curl/|wget/|"
    r"go-http-client|apache-httpclient|okhttp|scrapy|httpx|aiohttp|uptime",
    re.IGNORECASE,
)


def _init_stats():
    conn = sqlite3.connect(STATS_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS views (
            id   INTEGER PRIMARY KEY,
            path TEXT    NOT NULL,
            date TEXT    NOT NULL,
            ts   INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS view_dedup (
            fingerprint TEXT    NOT NULL,
            path        TEXT    NOT NULL,
            bucket      INTEGER NOT NULL,
            PRIMARY KEY (fingerprint, path, bucket)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qrng_usage (
            month    TEXT PRIMARY KEY,
            requests INTEGER NOT NULL DEFAULT 0
        )
    """)
    current_bucket = int(time.time()) // VIEW_DEDUP_SECONDS
    conn.execute("DELETE FROM view_dedup WHERE bucket < ?", (current_bucket - 48,))
    conn.commit()
    conn.close()

_init_stats()

with open(DATA_PATH, encoding="utf-8") as f:
    CARDS = json.load(f)["cards"]

# Draw order: major → wands → cups → swords → pentacles
DRAW_ORDER = (
    [c for c in CARDS if c["arcana"] == "major"] +
    [c for c in CARDS if c.get("suit") == "权杖"] +
    [c for c in CARDS if c.get("suit") == "圣杯"] +
    [c for c in CARDS if c.get("suit") == "宝剑"] +
    [c for c in CARDS if c.get("suit") == "星币"]
)

ANU_QRNG_API_KEY = os.environ.get("ANU_QRNG_API_KEY", "").strip()
ANU_QRNG_URL = os.environ.get("ANU_QRNG_URL", "").strip() or (
    "https://api.quantumnumbers.anu.edu.au"
    if ANU_QRNG_API_KEY
    else "https://qrng.anu.edu.au/API/jsonI.php"
)
_qrng_state = {"retry_after": 0, "pool": []}
_qrng_lock = threading.Lock()


def search_cards(query: str) -> list:
    query = query.strip().lower()
    if not query:
        return []

    results = []
    for card in CARDS:
        name = card["name"].lower()
        name_en = card["name_en"].lower()
        suit = (card["suit"] or "").lower()
        number = card["number"].lower()

        keywords = " ".join([
            *card.get("keywords_upright", []),
            *card.get("keywords_reversed", []),
        ]).lower()
        desc = (card.get("description_upright", "") + " " +
                card.get("description_reversed", "")).lower()

        if (query in name or query in name_en or
                query in suit or query in number or
                name in query or query in keywords or query in desc):
            results.append(card)

    return results


def secure_draw(n):
    """Draw locally with the operating system's cryptographic RNG."""
    rng = secrets.SystemRandom()
    return rng.sample(range(1, 79), n), [rng.randrange(2) for _ in range(n)]


def _record_qrng_request():
    month = time.strftime("%Y-%m")
    with sqlite3.connect(STATS_DB) as conn:
        conn.execute(
            """INSERT INTO qrng_usage (month, requests) VALUES (?, 1)
               ON CONFLICT(month) DO UPDATE SET requests = requests + 1""",
            (month,),
        )


def _is_automated_request() -> bool:
    """Exclude obvious crawlers, scripts and browser prefetches from analytics."""
    user_agent = request.headers.get("User-Agent", "").strip()
    purpose = " ".join(filter(None, (
        request.headers.get("Purpose"),
        request.headers.get("Sec-Purpose"),
    ))).lower()
    return not user_agent or BOT_UA_RE.search(user_agent) is not None or "prefetch" in purpose


def _visitor_fingerprint() -> str:
    """Create a hashed deduplication key without storing raw client data."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() or request.remote_addr or "unknown"
    user_agent = request.headers.get("User-Agent", "")
    value = f"{client_ip}\0{user_agent}".encode("utf-8", errors="replace")
    return hashlib.sha256(value).hexdigest()


@app.before_request
def track_view():
    if (request.path in TRACK_PATHS and request.method == 'GET'
            and not _is_automated_request()):
        try:
            now = int(time.time())
            bucket = now // VIEW_DEDUP_SECONDS
            conn = sqlite3.connect(STATS_DB)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.execute(
                "INSERT OR IGNORE INTO view_dedup (fingerprint, path, bucket) VALUES (?, ?, ?)",
                (_visitor_fingerprint(), request.path, bucket),
            )
            if cursor.rowcount:
                conn.execute("INSERT INTO views (path, date, ts) VALUES (?, ?, ?)",
                             (request.path, time.strftime('%Y-%m-%d'), now))
            conn.commit()
            conn.close()
        except Exception:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def search():
    query = request.args.get("q", "")
    results = search_cards(query)
    return jsonify(results)


@app.route("/api/all")
def all_cards():
    return jsonify(CARDS)


def _qrng_draw(n):
    """Draw cards with ANU uint16 data, falling back to the OS CSPRNG."""
    try:
        if time.time() < _qrng_state["retry_after"]:
            raise RuntimeError("ANU QRNG is in cooldown")

        # Fetch the maximum batch and consume it across draws. This makes the
        # 100-request free tier practical instead of spending one request per
        # visitor action. The pool is process-local and contains unused values.
        if len(_qrng_state["pool"]) < 64:
            r = requests.get(
                ANU_QRNG_URL,
                params={"length": 1024, "type": "uint16"},
                headers={"x-api-key": ANU_QRNG_API_KEY} if ANU_QRNG_API_KEY else None,
                timeout=5,
            )
            r.raise_for_status()
            payload = r.json()
            values = payload.get("data", [])
            if payload.get("success") is not True or len(values) != 1024:
                raise ValueError("Invalid ANU QRNG response")
            _record_qrng_request()
            _qrng_state["pool"].extend(
                value for value in values
                if isinstance(value, int) and 0 <= value < 65520
            )

        # 65520 is the largest multiple of 78 below 2**16. Discarding the
        # remaining 16 values prevents modulo bias when mapping to 78 cards.
        usable = _qrng_state["pool"]
        card_nums = []
        consumed = 0
        for consumed, value in enumerate(usable, start=1):
            card_num = value % 78 + 1
            if card_num not in card_nums:
                card_nums.append(card_num)
                if len(card_nums) == n:
                    break
        orient_values = usable[consumed:consumed + n]
        if len(card_nums) != n or len(orient_values) != n:
            raise ValueError("Not enough usable ANU QRNG values")

        del usable[:consumed + n]
        _qrng_state["retry_after"] = 0
        return card_nums, orient_values, True
    except Exception:
        # Avoid making every draw wait on a known-down remote service.
        _qrng_state["retry_after"] = time.time() + 5 * 60
        pool, orients = secure_draw(n)
        return pool, orients, False


def qrng_draw(n):
    # Protect the shared entropy pool when Gunicorn uses threaded workers.
    with _qrng_lock:
        return _qrng_draw(n)


@app.route("/api/draw")
def draw_card():
    n = min(max(request.args.get("n", 1, type=int) or 1, 1), 5)
    card_nums, orient_nums = secure_draw(n)
    results = []
    for card_num, orient_num in zip(card_nums, orient_nums):
        card = DRAW_ORDER[card_num - 1]
        results.append({"card": card, "reversed": orient_num % 2 == 1})
    return jsonify({"results": results, "qrng": False})


@app.route("/api/quantum-draw")
def quantum_draw_card():
    n = min(max(request.args.get("n", 1, type=int) or 1, 1), 5)
    card_nums, orient_nums, used_qrng = qrng_draw(n)
    results = []
    for card_num, orient_num in zip(card_nums, orient_nums):
        card = DRAW_ORDER[card_num - 1]
        results.append({"card": card, "reversed": orient_num % 2 == 1})
    return jsonify({"results": results, "qrng": used_qrng})


@app.route("/api/quantum-usage")
def quantum_usage():
    month = time.strftime("%Y-%m")
    with sqlite3.connect(STATS_DB) as conn:
        row = conn.execute(
            "SELECT requests FROM qrng_usage WHERE month = ?", (month,)
        ).fetchone()
    used = row[0] if row else 0
    return jsonify({"month": month, "used": used, "limit": 100,
                    "remaining": max(100 - used, 0)})


@app.route("/draw")
def draw_page():
    return render_template("draw.html", quantum_mode=False)


@app.route("/quantum-draw")
def quantum_draw_page():
    return render_template("draw.html", quantum_mode=True)


@app.route("/draw/about")
def draw_about():
    return render_template("draw_about.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/api/stats")
def stats():
    try:
        conn = sqlite3.connect(STATS_DB)
        conn.execute("PRAGMA journal_mode=WAL")
        totals = conn.execute(
            "SELECT path, COUNT(*) FROM views GROUP BY path ORDER BY COUNT(*) DESC"
        ).fetchall()
        total = sum(r[1] for r in totals)
        conn.close()
        path_names = {'/': '检索首页', '/draw': '抽牌', '/draw/about': '抽牌说明', '/about': '关于'}
        return jsonify({
            'total': total,
            'pages': [{'path': r[0], 'name': path_names.get(r[0], r[0]), 'count': r[1]} for r in totals],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route("/sources")
def sources():
    return redirect("/about")


if __name__ == "__main__":
    app.run(debug=True, port=7777, use_reloader=False)
