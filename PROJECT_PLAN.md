# Project plan

Narrow MVP, built. See `docs/PLAN.md` for the full plan and feasibility assessment.

## Done
- FastAPI backend: vPIC decode, Hollander-derived taxonomy (~115 part types), eBay Browse
  client with Taxonomy-API category resolution and compatibility search, SQLite TTL cache,
  pricing math, Texas legal flags, valuation and comparison endpoints, 17 tests.
- Vite + React + antd frontend on the shared VentureT theme: VIN entry, vehicle sheet with
  options, parts ledger with proportional value bars, compare board, rules sheet.

## Next
1. Spot-check 10 live part prices against eBay's sold filter manually; tune
   `ASKING_TO_SOLD` and `SHIPPING_BY_SIZE` per size class in `backend/app/services/pricing.py`.
2. Keep tuning the title rules in `backend/app/data/part_types.json` (`title_any`,
   `title_none`, `title_allow`) using
   `python -m scripts.price_one <VIN> <part_id> 75201 [drop-reason filter]`, which prints why
   each listing was dropped, and `python -m scripts.price_all <VIN>` for the whole car.
3. Apply for eBay Marketplace Insights (sold data) via Application Growth Check.
4. Consider Audi-specific PR-code entry to replace the manual options checklist.

## Verified 2026-11-24 (production eBay keyset)
- Client-credentials auth, `conditions:{USED}`, `buyingOptions:{FIXED_PRICE|BEST_OFFER}` and
  `compatibility_filter=Year:2015;Make:Audi;Model:A5` are all accepted by the Browse API.
- Category resolution must use the **eBay Motors category tree (id 100)** with marketplace
  header `EBAY_MOTORS_US`; tree 0 suggests heavy-equipment and consumer-electronics categories
  for car parts. Tree 100 resolves all 121 taxonomy queries; 11 are pinned via
  `ebay_category_id` where the suggestion was wrong (key fobs -> Carburetors, etc.).
- `sort=price` returned the 200 cheapest accessories in the category; best-match order is used.
- eBay's `compatibilityMatch=EXACT` is the seller's fitment claim and is unreliable (a Ford
  Escape turbo and a VW Tiguan bumper came back EXACT for the A5). `pricing.clean_listings`
  therefore checks titles for accessory words, wrong side, body style, make, model family and
  model-year ranges, drops "for parts" listings, splits pairs, dedupes and applies a price floor.
  Before cleaning, a headlight priced at $50 (ballasts); after, $475 with 43 comparables.
- Raw eBay responses are cached for 7 days; cleaning is applied on read, so rule changes do
  not need refetching. One cold vehicle is ~150-250 Browse calls.
- `conditions:{USED}` still returns "For parts or not working" and "Remanufactured"; both are
  dropped client-side unless the part allows remanufactured (wheels).
- Render's proxy drops a request at 60s and the free instance is ~8x slower than a laptop, so
  a cold vehicle cannot be one request. Valuations run as background jobs
  (`POST /api/valuate/start`, `GET /api/valuate/jobs/{id}`) with 8 parallel eBay lookups;
  the UI shows "Priced N of M parts". Measured on Render free tier: cold vehicle ~2 min,
  warm ~20s (locally 23s cold, 1-3s warm).

## Unverified (come back to these)
1. **True mobile check at 390px.** Headless Chrome enforces a ~500px minimum window, so the
   layout was only confirmed at 600px. Open the site on a phone or in devtools device mode and
   check: no horizontal scroll, strip and ledger stack, chips wrap.
2. **Haircut tuning.** `ASKING_TO_SOLD = 0.75` and `SHIPPING_BY_SIZE` in
   `backend/app/services/pricing.py` are guesses. Spot-check 10 parts against eBay's sold
   filter in the browser and adjust per size class.
3. **Texas title path for an undamaged car.** TxDMV says it won't issue a salvage title for
   an undamaged vehicle; the nonrepairable-title route via VTR-441 needs confirming with
   TxDMV before any dismantling.
4. **Render free tier spin-down.** The instance sleeps after 15 idle minutes and the first
   request then takes ~30-60s to boot. Fine for a demo; a paid instance fixes it.
5. **Thin parts.** Front bumper cover, MMI head unit and a few others have 1-4 comparables
   after cleaning; they fall back to reference prices or show low confidence. Better queries
   or a second category may help.

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
