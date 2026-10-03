"""
Objective 1 - disneycruise.disney.go.com cruise scraper (Playwright + Microsoft Edge/Chromium).

Steps (mirrors the challenge):
  1. Open https://disneycruise.disney.go.com/en-in/ and decline optional cookies.
  2. Click "View Dates" (optionally choosing filters via CLI flags).
  3. Wait for the cruise cards to render.
  4. Scroll to the end of the page (infinite scroll, 35 "pages" of cards) and collect every card.
  5. Save raw data to a temporary CSV, clean it (no empty fields, no duplicates,
     locations present) and write the final CSV.
  6. Print the answers to the analysis questions.

Usage:  python disney_cruise_scraper.py [--headless] [--destination pacific-coast-cruises]
"""
import argparse
import json
import re
import sys

import pandas as pd
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = "https://disneycruise.disney.go.com/en-in/"
API = "/dcl-apps-productavail-vas/available-products/"
RAW_CSV = "disney_raw_temp.csv"
FINAL_CSV = "disney_results.csv"
COLUMNS = ["Title", "Special Offer", "Departing From", "Duration", "Sailing To",
           "Price From (INR)", "Guests", "Number of Dates", "Holiday Cruise"]
HOLIDAY_WORDS = ("merrytime", "halloween", "christmas", "thanksgiving", "new year", "holiday",
                 "memorial", "presidents", "july", "easter", "spooky", "valentine")


# --------------------------------------------------------------------------- #
# Browser helpers
# --------------------------------------------------------------------------- #
def decline_cookies(page):
    """Choose the most privacy-preserving option on the consent banner, if shown."""
    try:
        page.locator("#onetrust-reject-all-handler").click(timeout=4000)
    except PWTimeout:
        pass


def api_search(page, filters, page_no=1):
    """POST the same request the site's front end makes; returns parsed JSON."""
    filters = [f if ";" in f else f"{f};filterId=urlFriendlyId" for f in filters]
    body = {"currency": "INR", "filters": filters,
            "partyMix": [{"accessible": False, "adultCount": 2, "childCount": 0,
                          "nonAdultAges": [], "partyMixId": "0"}],
            "region": "INTL", "storeId": "DCL", "affiliations": [], "page": page_no,
            "pageHistory": False, "includeAdvancedBookingPrices": True,
            "exploreMorePage": 1, "exploreMorePageHistory": False,
            "sorts": [{"criteria": "RECOMMENDED", "order": "ASC", "region": "MP"}]}
    return page.evaluate(
        """async ([url, body]) => (await fetch(url, {method:'POST',
              headers:{'content-type':'application/json'}, body: JSON.stringify(body)})).json()""",
        [API, body])


def open_results(page, destination=None):
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_selector("button.view-cruises-button", timeout=60000)
    decline_cookies(page)
    if destination:                                    # optional programmatic filter
        page.get_by_text("Sailing to").first.click()
        page.locator(f"a[href*='{destination}'], text=/{destination}/i >> visible=true").first.click()
    page.locator("button.view-cruises-button").click()           # "View Dates"
    page.wait_for_selector("dcl-product-card", timeout=60000)    # wait till cards load


def scroll_to_end(page, expected_cards):
    """Infinite scroll until every card is in the DOM (or no more cards appear)."""
    last, stalls = 0, 0
    while True:
        count = page.locator("dcl-product-card").count()
        if count >= expected_cards:
            break
        stalls = stalls + 1 if count == last else 0
        if stalls >= 8:
            break
        last = count
        page.mouse.wheel(0, 25000)
        page.wait_for_timeout(1200)
    print(f"Cards loaded in DOM: {page.locator('dcl-product-card').count()}")


