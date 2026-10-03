"""Flask app showing the scraped Disney Cruise and Ingredients Network data.

Data source: Supabase (set SUPABASE_URL and SUPABASE_ANON_KEY); falls back to the local CSVs if unset.
"""
import os

import pandas as pd
from flask import Flask, render_template, request

app = Flask(__name__)
DATA = os.path.join(os.path.dirname(__file__), "data")
PAGE_SIZE = 25

# key -> (title, csv file, supabase table, {db column: display name})
SETS = {
    "cruises": ("Disney Cruises", "disney_results.csv", "disney_cruises", {
        "title": "Title", "special_offer": "Special Offer", "departing_from": "Departing From",
        "duration": "Duration", "sailing_to": "Sailing To", "price_from_inr": "Price From (INR)",
        "guests": "Guests", "number_of_dates": "Number of Dates", "theme_banner": "Theme Banner",
        "holiday_cruise": "Holiday Cruise"}),
    "companies": ("Ingredients Network Companies", "ingredients_results.csv", "ingredient_companies", {
        "company_id": "Company ID", "company_name": "Company Name",
        "company_description": "Company Description", "sales_markets": "Sales Markets",
        "primary_business_activity": "Primary Business Activity", "categories": "Categories",
        "events": "Events", "address": "Address", "email": "Email", "telephone": "Telephone",
        "website": "Website", "company_url": "Company URL"}),
}
# text columns searched with ILIKE
SEARCH_COLS = {
    "cruises": ["title", "departing_from", "sailing_to", "special_offer", "theme_banner"],
    "companies": ["company_name", "company_description", "sales_markets", "primary_business_activity",
                  "categories", "events", "address", "email", "website"],
}

SB_URL, SB_KEY = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_ANON_KEY")
supabase = None
if SB_URL and SB_KEY:
    from supabase import create_client
    supabase = create_client(SB_URL, SB_KEY)

_csv_cache = {}


def from_supabase(key, q, page):
    _, _, table, cols = SETS[key]
    query = supabase.table(table).select(",".join(cols), count="exact")
    if q:
        safe = q.replace(",", " ").replace("(", " ").replace(")", " ")
        query = query.or_(",".join(f"{c}.ilike.%{safe}%" for c in SEARCH_COLS[key]))
    start = (page - 1) * PAGE_SIZE
    res = query.order(next(iter(cols))).range(start, start + PAGE_SIZE - 1).execute()
    return [[r[c] for c in cols] for r in res.data], res.count


def from_csv(key, q, page):
    if key not in _csv_cache:
        _csv_cache[key] = pd.read_csv(os.path.join(DATA, SETS[key][1]), encoding="utf-8-sig").fillna("")
    df = _csv_cache[key]
    if q:
        mask = df.astype(str).apply(lambda c: c.str.contains(q, case=False, regex=False)).any(axis=1)
        df = df[mask]
    start = (page - 1) * PAGE_SIZE
    return df.iloc[start:start + PAGE_SIZE].values.tolist(), len(df)


@app.route("/")
def index():
    key = request.args.get("set", "cruises")
    if key not in SETS:
        key = "cruises"
    q = request.args.get("q", "").strip()
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    rows, total = (from_supabase if supabase else from_csv)(key, q, page)
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    return render_template("index.html", sets={k: (v[0], v[1]) for k, v in SETS.items()}, key=key, q=q,
                           page=page, pages=pages, total=total, columns=list(SETS[key][3].values()),
                           rows=rows, source="Supabase" if supabase else "local CSV")


if __name__ == "__main__":
    app.run(debug=True)
