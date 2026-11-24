# Chop Shop

VIN in, ranked list of sellable used parts with estimated resale value out, plus an honest
part-out vs. private-sale vs. instant-offer comparison.

The complete parts list for a car (Audi ETKA and the like) and used *sold* prices
(Hollander, Car-Part.com, eBay Marketplace Insights) are proprietary. This MVP works around
that legitimately: free NHTSA VIN decode, a curated Hollander-derived taxonomy of ~100 part
types that actually resell, and eBay Browse API asking prices with a haircut. See
`docs/PLAN.md` for the feasibility assessment and design.

## Run it

Two terminals.

```bash
# backend (FastAPI on :8000)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add eBay keys for live pricing (optional)
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (Vite on :5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Without eBay credentials the app uses built-in reference prices
and says so.

## Live eBay pricing

1. Create an eBay Developers Program account and a **production** keyset
   (sandbox returns mock data for parts-compatibility search). On the keyset's
   Alerts & Notifications page, turn on "Exempted from Marketplace Account Deletion"
   (this app stores no eBay user data) so the keyset becomes compliant.
2. Put the App ID as `EBAY_CLIENT_ID` and the Cert ID as `EBAY_CLIENT_SECRET` in
   `backend/.env` (locally) or the Render Environment tab (live site).
3. Check one part, with a breakdown of why each raw listing was kept or dropped:

   ```bash
   cd backend && .venv/bin/python -m scripts.price_one <VIN> headlamp_assembly 75201
   # add a drop-reason filter to list those listings, e.g. ... 75201 accessory
   ```

4. Price the whole car and print a tuning table:

   ```bash
   cd backend && .venv/bin/python -m scripts.price_all <VIN> 75201
   ```

How a price is built: the part's leaf category comes from eBay's Motors category tree
(or a pinned `ebay_category_id`); a compatibility-filtered search runs in that category in
best-match order; `pricing.clean_listings` drops accessories, wrong side/body/make/model/year
and "for parts" listings, splits pairs and dedupes; if fewer than 5 survive, a keyword search
with the vehicle terms tops it up. Exact fitment matches are preferred, outliers trimmed, and
the median asking price gets the asking-to-sold haircut, eBay fees and shipping by size class.

Raw lookups are cached in `backend/cache.db` for 7 days, so one vehicle costs roughly
150-250 Browse calls cold and none warm. Lookups run 8 in parallel (~25s cold locally).

The UI does not call `POST /api/valuate` directly: a cold vehicle can outlast a proxy
timeout as one request, so it calls `POST /api/valuate/start` and polls
`GET /api/valuate/jobs/{job_id}` for progress (`done`/`total`) until `status` is `done`.
Jobs live in process memory for 15 minutes; the synchronous endpoint remains for scripts.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
cd frontend && npm run typecheck
```

## Layout

- `backend/app/data/part_types.json` is the taxonomy. Each entry has a Hollander code, eBay
  keyword, size class (drives shipping estimate), removal hours, applicability rules
  (body / drive / transmission / turbo / options), option-specific keyword variants, and
  legal flag tags.
- `backend/app/services/legal.py` holds the Texas-specific title, license, airbag and
  catalytic-converter rules.
- `backend/app/services/pricing.py` is the asking-to-net math.
