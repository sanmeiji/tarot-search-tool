import json
import os
import re
import sqlite3
import time
import random
import requests
from flask import Flask, render_template, request, jsonify, redirect

app = Flask(__name__)

DATA_PATH  = os.path.join(os.path.dirname(__file__), "data", "tarot.json")
STATS_DB   = os.path.join(os.path.dirname(__file__), "data", "stats.db")
TRACK_PATHS = {'/', '/draw', '/draw/about', '/about'}


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

_nonce_cache = {"value": None, "expires": 0}


def get_qrng_nonce():
    if _nonce_cache["value"] and time.time() < _nonce_cache["expires"]:
        return _nonce_cache["value"]
    r = requests.get("https://qrng.anu.edu.au/dice-throw/", timeout=10)
    r.encoding = "utf-8"
    # Try hidden input field first
    m = re.search(r'name=["\']dice_nonce_field["\'][^>]*value=["\']([a-f0-9]+)["\']', r.text)
    if not m:
        m = re.search(r'value=["\']([a-f0-9]+)["\'][^>]*name=["\']dice_nonce_field["\']', r.text)
    if not m:
        # Try JS variable
        m = re.search(r'"dice_nonce_field"\s*:\s*"([a-f0-9]+)"', r.text)
    if not m:
        raise ValueError("Could not extract QRNG nonce from page")
    nonce = m.group(1)
    _nonce_cache["value"] = nonce
    _nonce_cache["expires"] = time.time() + 3600
    return nonce


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


@app.before_request
def track_view():
    if request.path in TRACK_PATHS and request.method == 'GET':
        try:
            conn = sqlite3.connect(STATS_DB)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("INSERT INTO views (path, date, ts) VALUES (?, ?, ?)",
                         (request.path, time.strftime('%Y-%m-%d'), int(time.time())))
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


def qrng_draw(n):
    """Draw 2 independent sets of n numbers from QRNG.
    Set 1 (card indices 1-78, norepeat) selects cards.
    Set 2 (1-78, norepeat) determines orientation via odd/even.
    Falls back to Python random on failure."""
    try:
        nonce = get_qrng_nonce()
        r = requests.post(
            "https://qrng.anu.edu.au/wp-admin/admin-ajax.php",
            data={
                "repeats": "norepeat",
                "set_num": "2",
                "rep_num": str(n),
                "min_num": "1",
                "max_num": "78",
                "action": "dice_action",
                "dice_nonce_field": nonce,
                "_wp_http_referer": "/dice-throw/",
            },
            headers={
                "Referer": "https://qrng.anu.edu.au/dice-throw/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=10,
        )
        raw = r.json()
        data = json.loads(raw) if isinstance(raw, str) else raw
        if data.get("type") == "success":
            return data["output"][0], data["output"][1], True
        _nonce_cache["value"] = None
        raise ValueError("QRNG error")
    except Exception:
        pool = random.sample(range(1, 79), n)
        orients = [random.randint(1, 78) for _ in range(n)]
        return pool, orients, False


@app.route("/api/draw")
def draw_card():
    n = min(max(int(request.args.get("n", 1)), 1), 5)
    card_nums, orient_nums, used_qrng = qrng_draw(n)
    results = []
    for card_num, orient_num in zip(card_nums, orient_nums):
        card = DRAW_ORDER[card_num - 1]
        results.append({"card": card, "reversed": orient_num % 2 == 1})
    return jsonify({"results": results, "qrng": used_qrng})


@app.route("/draw")
def draw_page():
    return render_template("draw.html")


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
