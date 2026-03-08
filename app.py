import json
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "tarot.json")

with open(DATA_PATH, encoding="utf-8") as f:
    CARDS = json.load(f)["cards"]


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

        if (query in name or query in name_en or
                query in suit or query in number or
                name in query):
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


@app.route("/sources")
def sources():
    return render_template("sources.html", cards=CARDS)


if __name__ == "__main__":
    app.run(debug=True, port=7777, use_reloader=False)
