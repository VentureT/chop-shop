# Project plan

Narrow MVP, built. See `docs/PLAN.md` for the full plan and feasibility assessment.

## Done
- FastAPI backend: vPIC decode, Hollander-derived taxonomy (~115 part types), eBay Browse
  client with Taxonomy-API category resolution and compatibility search, SQLite TTL cache,
  pricing math, Texas legal flags, valuation and comparison endpoints, 17 tests.
- Vite + React + antd frontend on the shared VentureT theme: VIN entry, vehicle sheet with
  options, parts ledger with proportional value bars, compare board, rules sheet.

## Next
1. Add production eBay keyset; run `scripts/price_one.py` on the A5 to confirm the
   `conditions:{USED}` filter and category resolution; tune haircuts per size class.
2. Spot-check 10 part prices against eBay sold filter manually.
3. Apply for eBay Marketplace Insights (sold data) via Application Growth Check.
4. Consider Audi-specific PR-code entry to replace the manual options checklist.
