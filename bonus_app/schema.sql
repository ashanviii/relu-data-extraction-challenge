-- Run in the Supabase SQL editor.
create table if not exists public.disney_cruises (
  id bigint generated always as identity primary key,
  title text not null,
  special_offer text,
  departing_from text not null,
  duration text not null,
  sailing_to text not null,
  price_from_inr text not null,
  guests text not null,
  number_of_dates integer not null,
  theme_banner text,
  holiday_cruise text not null
);

create table if not exists public.ingredient_companies (
  company_id bigint primary key,
  company_name text not null,
  company_description text not null,
  sales_markets text not null,
  primary_business_activity text not null,
  categories text not null,
  events text not null,
  address text not null,
  email text not null,
  telephone text not null,
  website text not null,
  company_url text
);

-- If the disney_cruises table already exists, add the new column instead:
-- alter table public.disney_cruises add column if not exists theme_banner text;

-- Allow the web app (anon key) to read, not write.
alter table public.disney_cruises enable row level security;
alter table public.ingredient_companies enable row level security;
drop policy if exists "public read" on public.disney_cruises;
create policy "public read" on public.disney_cruises for select using (true);
drop policy if exists "public read" on public.ingredient_companies;
create policy "public read" on public.ingredient_companies for select using (true);
