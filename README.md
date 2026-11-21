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
   (sandbox returns mock data for parts-compatibility search).
2. Put `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in `backend/.env`.
3. Validate one part before running the whole loop:

   ```bash
   cd backend && .venv/bin/python -m scripts.price_one <VIN> headlamp_assembly 75201
   ```

Lookups are cached in `backend/cache.db` for 7 days, so one vehicle costs roughly 100
Browse calls cold and none warm.

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
