# Chop Shop: narrow MVP implementation plan

## Context

Tate owns a 2015 Audi A5 (<50k miles) that Carvana quoted at ~$6k and wants software that takes a VIN and shows which parts in the car have real used-resale value. The feasibility assessment (below, kept for reference) found that a complete OEM parts list by VIN (Audi ETKA) and used *sold* prices (eBay Marketplace Insights, Car-Part.com, Hollander) are all proprietary or partner-only. Tate chose the **narrow MVP**: free VIN decode, a curated ~100-item sellable-parts taxonomy, eBay Browse API asking prices with a haircut, ranked output with legal flags, and a part-out vs. private-sale vs. instant-offer comparison. Car is titled in **Texas**.

The `chop-shop` directory is empty. No code exists yet.

## Scope

**In:** VIN -> vehicle; options checklist; ranked list of sellable part types with estimated used asking price, estimated net, and legal/practical flags; three-way comparison; result caching.
**Out (explicitly):** full ETKA enumeration, Hollander/Car-Part licensing, scraping any site, eBay Marketplace Insights (apply in parallel, don't block), listing/selling flows, user accounts.

## Stack and layout (house Pattern A, per sibling projects)

Follow the `/pitch-brief` demo-app conventions found in `tate-bits`, `drafture`, `groom.ly`:
- `backend/` FastAPI + uvicorn + pydantic v2 + pydantic-settings, `requirements.txt`, `.venv`, `.env.example` committed. Port 8000.
- `frontend/` Vite + React 18 + TypeScript + antd v5 + `@ant-design/icons`. Port 5173, `vite.config.ts` proxies `/api` -> `http://localhost:8000`.
- Shared packages: `"@venturet/theme": "git+https://github.com/VentureT/theme.git#semver:^1.0.0"` for consistent look (wrap in `ThemeProvider` as in `tate-bits/frontend/src/main.tsx`); `"@venturet/docs-viewer": "git+https://github.com/VentureT/docs-viewer.git#semver:^1.0.0"` to render `docs/`. **Skip demo-shell** (its mock Dashboard/Team pages add nothing here).
- Mobile-first layout (per standing preference); desktop is enhancement.
- Root: `README.md` (run instructions), `PROJECT_PLAN.md`, `.gitignore`, `docs/feasibility.md` (copy of the assessment below). No `git init` unless asked.
- Tests: `pytest` in `backend/tests/` for taxonomy filtering, pricing math, and legal flags (pure functions). Frontend tests optional.

## Architecture

```
VIN ──> /api/decode (NHTSA vPIC) ──> VehicleProfile
            + user options checklist (PR-code proxies)
        ──> taxonomy filter ──> applicable PartType[]
        ──> /api/valuate ──> for each PartType: eBay Browse search (cached)
                           ──> PartValuation{asking_median, est_sold, est_net, n, flags}
        ──> /api/compare ──> part-out gross/net/hours vs private-party vs instant-offer
```

### Backend files (`backend/app/`)
- `main.py` – FastAPI app, CORS, routers, `/health`.
- `config.py` – pydantic-settings: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_ENV` (sandbox|production), `CACHE_TTL_DAYS=7`, `CORS_ORIGINS`.
- `routers/decode.py` – `GET /api/decode/{vin}`.
- `routers/valuate.py` – `POST /api/valuate` body `{vin, options: {...}}`; `POST /api/compare`.
- `services/vpic.py` – calls `https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{VIN}?format=json`. Verified live: returns `Make, Model, ModelYear, Trim, BodyClass, Doors, DriveType, EngineCylinders, DisplacementL, FuelTypePrimary, TransmissionStyle, PlantCountry, ErrorCode/ErrorText`. Surface `ErrorCode != 0` as a warning, not a failure (check-digit errors still decode).
- `services/ebay_auth.py` – client-credentials grant: `POST https://api.ebay.com/identity/v1/oauth2/token` (sandbox: `api.sandbox.ebay.com`), `Content-Type: application/x-www-form-urlencoded`, `Authorization: Basic base64(client_id:client_secret)`, body `grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope`. Token `expires_in` 7200s; cache in memory and refresh at 6600s. Verified from eBay auth guide via edp.ebay.com mirror.
- `services/ebay_browse.py` – `GET https://api.ebay.com/buy/browse/v1/item_summary/search` with:
  - `q=<part keyword>` (required when compatibility_filter is used; max 100 chars, no `*`),
  - `category_ids=<one parts-compatibility-supported leaf id>` (only one id per request; spec example `33559` Brakes),
  - `compatibility_filter=Year:2015;Make:Audi;Model:A5` (semicolon-separated `Name:Value` pairs, verified from spec example `Year:2018;Make:BMW`; add `Trim`/`Engine` when the taxonomy entry needs it),
  - `filter=conditions:{USED},price:[<lo>..<hi>],priceCurrency:USD,deliveryCountry:US` (price requires priceCurrency; `conditions:{USED}` syntax taken from the Buy API field-filters page, **verify on first call**),
  - `sort=price`, `limit=50`, `fieldgroups=MATCHING_ITEMS`,
  - headers `X-EBAY-C-MARKETPLACE-ID: EBAY_US`, `X-EBAY-C-ENDUSERCTX: contextualLocation=country%3DUS%2Czip%3D<user zip>`.
  - Read from each `itemSummary`: `price.value`, `condition`, `conditionId`, `buyingOptions`, `compatibilityMatch` (EXACT|POSSIBLE), `itemWebUrl`, `shippingOptions`, `itemLocation`.
  - Note: sandbox returns mock data only for compatibility searches; test real queries in production with a small quota.
- `services/pricing.py` – pure functions: keep `FIXED_PRICE`/`BEST_OFFER` listings, prefer `compatibilityMatch == EXACT`, drop top/bottom 10%, `asking_median`; `est_sold = asking_median * 0.75` (asking->sold haircut, tunable per part class); `est_net = est_sold * (1 - 0.13) - shipping_estimate[size_class]`; confidence from `n` and EXACT share.
- `services/taxonomy.py` – loads `data/part_types.json`, filters by `VehicleProfile` + options.
- `services/legal.py` – pure rules -> `Flag[]` (see Legal flags).
- `services/cache.py` – SQLite (`backend/cache.db`, gitignored) keyed `(year, make, model, part_type_id)` with TTL; one vehicle = ~100 Browse calls, so caching is what keeps the daily quota (default not published; raise via eBay "Application Growth Check") workable.
- `data/part_types.json` – the curated taxonomy (below).
- `data/categories.json` – eBay leaf category ids for each taxonomy entry (populate once via Taxonomy API `getCompatibilityPropertyValues`/category tree, or manual lookup; mark unverified ids).

### Taxonomy (`data/part_types.json`)
Seed from the Hollander Part Type Descriptions Guide (extracted; 188 codes). Keep the ~90-110 that apply to a modern passenger car and have resale demand. Each entry:
```json
{"id":"headlamp_assembly","hollander":"114","name":"Headlamp Assembly","qty":2,"side":true,
 "ebay_q":"headlight assembly","ebay_category_id":"<leaf id>","size_class":"M",
 "applies_if":{"body":["Coupe","Sedan","Convertible","SUV"]},
 "variants_by_option":{"headlights":{"xenon":"xenon hid headlight","led":"led headlight","halogen":"halogen headlight"}},
 "removal_hours":1.0,"flags":[]}
```
Core groups to include (Hollander codes): front end 101/104/105/110/114/116/117; doors/mirrors 120/125/128/129/130; rear 150/152/153/166/169/170/187/190; interior 202/215/238/241/257/260; glass 270/275/277; engine 300/306/317/321/322/323/329/336/337; trans/driveline 400/407/409/412/430/431/435/444; suspension/brakes 511/512/515/527/530/533/536/551/553; wheels 560; electronics 590/591/593/594/596/638/654/655; electrical 600/601/604/610/615/617/620/646/663; cooling/HVAC 674/675/679/682; plus exhaust/catalytic converter (not a Hollander body code; add as `catalytic_converter`). **Exclude or zero-value:** 253 Air bag, 210/212 seat belts w/ pretensioners (same safety-part problem), 197 fuel tank.

### Options checklist (VIN can't see these)
Headlights (halogen/xenon/LED), wheel size (17/18/19) and style, audio (standard/B&O), navigation/MMI level, seats (standard/sport), sunroof, S-line package, convertible top (Cabriolet only). Shown after decode with sensible defaults for the decoded trim.

### Legal and practical flags (`services/legal.py`, Texas-specific where noted)
- `AIRBAG_UNSELLABLE`: eBay bans all airbag/inflator sales effective 2026-09-24; Amazon, Meta Marketplace, Alibaba, Temu already prohibit. Value shown as $0.
- `CAT_CONVERTER_RESTRICTED` (TX): SB 224 (eff. 2023-07-01) requires seller ID to metal recycling entities, which must mark/record each unit; eBay has its own converter policy. Show value but flag "sell only to licensed buyer with documentation."
- `COMPONENT_PROTECTION` (Audi 2011+): MMI head unit, display, instrument cluster, ECU, gateway are VIN-locked; buyer needs dealer coding. Apply extra 0.6 haircut and flag.
- `TITLE_REQUIRED` (TX): Transp. Code §501.09111 lets a salvage/nonrepairable title holder dismantle and sell parts; application is VTR-441 ($8). TxDMV states it will not issue a salvage title for an undamaged vehicle, so flag "confirm nonrepairable-title path with TxDMV before dismantling." Component Parts Bill of Sale is VTR-63.
- `LICENSE_IF_COMMERCIAL` (TX): operating a used-parts business requires a TDLR Used Automotive Parts Recycler license (Occ. Code ch. 2309); one-off sale of your own car's parts is generally outside that, but flag it.
- `HAZMAT`: A/C refrigerant recovery (EPA 609), fluids disposal.
- `SHELL_DISPOSAL`: shell scrap value ~$300-500, needs title handoff to recycler.

### Comparison (`POST /api/compare`)
Inputs: `instant_offer` (user-entered, e.g. 6000), `private_party` (user-entered from KBB/Edmunds; MVP does not scrape valuation sites), valuation result. Output: part-out `gross_asking`, `est_sold`, `est_net`, `total_hours`, `months_estimate` (default 6-12), `sell_through_assumption` (default 70% of parts sell), plus flags summary. Render as a 3-column mobile card stack.

## Frontend (`frontend/src/`)
- `main.tsx` – `ThemeProvider` + `App`.
- `App.tsx` – single-page flow with antd `Steps`: VIN -> Confirm vehicle + options -> Results -> Compare. `DocsViewer` route for `docs/`.
- `api.ts` – typed fetch wrappers for `/api/decode`, `/api/valuate`, `/api/compare`.
- `components/VinForm.tsx`, `VehicleCard.tsx`, `OptionsChecklist.tsx`, `PartsTable.tsx` (antd `Table` on desktop, `List` cards on mobile; sortable by est_net; flag chips; link out to `itemWebUrl` samples), `CompareCards.tsx`.
- `theme.ts` – base tokens for `@venturet/theme`.

## Prerequisites Tate must do
1. Create an eBay Developers Program account and a **production** keyset (client id/secret). Sandbox can't test compatibility search meaningfully.
2. Optionally submit the Application Growth Check requesting Marketplace Insights (sold data) and a higher Browse quota. Not blocking.

## Build order
1. Scaffold `backend/` + `frontend/` per Pattern A; README; `.env.example`; `docs/feasibility.md`.
2. `vpic.py` + `/api/decode` + tests. Decode Tate's real VIN.
3. `part_types.json` (~100 entries) + `taxonomy.py` + tests for applicability filtering.
4. `ebay_auth.py`, `ebay_browse.py`, `cache.py`, `pricing.py`; one CLI script `backend/scripts/price_one.py <year> <make> <model> <part_id>` to validate filter syntax and category ids against production before wiring the full loop.
5. `legal.py` + tests; `/api/valuate`, `/api/compare`.
6. Frontend flow; mobile layout first.
7. Run Tate's A5 end to end; spot-check 10 part prices manually against eBay's sold filter in the browser; tune the 0.75 haircut per size class.

## Verification
- `cd backend && uvicorn app.main:app --reload --port 8000` and `cd frontend && npm run dev` (two terminals, per house convention).
- `pytest backend/tests` green: taxonomy filter (Coupe excludes rear doors/pickup box; Cabriolet includes convertible top), pricing math (trim, haircut, fees), legal flags (airbag -> $0, cat -> restricted, MMI -> component protection).
- `curl localhost:8000/api/decode/<VIN>` returns 2015 AUDI A5 Coupe AWD 2.0L.
- `price_one.py 2015 Audi A5 headlamp_assembly` returns n>=5 USED listings with `compatibilityMatch` populated; confirm `conditions:{USED}` filter is accepted (if 400, consult the Buy API field-filters page and adjust).
- Full valuation for the A5 completes under ~100 Browse calls on a cold cache and ~0 on a warm cache.
- Mobile check at 390px width: no horizontal scroll, cards stack, flags readable.

---

# Appendix: feasibility assessment (2026-11-21)

## Verdict
Partially feasible. VIN -> identity is free (vPIC). Vehicle -> complete OEM parts list is proprietary (ETKA; 7zap/PartSouq mirrors have no official API; Laximo is quote-only B2B). Part-type/interchange data (Hollander, Car-Part Interchange) is licensed to recyclers only. Used *sold* prices via eBay Marketplace Insights are partner-only; eBay Browse (asking prices) is open. Car-Part.com has no API.

## Prior art
Bidmate (Car-Part.com, B2B, prices by interchange vs. yard history), AutoValueAI, AuctionCalc ($29-299/mo flipper bid calc, VIN in, eBay+Car-Part via Chrome extension, outputs max bid), Parts2Profit (photo/text in, eBay 90-day sold, no VIN field, sign-up gated), Car-Part Core Pricing app. No verified consumer VIN -> ranked sellable parts tool.

## Legal/practical
Title to salvage/nonrepairable before dismantling (TX §501.09111, VTR-441; TxDMV won't issue salvage for undamaged car). TX TDLR UAPR license for commercial parts sales. eBay airbag ban 2026-09-24 (Amazon/Meta/Alibaba/Temu already). TX SB 224 catalytic converter seller ID. Audi component protection depresses MMI/ECU values. Forum consensus: 6-12 months, 100+ hours.

## Sanity check
KBB 2015 A5 coupe private party ~$10,050-$12,250; trade-in ~$5,675. Carvana's $6k is wholesale.

## Rough A5 2.0T part-out (asking, ±40%)
Engine $2,000-3,500 (new long block lists $2,199) | Trans $800-1,800 | Xenon headlights pair $600-1,400 | 18" wheels $500-1,000 | Mirrors/doors/bumpers/hood $200-600 ea | MMI $100-400 | Airbags ~$0 | Shell $300-500. Gross asking $10-18k; realistic net $6-10k after fees, shipping, returns, unsold.
