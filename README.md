# Relu Consultancy Hiring Challenge: Data Extraction Engineer

My solution to the Relu Consultancy data extraction challenge: two production-style scrapers (Disney Cruise Line and Ingredients Network), their cleaned datasets, and a deployed web app that serves the data from Supabase.

| | |
|---|---|
| **Live app** | https://relu-data-extraction-challenge-1.onrender.com/ |
| **Stack** | Python, Playwright, requests, lxml, pandas, Flask, Supabase (Postgres), Render |

> The app runs on Render's free tier, so the first request after a quiet period can take about 30 seconds while the service wakes up.

---

## Contents
1. [Repository layout](#repository-layout)
2. [Objective 1: Disney Cruise Line](#objective-1-disney-cruise-line)
3. [Objective 2: Ingredients Network](#objective-2-ingredients-network)
4. [Bonus: Supabase and web app](#bonus-supabase-and-web-app)
5. [Running everything yourself](#running-everything-yourself)
6. [Design decisions, assumptions and limitations](#design-decisions-assumptions-and-limitations)

---

## Repository layout

```
.
├── disney_cruise_scraper.py          # Objective 1 scraper (Playwright)
├── disney_results.csv                # Objective 1 cleaned output
├── ingredients_network_scraper.py    # Objective 2 scraper (requests + lxml)
├── ingredients_results.csv           # Objective 2 cleaned output
├── Disney_Cruise_Scraper.ipynb       # Google Colab version of the Disney scraper
├── Ingredients_Network_Scraper.ipynb # Google Colab version of the Ingredients scraper
└── bonus_app/
    ├── app.py                        # Flask app (Supabase, with CSV fallback)
    ├── schema.sql                    # Supabase tables and read-only policies
    ├── upload_to_supabase.py         # loads the CSVs into Supabase
    ├── templates/index.html
    ├── data/                         # CSV copies used as a fallback source
    ├── requirements.txt
    └── render.yaml                   # Render service definition
```

---

## Objective 1: Disney Cruise Line

**Target:** `https://disneycruise.disney.go.com/en-in/`

### How it works
1. Opens the site in a real browser (Playwright; Microsoft Edge on Windows, Chromium elsewhere) and declines optional cookies.
2. Clicks **View Dates**. A destination filter can be applied with `--destination`.
3. Waits for the cruise cards to render, then scrolls the infinite list to the end. The site reports about 34-35 pages of results.
4. Reads every card from the DOM: title, special-offer badge, departing port, duration, ports sailed to, starting price, guests, number of available dates and the themed banner (for example "Very Merrytime").
5. Writes the raw data to `disney_raw_temp.csv`, cleans it, and saves `disney_results.csv`.

### Output columns
`Title`, `Special Offer`, `Departing From`, `Duration`, `Sailing To`, `Price From (INR)`, `Guests`, `Number of Dates`, `Theme Banner`, `Holiday Cruise`

### Cleaning rules
- No empty fields, except the two that are genuinely optional (`Special Offer` and `Theme Banner`).
- Exact duplicates are removed.
- Every cruise must have a location. Cruises with no "Sailing to" port are dropped (`--keep-no-port` keeps them).
- Ports are stored as a single ` | `-separated string.

### Answers to the analysis questions
Totals and filter counts come from the same API the website's own front end calls, so they match what the site displays.

| Question | Answer |
|---|---|
| Cruises with Pacific (Pacific Coast) as the destination | **5** |
| Total cruises | **947** (171 distinct cruise cards) |
| Holiday cruises | **71** cards |
| Cruises offering more than 2 dates | **67** |
| Cruises departing from Miami / London | **0 / 0** |

Notes on these numbers:
- "Total cruises" is the figure in the site's results header, which counts individual sailings. The 171 cards group those sailings by itinerary.
- A holiday cruise is a card carrying a "Very Merrytime" or "Halloween on the High Seas" banner. The site's own holiday filters list 234 sailings for the same cruises.
- The site only departs from Barcelona, Civitavecchia, Fort Lauderdale, Galveston, New York, Port Canaveral, San Diego, San Juan, Singapore, Southampton and Vancouver, which is why Miami and London are 0.
- The live inventory changes, so counts can move slightly between runs.

---

## Objective 2: Ingredients Network

**Target:** `https://www.ingredientsnetwork.com/`

### How it works
1. Reads the category navigation on the home page to learn how categories group under Ingredients, Finished Products, Health & Wellness and Delivery Formats.
2. Walks the A-Z supplier directory, which lists about 9,600 companies. The site's search results are built client-side from these same company records, so the directory is the complete and stable source for every card.
3. Opens each company profile and extracts the required fields. Emails are obfuscated by Cloudflare on the page and are decoded back to the real address.
4. Writes everything to `ingredients_raw_temp.csv`, cleans it, and saves `ingredients_results.csv`.

### Output columns
`Company ID`, `Company Name`, `Company Description`, `Sales Markets`, `Primary Business Activity`, `Categories`, `Events`, `Address`, `Email`, `Telephone`, `Website`, `Company URL`

### Cleaning rules
- All ten required fields must be present and non-empty.
- The email must be a valid address and the website must start with `http://` or `https://`.
- Duplicates are removed (by company ID, and by name plus website).

Most free listings on the site have no email, website or events. Applying the "no empty or inaccurate fields" rule strictly takes **9,647 scraped companies down to 713 complete records**. The untouched raw data is saved to the temporary CSV before cleaning, as the brief asks.

### Answers to the analysis questions (on the cleaned dataset)

| Question | Answer |
|---|---|
| Companies with ingredient categories | **296** |
| Companies with finished-product categories | **421** |
| Companies with Herbs & Spices | **145** |
| Companies with Physical Formats | **325** |
| Companies in Cognitive & Mental Health | **171** |

The first two use the site's own navigation groups ("Ingredients" and "Finished Products") to classify each company's categories.

---

## Bonus: Supabase and web app

- **Persistence:** the cleaned CSVs are stored in two Supabase (Postgres) tables, `disney_cruises` and `ingredient_companies`. Row-level security is on, with a read-only policy so the public key can read but never write.
- **Web app:** a small Flask app shows both datasets in clean, searchable, paginated tables. Switch datasets with the dropdown.
- **Source switching:** when `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set, the app reads from Supabase and queries only the 25 rows it needs per page. Without them it falls back to the bundled CSVs, so it also runs offline. The page header shows which source is active.
- **Deployment:** hosted on Render (see the live link at the top).

---

## Running everything yourself

Requirements: Python 3.10 or newer.

```bash
pip install pandas requests lxml playwright flask supabase
playwright install chromium
```

### Scrapers
```bash
python disney_cruise_scraper.py              # add --headless on a server
python ingredients_network_scraper.py        # add --limit 100 for a quick test run
```
Each script prints its answers to the terminal when it finishes. The full Ingredients run makes roughly 9,600 requests and takes around 10-20 minutes.

### Google Colab
Upload either `.ipynb` notebook (File, then Upload notebook) and choose Runtime, then Run all. The notebook installs its dependencies, writes the script, runs it and offers the CSV for download. The Disney notebook runs the browser inside a virtual display (`xvfb`) so it behaves like a normal desktop browser. Colab runs on cloud IP addresses, which the target sites may throttle.

### Web app and Supabase
```bash
cd bonus_app
pip install -r requirements.txt
```
1. Create a Supabase project and run `schema.sql` in the SQL editor.
2. Upload the data with the project's **secret** key (keep it private and never commit it):
   ```bash
   export SUPABASE_URL=https://<project>.supabase.co
   export SUPABASE_SERVICE_KEY=<secret key>
   python upload_to_supabase.py
   ```
3. Run the app with the read-only **publishable** key:
   ```bash
   export SUPABASE_ANON_KEY=<publishable key>
   python app.py
   ```

On Windows PowerShell, set variables with `$env:SUPABASE_URL="..."` instead of `export`.

### Deploying to Render
Create a Web Service from this repo with:
- Root Directory: `bonus_app`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `PYTHON_VERSION=3.12.3`

---

## Design decisions, assumptions and limitations

- **Real browser for Disney, plain HTTP for Ingredients.** Disney renders everything client-side and uses bot protection, so Playwright drives a real browser. Ingredients Network serves its profiles as normal HTML, so requests plus lxml is faster and lighter on the site.
- **Reading structure, not guessing from text.** Ports come from the card's list elements and the holiday flag from the card's banner, rather than from parsing flattened text. This avoids mis-splitting ports and false holiday matches.
- **Politeness.** The Ingredients scraper uses a small worker pool with retries and back-off, and Disney is scraped in a single browser session.
- **Strict cleaning has a cost.** Requiring every field means many real cruises or companies are excluded (cruises without a port; companies without an email, website or events). The raw temporary CSVs keep everything.
- **Ambiguous question wording.** "Total ingredients" and "total finished products" for Ingredients Network are interpreted as the number of cleaned companies in each navigation group. If the site's own filter counts are meant instead, those two figures would differ.
- **Live data moves.** Disney inventory and prices change over time, so a re-run can give slightly different counts.
- **Secrets.** The Supabase secret key is only used locally for the one-off upload. The deployed app uses the publishable key, which can only read.
