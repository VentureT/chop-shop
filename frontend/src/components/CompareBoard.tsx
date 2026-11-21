import { useEffect, useState } from 'react';
import { InputNumber } from 'antd';
import { api, money } from '../api';
import type { CompareResponse, ValuateResponse } from '../types';

interface Props {
  result: ValuateResponse;
}

export default function CompareBoard({ result }: Props) {
  const [offer, setOffer] = useState(6000);
  const [privateParty, setPrivateParty] = useState(11000);
  const [hourly, setHourly] = useState(25);
  const [cmp, setCmp] = useState<CompareResponse | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api.compare(result, offer, privateParty, hourly).then(setCmp).catch(() => setCmp(null));
    }, 250);
    return () => clearTimeout(t);
  }, [result, offer, privateParty, hourly]);

  return (
    <section className="cs-sheet">
      <h2>Part it out, or sell it whole?</h2>
      <p className="cs-sub">Put in the offers you actually have. The part-out lane uses the ledger above.</p>

      <div className="cs-inputs">
        <div className="cs-opt">
          <label>Instant offer (Carvana, CarMax, dealer)</label>
          <InputNumber
            value={offer}
            onChange={(v) => setOffer(Number(v ?? 0))}
            prefix="$"
            min={0}
            step={100}
            style={{ width: '100%' }}
          />
        </div>
        <div className="cs-opt">
          <label>Private party (KBB, Edmunds, local listings)</label>
          <InputNumber
            value={privateParty}
            onChange={(v) => setPrivateParty(Number(v ?? 0))}
            prefix="$"
            min={0}
            step={100}
            style={{ width: '100%' }}
          />
        </div>
        <div className="cs-opt">
          <label>What your time is worth per hour</label>
          <InputNumber
            value={hourly}
            onChange={(v) => setHourly(Number(v ?? 0))}
            prefix="$"
            min={0}
            step={5}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      {cmp && (
        <>
          <div className="cs-board">
            <Lane
              k="Instant offer"
              v={cmp.instant_offer}
              note="Cash this week. Wholesale number."
              win={cmp.winner === 'instant_offer'}
            />
            <Lane
              k="Private party"
              v={cmp.private_party}
              note="A few weeks of listings, test drives and haggling. The car stays a car."
              win={cmp.winner === 'private_party'}
            />
            <Lane
              k="Part it out"
              v={cmp.part_out_net_after_labor}
              note={`${money(cmp.part_out_est_net)} after fees, shipping and ${Math.round(cmp.sell_through * 100)}% sell-through, minus ${Math.round(cmp.total_hours)} hours of your time. ${cmp.months_estimate} months.`}
              win={cmp.winner === 'part_out'}
            />
          </div>
          <ul className="cs-notes">
            {cmp.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function Lane({ k, v, note, win }: { k: string; v: number; note: string; win: boolean }) {
  return (
    <div className={`cs-lane${win ? ' win' : ''}`}>
      {win && <span className="cs-win-tag">Best</span>}
      <div className="cs-k">{k}</div>
      <div className="cs-v">{money(v)}</div>
      <div className="cs-note">{note}</div>
    </div>
  );
}
