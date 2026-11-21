import { useMemo, useState, type ReactNode } from 'react';
import { Segmented, Tooltip } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { money } from '../api';
import type { PartValuation, ValuateResponse } from '../types';

interface Props {
  result: ValuateResponse;
}

type View = 'value' | 'system';

const STATUS_LABEL: Record<PartValuation['price_status'], string> = {
  live: 'eBay',
  cached: 'eBay',
  reference: 'reference',
  no_results: 'reference',
  error: 'reference',
  no_credentials: 'reference',
};

const HELP = {
  net: (
    <>
      What you would likely pocket after everything sells: each part's asking price, cut to an expected sold
      price (75% of asking by default, less for VIN-locked modules), minus about 13% in marketplace fees and
      an estimated shipping cost by part size. Airbags count as $0.
    </>
  ),
  asking: (
    <>
      The sum of current asking prices for every sellable part, times quantity. Sellers rarely get asking,
      and fees and shipping come out of it, so this is the ceiling, not the forecast.
    </>
  ),
  removal: (
    <>
      Rough wrench time to remove every sellable part, from the taxonomy's per-part estimates. The second
      number is the same estimate for just the ten most valuable parts. Neither includes listing, packing or
      shipping.
    </>
  ),
  top10: (
    <>
      Net value of the ten highest-value parts divided by net value of all sellable parts. A high number
      means most of the money is in a few big items and the rest may not be worth the effort.
    </>
  ),
  each: (
    <>
      The median asking price for one unit in current listings, before any haircut. The bold figure on the
      right is the estimated net for all units of that part after the sold-price haircut, fees and shipping.
    </>
  ),
};

function Hint({ label, text }: { label: ReactNode; text: ReactNode }) {
  return (
    <Tooltip title={text} placement="top" overlayStyle={{ maxWidth: 320 }}>
      <span className="cs-hint-label">
        {label}
        <InfoCircleOutlined aria-label="More about this figure" />
      </span>
    </Tooltip>
  );
}

