# Relu Consultancy Hiring Challenge – Data Extraction Engineer

Two web scrapers, their cleaned datasets, and a small web app (bonus) that serves the data from Supabase.

**Live app:** https://relu-data-extraction-challenge-1.onrender.com/
(Hosted on Render's free tier – the first load after idle can take ~30 seconds.)

## Repository layout

| Path | What it is |
|---|---|
| `disney_cruise_scraper.py` | Objective 1 – Disney Cruise Line scraper (Playwright) |
| `disney_results.csv` | Objective 1 – cleaned output |
| `ingredients_network_scraper.py` | Objective 2 – Ingredients Network scraper (requests + lxml) |
| `ingredients_results.csv` | Objective 2 – cleaned output |
| `Disney_Cruise_Scraper.ipynb`, `Ingredients_Network_Scraper.ipynb` | Optional Google Colab notebooks that embed the scripts |
| `bonus_app/` | Flask web app, Supabase schema and upload script |

## Objective 1 – disneycruise.disney.go.com

**Approach** (`disney_cruise_scraper.py`)
1. Opens `https://disneycruise.disney.go.com/en-in/` and declines optional cookies.
2. Clicks **View Dates** (optionally applies a destination filter with `--destination`).
3. Waits for the cruise cards, then scrolls the infinite list to the end (about 34–35 pages).
4. Parses each card: title, special offer, departing port, duration, ports sailed to, price from (INR), guests and number of available dates.
5. Saves the raw data to `disney_raw_temp.csv`, cleans it, and writes `disney_results.csv`.

**Cleaning rules:** required fields must not be empty (the special-offer badge is optional), exact duplicates are removed, and cruises with no "Sailing to" location are dropped (use `--keep-no-port` to keep them).

**Analysis numbers.** Totals and filter counts come from the same API the site's front end calls. The live inventory changes slightly between runs.

| Question | Answer |
|---|---|
| Cruises with Pacific (Pacific Coast) as destination | 5 |
| Total cruises | 948 (about 170 distinct cards) |
| Holiday cruises | 27 (title keywords; the site's own holiday themes cover 33 titles) |
| Cruises with more than 2 dates | 67 |
| Departing from Miami / London | 0 / 0 |

## Objective 2 – ingredientsnetwork.com

**Approach** (`ingredients_network_scraper.py`)
1. Reads the category navigation on the home page.
2. Walks the A–Z supplier directory (about 9,600 companies). The site's search results are rendered client-side from these same records, so the server-rendered directory is the complete source.
3. Opens every company profile and extracts: company name, description, sales markets, primary business activity, categories, events, address, email (Cloudflare-obfuscated emails are decoded), telephone and website.
4. Saves everything to `ingredients_raw_temp.csv`, cleans it, and writes `ingredients_results.csv`.

**Cleaning rules:** every required field must be present, the email must be valid, the website must start with `http(s)://`, and duplicates are removed. Most free listings lack an email, website or events, so 9,647 raw companies reduce to **713** complete records.

| Question | Answer (on the cleaned data) |
|---|---|
| Companies with ingredient categories | 296 |
| Companies with finished-product categories | 421 |
| Companies with Herbs & Spices | 145 |
| Companies with Physical Formats | 325 |
| Companies in Cognitive & Mental Health | 171 |

The first two answers use the site's navigation groups ("Ingredients", "Finished Products") to classify categories.

## Running the scrapers

Requirements: Python 3.10+.

```bash
pip install pandas requests lxml playwright flask
playwright install chromium
```

```bash
python disney_cruise_scraper.py              # add --headless on a server
python ingredients_network_scraper.py        # add --limit 100 for a quick test
```

Each script prints its answers to the terminal when it finishes. The Disney script uses Microsoft Edge on Windows and falls back to bundled Chromium; on Linux (including Colab) it runs headless automatically.

### Google Colab
Upload one of the `.ipynb` notebooks via File → Upload notebook and choose Runtime → Run all. Each notebook installs its dependencies, writes the script, runs it, and downloads the CSV. Colab uses cloud IP addresses, which the target sites may throttle or block.

## Bonus – web app (`bonus_app/`)

A Flask app that shows both datasets in searchable, paginated tables.

- **Data source:** Supabase when `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set; otherwise it falls back to the bundled CSVs in `bonus_app/data/`. The page header shows which source is active.
- **Schema:** `bonus_app/schema.sql` creates the `disney_cruises` and `ingredient_companies` tables and enables read-only access for the public key.
- **Upload:** `bonus_app/upload_to_supabase.py` loads the CSVs into Supabase.

```bash
cd bonus_app
pip install -r requirements.txt

# 1. Create the tables: run schema.sql in the Supabase SQL editor
# 2. Upload the data (use the secret key, keep it private; never commit it)
export SUPABASE_URL=https://<project>.supabase.co
export SUPABASE_SERVICE_KEY=<secret key>
python upload_to_supabase.py

# 3. Run the app with the read-only publishable key
export SUPABASE_ANON_KEY=<publishable key>
python app.py
```

On PowerShell, set variables with `$env:SUPABASE_URL="..."` instead of `export`.

**Deployment (Render):** create a Web Service from this repo with Root Directory `bonus_app`, build command `pip install -r requirements.txt`, start command `gunicorn app:app`, and the environment variables `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `PYTHON_VERSION=3.12.3`.

## Notes and limitations
- Requests are kept polite (a handful of concurrent workers with retry and back-off).
- The live Disney inventory and prices change over time, so counts can differ slightly from run to run.
- Never commit the Supabase secret key; the deployed app only needs the publishable key.
