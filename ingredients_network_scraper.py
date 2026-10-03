"""
Objective 2 - IngredientsNetwork.com company scraper.

Flow (mirrors the challenge steps):
  1. Visit https://www.ingredientsnetwork.com/ and read the category navigation
     (used later to classify companies as Ingredients / Finished Products / ...).
  2. "Search" -> the supplier directory (/company/<letters>.html). The site's
     search results are rendered client-side from the same company records, so
     the server-rendered directory is the reliable, complete source of cards.
  3. Open every company profile and extract the required fields.
  4. Save the raw data to a temporary CSV, clean it (no empty / invalid
     required fields, no duplicates), and write the final CSV.
  5. Print the answers to the analysis questions.

Usage:  python ingredients_network_scraper.py [--limit N] [--workers 4]
"""
import argparse
import csv
import html as htmllib
import json
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
from lxml import html as lh

BASE = "https://www.ingredientsnetwork.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
RAW_CSV = "ingredients_raw_temp.csv"
FINAL_CSV = "ingredients_results.csv"
REQUIRED = ["Company Name", "Company Description", "Sales Markets", "Primary Business Activity",
            "Categories", "Events", "Address", "Email", "Telephone", "Website"]

session = requests.Session()
session.headers.update(HEADERS)


def get(url, retries=4, pause=1.5):
    """GET with retry/back-off; returns decoded HTML or None."""
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.content.decode("utf-8", errors="replace")
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(pause * (attempt + 1))
    return None


def clean(text):
    """Collapse whitespace; the site's text is otherwise kept raw."""
    return re.sub(r"\s+", " ", htmllib.unescape(text or "")).strip()


def decode_cfemail(hexstr):
    """Decode Cloudflare's email obfuscation (data-cfemail)."""
    key = int(hexstr[:2], 16)
    return "".join(chr(int(hexstr[i:i + 2], 16) ^ key) for i in range(2, len(hexstr), 2))


# --------------------------------------------------------------------------- #
# Step 1/2: navigation structure + company directory
# --------------------------------------------------------------------------- #
def load_nav_groups():
    """Map every category name to its top-level navigation group
    (Ingredients, Finished Products, Health & Wellness, Delivery Formats, ...)."""
    page = get(BASE + "/")
    doc = lh.fromstring(page)
    groups = {}
    for h in doc.xpath("//*[starts-with(normalize-space(text()),'Browse by')]"):
        group = clean(h.text_content()).replace("Browse by ", "")
        names = [clean(a.text_content()) for a in h.xpath("following::ul[1]//a")]
        for n in names:
            groups.setdefault(n, group)
    return groups


def directory_slugs():
    two = [a + b for a in string.ascii_lowercase for b in string.ascii_lowercase + "0"]
    return ["0-9"] + list(string.ascii_lowercase) + two + [a + "0-9" for a in string.ascii_lowercase]


def collect_company_urls(workers):
    def one(slug):
        page = get(f"{BASE}/company/{slug}.html")
        if not page:
            return []
        seg = page.split('<section class="suppliers">')[-1]
        return re.findall(r'href="(/[^"]*?-comp(\d+)\.html)"', seg)

    companies = {}
    with ThreadPoolExecutor(workers) as ex:
        for found in ex.map(one, directory_slugs()):
            for path, cid in found:
                companies[cid] = BASE + path
    return companies


