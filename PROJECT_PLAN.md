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

## Unverified (come back to these)
1. **eBay production keyset.** Nothing live has been tested. Create a Developers Program
   account, put a PRODUCTION `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` in `backend/.env`.
   Sandbox returns mock data for compatibility search, so it cannot stand in.
2. **eBay filter syntax and category resolution.** `conditions:{USED}` in the Browse
   `filter` param and the Taxonomy-API category lookup in
   `backend/app/services/ebay_browse.py` have not hit production. Validate with
   `cd backend && .venv/bin/python -m scripts.price_one <VIN> headlamp_assembly 75201`.
   A 400 means adjust the filter per eBay's Buy API field-filters page.
3. **True mobile check at 390px.** Headless Chrome enforces a ~500px minimum window, so the
   layout was only confirmed at 600px. Open http://localhost:5173 on a phone or in devtools
   device mode and check: no horizontal scroll, strip and ledger stack, chips wrap.
4. **Haircut tuning.** `ASKING_TO_SOLD = 0.75` and `SHIPPING_BY_SIZE` in
   `backend/app/services/pricing.py` are guesses. Spot-check 10 parts against eBay's sold
   filter in the browser and adjust per size class.
5. **Texas title path for an undamaged car.** TxDMV says it won't issue a salvage title for
   an undamaged vehicle; the nonrepairable-title route via VTR-441 needs confirming with
   TxDMV before any dismantling.

## Deployment (live since 2026-11-23)
- URL: https://chop-shop-k6ws.onrender.com (one Render web service, python runtime, free plan,
  Oregon; service `srv-dc133qff3r2c73bf2ofg` in the City-Sites workspace). Build installs
  `backend/requirements.txt`, runs `npm ci && npm run build` in `frontend/`, and uvicorn
  serves `frontend/dist` as static files.
- **Live eBay pricing:** in the Render dashboard open the service, Environment tab, add
  `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` (production keyset: App ID = client id,
  Cert ID = client secret), save. Render redeploys on save. Confirm with
  `GET /api/status` returning `"ebay_configured": true`.
- Deploys do not fire on push: the Render GitHub app is not installed on VentureT, so
  trigger them from the dashboard ("Manual Deploy") or via the Render MCP `trigger_deploy`.
- The repo was made public on 2026-11-23 only so Render could fetch it. Once the Render
  GitHub app is installed for VentureT, flip it back:
  `gh repo edit VentureT/chop-shop --visibility private --accept-visibility-change-consequences`.
- `@venturet/theme` and `@venturet/docs-viewer` are vendored as tarballs in
  `frontend/vendor/` because Render's build box cannot read private VentureT repos over
  git+ssh. To return to the house git-dep convention: restore the `git+https://...#semver`
  specs in `frontend/package.json`, add a `GITHUB_TOKEN` env var on Render, and set
  `git config url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"`
  in the build command (as city-sites does).
- `render.yaml` describes the same service but is not linked; the service was created via
  the Render MCP, so edit settings in the dashboard, not the blueprint.
