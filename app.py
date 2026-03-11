import json
import os
import re
import time
import random
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "tarot.json")

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
    """Draw n*2 numbers from QRNG (first n = card indices 1-78, last n = orientation).
    Falls back to Python random on failure."""
    rep = n * 2
    try:
        nonce = get_qrng_nonce()
        r = requests.post(
            "https://qrng.anu.edu.au/wp-admin/admin-ajax.php",
            data={
                "repeats": "norepeat",
                "set_num": "1",
                "rep_num": str(rep),
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
            nums = data["output"][0]
            return nums[:n], nums[n:], True
        # Invalid nonce or other error — clear cache so next call re-fetches
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


@app.route("/sources")
def sources():
    return render_template("sources.html", cards=CARDS)


if __name__ == "__main__":
    app.run(debug=True, port=7777, use_reloader=False)