# --------------------------------------------------------------------------- #
# Card parsing
# --------------------------------------------------------------------------- #
def parse_card(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = next((l for l in lines if re.search(r"-Night", l)), "")
    offer = next((l for l in lines if l.lower().startswith("guaranteed")), "")
    price = next((l for l in lines if "INR" in l), "")
    guests = next((l for l in lines if re.search(r"\d+ Guests?", l)), "")
    dates = next((re.search(r"Show (\d+) Dates?", l).group(1) for l in lines
                  if re.search(r"Show \d+ Dates?", l)), "")
    sailing_to = ""
    if "Sailing to" in lines:
        i = lines.index("Sailing to") + 1
        j = next((k for k in range(i, len(lines)) if lines[k].startswith("Price from")), len(lines))
        sailing_to = " | ".join(lines[i:j])
    m = re.search(r"from (.+)$", title)
    nights = re.search(r"(\d+)-Night", title)
    return {
        "Title": title,
        "Special Offer": offer,
        "Departing From": m.group(1).strip() if m else "",
        "Duration": f"{nights.group(1)} Nights" if nights else "",
        "Sailing To": sailing_to,
        "Price From (INR)": price.replace("INR", "").strip(),
        "Guests": guests,
        "Number of Dates": dates,
        "Holiday Cruise": "Yes" if any(w in title.lower() for w in HOLIDAY_WORDS) else "No",
    }


def clean(df, keep_no_port=False):
    df = df.copy()
    for c in COLUMNS:
        df[c] = df[c].fillna("").astype(str).str.strip()
    required = [c for c in COLUMNS if c not in ("Special Offer",)]      # offer badge is optional
    if keep_no_port:
        required.remove("Sailing To")
    df = df[(df[required] != "").all(axis=1)]
    df = df.drop_duplicates().reset_index(drop=True)
    return df


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--destination", help="urlFriendlyId, e.g. pacific-coast-cruises")
    ap.add_argument("--keep-no-port", action="store_true",
                    help="keep cruises that have no 'Sailing to' port (default: dropped per cleaning rule)")
    args = ap.parse_args()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=args.headless)
        except Exception:
            browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        open_results(page, args.destination)

        filters = [args.destination] if args.destination else []
        first = api_search(page, filters)
        total_pages, total_cruises = first["totalPages"], first["totalAvailableCruises"]
        per_page = len(first["products"])
        print(f"Site reports {total_cruises} cruises over {total_pages} pages")
        scroll_to_end(page, total_pages * per_page)

        texts = page.evaluate("[...document.querySelectorAll('dcl-product-card')].map(c => c.innerText)")
        rows = [parse_card(t) for t in texts]
        pd.DataFrame(rows, columns=COLUMNS).to_csv(RAW_CSV, index=False, encoding="utf-8-sig")  # temporary

        # --- numbers for the analysis questions come from the same API the page uses ---
        def count(filters_):
            r = api_search(page, filters_)
            return r["totalAvailableCruises"], r["totalPages"]

        pacific = count(["pacific-coast-cruises"])
        holiday_titles = set()
        for theme in ("merry", "spooky", "mdas", "pdas"):
            r = api_search(page, [theme])
            for pg_no in range(1, r["totalPages"] + 1):
                resp = r if pg_no == 1 else api_search(page, [theme], pg_no)
                holiday_titles |= {(pr["productDisplayName"]) for pr in resp["products"]}
        browser.close()

    raw = pd.DataFrame(rows, columns=COLUMNS)
    final = clean(raw, args.keep_no_port)
    final.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig")
    print(f"Raw cards: {len(raw)} -> cleaned: {len(final)}  ({FINAL_CSV})")

    dep = raw["Departing From"].str.lower()
    print("\n=== ANSWERS ===")
    print(f"(i)   Cruises with Pacific (Pacific Coast) as destination: {pacific[0]}")
    print(f"(ii)  Total cruises on the site                          : {total_cruises} "
          f"({len(raw)} distinct cruise cards)")
    print(f"(iii) Holiday cruises (cards)                            : "
          f"{int((raw['Holiday Cruise'] == 'Yes').sum())}  (distinct holiday-theme titles on site: {len(holiday_titles)})")
    print(f"(iv)  Cruises offering more than 2 dates                 : "
          f"{int((pd.to_numeric(raw['Number of Dates'], errors='coerce') > 2).sum())}")
    print(f"(v)   Cruises departing from Miami / London              : "
          f"Miami={int(dep.str.contains('miami').sum())}, London={int(dep.str.contains('london').sum())}")


if __name__ == "__main__":
    sys.exit(main())