# --------------------------------------------------------------------------- #
# Step 3: company profile parser
# --------------------------------------------------------------------------- #
def parse_company(cid, url):
    page = get(url)
    if not page:
        return None
    doc = lh.fromstring(page)

    def first(xp):
        r = doc.xpath(xp)
        return clean(r[0] if isinstance(r[0], str) else r[0].text_content()) if r else ""

    name = first("//div[contains(@class,'company-profile')]//h1")
    desc = clean(" ".join(
        p.text_content() for p in doc.xpath("//h3[normalize-space()='Company description']/following-sibling::p[1]")))

    quick = {}
    for tr in doc.xpath("//table[contains(@class,'quickfacts')]//tr"):
        k = clean(tr.xpath("string(th)")).rstrip(":").lower()
        quick[k] = clean(tr.xpath("string(td)"))

    # Full category list (top-level + sub-categories) from the "Categories affiliated with" block
    cats = [clean(a.text_content()) for a in doc.xpath(
        "//div[contains(@class,'company-categories')]//a")]
    cats = list(dict.fromkeys(c for c in cats if c))

    events = []
    for ev in doc.xpath("//div[contains(@class,'event') and not(contains(@class,'event-'))]"):
        title = clean(ev.xpath("string(h3)"))
        dates = clean(ev.xpath("string(.//span[@class='event-dates'])"))
        if title:
            events.append(f"{title} ({dates})" if dates else title)
    events = list(dict.fromkeys(events))

    contact = doc.xpath("//h3[normalize-space()='Address']/..")
    address = email = phone = website = ""
    if contact:
        c = contact[-1]
        address = clean(c.xpath("string(.//address)"))
        cf = c.xpath(".//span[@data-cfemail]/@data-cfemail")
        if cf:
            email = decode_cfemail(cf[0])
        else:
            mail = c.xpath(".//a[starts-with(@href,'mailto:')]/@href")
            email = mail[0].replace("mailto:", "") if mail else ""
        phone = clean(c.xpath("string(.//h3[normalize-space()='Telephone']/following-sibling::a[1])"))
        website = clean(c.xpath("string(.//h3[normalize-space()='Website']/following-sibling::a[1])"))

    return {
        "Company ID": cid,
        "Company Name": name,
        "Company Description": desc,
        "Sales Markets": quick.get("sales markets", ""),
        "Primary Business Activity": quick.get("primary business activity", ""),
        "Categories": " | ".join(cats),
        "Events": " | ".join(events),
        "Address": address,
        "Email": email,
        "Telephone": phone,
        "Website": website,
        "Company URL": url,
    }


# --------------------------------------------------------------------------- #
# Step 4: cleaning
# --------------------------------------------------------------------------- #
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def clean_dataframe(df):
    df = df.copy()
    for col in REQUIRED:
        df[col] = df[col].fillna("").astype(str).str.strip()
    ok = (df[REQUIRED] != "").all(axis=1)
    ok &= df["Email"].str.match(EMAIL_RE)
    ok &= df["Website"].str.match(r"^https?://", case=False)
    ok &= ~df["Email"].str.contains("protected", case=False)
    df = df[ok]
    df = df.drop_duplicates(subset=["Company ID"]).drop_duplicates(subset=["Company Name", "Website"])
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Step 5: analysis questions
# --------------------------------------------------------------------------- #
def has_cat(series, wanted):
    return series.apply(lambda s: wanted.lower() in [c.strip().lower() for c in s.split("|")])


def answer_questions(df, groups):
    def in_group(cats, group):
        return any(groups.get(c.strip()) == group for c in cats.split("|"))

    ingredients = df["Categories"].apply(lambda s: in_group(s, "Ingredients")).sum()
    finished = df["Categories"].apply(lambda s: in_group(s, "Finished Products")).sum()
    herbs = (has_cat(df["Categories"], "Herbs, Spices") | has_cat(df["Categories"], "Herbs")
             | has_cat(df["Categories"], "Spices")).sum()
    physical = has_cat(df["Categories"], "Physical Formats").sum()
    cognitive = has_cat(df["Categories"], "Cognitive & Mental Health").sum()
    print("\n=== ANSWERS (computed on the cleaned dataset) ===")
    print(f"(i)   Companies with ingredient categories : {ingredients}")
    print(f"(ii)  Companies with finished products     : {finished}")
    print(f"(iii) Companies with Herbs and Spices      : {herbs}")
    print(f"(iv)  Companies with Physical Formats      : {physical}")
    print(f"(v)   Companies in Cognitive & Mental Health: {cognitive}")
    print(f"Total companies in final CSV: {len(df)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only scrape the first N companies (testing)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    groups = load_nav_groups()
    print(f"Navigation categories mapped: {len(groups)}")
    companies = collect_company_urls(args.workers)
    print(f"Companies found in directory: {len(companies)}")
    items = list(companies.items())
    if args.limit:
        items = items[:args.limit]

    rows = []
    with ThreadPoolExecutor(args.workers) as ex:
        for i, rec in enumerate(ex.map(lambda kv: parse_company(*kv), items), 1):
            if rec:
                rows.append(rec)
            if i % 250 == 0:
                print(f"  scraped {i}/{len(items)}")
                pd.DataFrame(rows).to_csv(RAW_CSV, index=False, encoding="utf-8-sig")

    raw = pd.DataFrame(rows)
    raw.to_csv(RAW_CSV, index=False, encoding="utf-8-sig")           # temporary, pre-cleaning
    final = clean_dataframe(raw)
    final.to_csv(FINAL_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    print(f"Raw rows: {len(raw)}  ->  cleaned rows: {len(final)}  ({FINAL_CSV})")
    json.dump(groups, open("nav_groups.json", "w"))
    answer_questions(final, groups)


if __name__ == "__main__":
    main()
