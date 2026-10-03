"""Upload the cleaned CSVs to Supabase.

Set environment variables first (use the service_role key, kept secret, for uploading):
    SUPABASE_URL=https://<project>.supabase.co
    SUPABASE_SERVICE_KEY=<service_role key>
Usage: python upload_to_supabase.py
"""
import os
import pandas as pd
from supabase import create_client

DATA = os.path.join(os.path.dirname(__file__), "data")
JOBS = [
    ("disney_cruises", "disney_results.csv", {
        "Title": "title", "Special Offer": "special_offer", "Departing From": "departing_from",
        "Duration": "duration", "Sailing To": "sailing_to", "Price From (INR)": "price_from_inr",
        "Guests": "guests", "Number of Dates": "number_of_dates", "Theme Banner": "theme_banner",
        "Holiday Cruise": "holiday_cruise"}),
    ("ingredient_companies", "ingredients_results.csv", {
        "Company ID": "company_id", "Company Name": "company_name",
        "Company Description": "company_description", "Sales Markets": "sales_markets",
        "Primary Business Activity": "primary_business_activity", "Categories": "categories",
        "Events": "events", "Address": "address", "Email": "email", "Telephone": "telephone",
        "Website": "website", "Company URL": "company_url"}),
]


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    for table, csv_name, cols in JOBS:
        df = pd.read_csv(os.path.join(DATA, csv_name), encoding="utf-8-sig").fillna("").rename(columns=cols)
        records = df.to_dict("records")
        if table == "disney_cruises":                       # no natural key: clear first so reruns do not duplicate
            sb.table(table).delete().gt("id", 0).execute()
        for i in range(0, len(records), 200):                       # batch inserts
            sb.table(table).upsert(records[i:i + 200]).execute() if table == "ingredient_companies" \
                else sb.table(table).insert(records[i:i + 200]).execute()
        print(f"{table}: uploaded {len(records)} rows")


if __name__ == "__main__":
    main()