function PartRow({ v, max }: { v: PartValuation; max: number }) {
  const [open, setOpen] = useState(false);
  const isLive = v.price_status === 'live' || v.price_status === 'cached';
  const pct = max > 0 ? Math.max(0, Math.min(100, (v.est_net_total / max) * 100)) : 0;
  const worst = v.flags.find((f) => f.severity === 'block') ?? v.flags.find((f) => f.severity === 'warn');
  const netTitle = v.sellable
    ? `Estimated net for ${v.part.qty > 1 ? `all ${v.part.qty}` : 'this part'}: ${money(v.est_sold_each)} expected sold each, minus fees and shipping, is ${money(v.est_net_each)} each.`
    : 'Not sellable on mainstream marketplaces, so it counts as $0.';

  return (
    <>
      <button type="button" className="cs-row" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <div className="cs-row-name">
          {v.part.name}
          {v.part.qty > 1 && <span className="qty">x{v.part.qty}</span>}
        </div>
        <Tooltip title={netTitle} placement="left" overlayStyle={{ maxWidth: 300 }}>
          <div className={`cs-row-net${v.est_net_total <= 0 ? ' zero' : ''}`}>
            {v.sellable ? money(v.est_net_total) : money(0)}
          </div>
        </Tooltip>
        <div className="cs-vbar" aria-hidden="true">
          <i className={isLive ? '' : 'ref'} style={{ width: `${pct}%` }} />
        </div>
        <div className="cs-row-meta">
          <Tooltip title={v.confidence_reason || v.note} placement="top" overlayStyle={{ maxWidth: 320 }}>
            <span className={`cs-chip${isLive ? ' live' : ''}`}>
              {isLive ? `${v.sample_size} eBay listings` : STATUS_LABEL[v.price_status]}
            </span>
          </Tooltip>
          {v.sellable && (
            <Tooltip title={HELP.each} placement="top" overlayStyle={{ maxWidth: 320 }}>
              <span className="cs-hint-label">
                asking {money(v.asking_median)} each
                <InfoCircleOutlined aria-label="How asking relates to the net figure" />
              </span>
            </Tooltip>
          )}
          {worst && <span className={`cs-chip ${worst.severity}`}>{worst.title}</span>}
        </div>
      </button>
      {open && (
        <div className="cs-detail">
          <dl>
            <dt>Search</dt>
            <dd>{v.query}</dd>
            {v.sellable && (
              <>
                <dt>Asking range</dt>
                <dd>
                  {money(v.asking_low)} to {money(v.asking_high)}, median {money(v.asking_median)}
                </dd>
                <dt>Estimated sold</dt>
                <dd>{money(v.est_sold_each)} each</dd>
                <dt>After fees and shipping</dt>
                <dd>
                  {money(v.est_net_each)} each, {money(v.est_net_total)} total
                </dd>
              </>
            )}
            <dt>Removal</dt>
            <dd>
              about {v.part.removal_hours * v.part.qty} h, size {v.part.size_class}
            </dd>
            <dt>Confidence</dt>
            <dd>
              {v.confidence}
              {v.confidence_reason && <span className="cs-why"> {v.confidence_reason}</span>}
            </dd>
          </dl>
          {v.note && <div>{v.note}</div>}
          {v.flags.map((f) => (
            <div key={f.code} className={`cs-flag ${f.severity}`}>
              <b>{f.title}</b>
              {f.detail}
              {f.source && <small>{f.source}</small>}
            </div>
          ))}
          {v.sample_listings.length > 0 && (
            <ul>
              {v.sample_listings.map((l) => (
                <li key={l.item_id}>
                  <a href={l.url} target="_blank" rel="noreferrer">
                    {money(l.price)} {l.compatibility_match ? `(${l.compatibility_match.toLowerCase()} fit)` : ''} {l.title}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}

export default function Ledger({ result }: Props) {
  const [view, setView] = useState<View>('value');
  const { parts, totals } = result;
  const max = useMemo(() => Math.max(...parts.map((p) => p.est_net_total), 1), [parts]);

  const groups = useMemo(() => {
    if (view === 'value') {
      const top = parts.filter((p) => p.sellable && p.est_net_total >= 50);
      const rest = parts.filter((p) => !top.includes(p));
      return [
        { name: 'Worth listing individually', parts: top },
        { name: 'Bundle, scrap, or leave on the shell', parts: rest },
      ];
    }
    const by = new Map<string, PartValuation[]>();
    for (const p of parts) {
      by.set(p.part.group, [...(by.get(p.part.group) ?? []), p]);
    }
    return [...by.entries()]
      .map(([name, ps]) => ({ name, parts: ps }))
      .sort((a, b) => sum(b.parts) - sum(a.parts));
  }, [parts, view]);

  return (
    <>
      <div className="cs-strip" role="region" aria-label="Totals">
        <div>
          <div className="cs-k">
            <Hint label="Estimated net, all parts" text={HELP.net} />
          </div>
          <div className="cs-v orange">{money(totals.est_net)}</div>
        </div>
        <div>
          <div className="cs-k">
            <Hint label="Asking total" text={HELP.asking} />
          </div>
          <div className="cs-v">{money(totals.gross_asking)}</div>
        </div>
        <div>
          <div className="cs-k">
            <Hint label="Removal time" text={HELP.removal} />
          </div>
          <div className="cs-v">
            {Math.round(totals.removal_hours)}
            <small>hours</small>
          </div>
          <div className="cs-k cs-k-sub">top 10 parts: {Math.round(totals.top_10_removal_hours)} hours</div>
        </div>
        <div>
          <div className="cs-k">
            <Hint label="Top 10 parts carry" text={HELP.top10} />
          </div>
          <div className="cs-v">
            {Math.round(totals.top_10_share * 100)}
            <small>% of value</small>
          </div>
        </div>
      </div>

      <section className="cs-sheet">
        <div className="cs-ledger-head">
          <div>
            <h2>Parts ledger</h2>
            <p className="cs-sub" style={{ margin: 0 }}>
              {totals.parts_sellable} sellable of {totals.parts_considered} part types.{' '}
              {result.ebay_live
                ? `${totals.live_priced} priced from live eBay listings.`
                : 'Reference prices; connect eBay for live data.'}
            </p>
          </div>
          <Segmented
            value={view}
            onChange={(v) => setView(v as View)}
            options={[
              { label: 'By value', value: 'value' },
              { label: 'By system', value: 'system' },
            ]}
          />
        </div>

        {groups.map((g) => (
          <div className="cs-group" key={g.name}>
            <div className="cs-group-title">
              {g.name}
              <span>{money(sum(g.parts))}</span>
            </div>
            {g.parts.map((p) => (
              <PartRow key={p.part.id} v={p} max={max} />
            ))}
          </div>
        ))}
      </section>
    </>
  );
}

function sum(ps: PartValuation[]) {
  return ps.reduce((a, p) => a + (p.sellable ? p.est_net_total : 0), 0);
}
