import { useCallback, useEffect, useState } from 'react';
import { ConfigProvider } from 'antd';
import { ThemeSettings, useTheme } from '@venturet/theme';
import { DocsViewer } from '@venturet/docs-viewer';
import { api } from './api';
import { FONT_BODY } from './theme';
import type { Options, Status, ValuateResponse, VehicleProfile } from './types';
import { DEFAULT_OPTIONS } from './types';
import VinEntry from './components/VinEntry';
import VehicleSheet from './components/VehicleSheet';
import Ledger from './components/Ledger';
import CompareBoard from './components/CompareBoard';
import VehicleFlags from './components/VehicleFlags';

const docFiles = import.meta.glob('../../docs/**/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

type Stage = 'vin' | 'decoding' | 'confirm' | 'valuing' | 'results';

function defaultsFor(v: VehicleProfile): Options {
  return {
    ...DEFAULT_OPTIONS,
    convertible_top: v.body === 'Convertible',
    sunroof: v.body !== 'Convertible',
  };
}

export default function App() {
  const { tokens } = useTheme();
  const [status, setStatus] = useState<Status | null>(null);
  const [stage, setStage] = useState<Stage>('vin');
  const [vin, setVin] = useState('');
  const [vehicle, setVehicle] = useState<VehicleProfile | null>(null);
  const [options, setOptions] = useState<Options>(DEFAULT_OPTIONS);
  const [zip, setZip] = useState('');
  const [result, setResult] = useState<ValuateResponse | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.csMode = tokens.mode;
  }, [tokens.mode]);

  useEffect(() => {
    api.status().then(setStatus).catch(() => setStatus(null));
  }, []);

  // Shareable link: /?vin=...  (add &auto=1 to price immediately with default options)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const v = params.get('vin');
    if (!v) return;
    (async () => {
      setError(null);
      setStage('decoding');
      try {
        const veh = await api.decode(v);
        setVin(v);
        setVehicle(veh);
        const opts = defaultsFor(veh);
        setOptions(opts);
        if (params.get('auto')) {
          setStage('valuing');
          setProgress(null);
          setResult(await api.valuateJob(v, opts, '', (done, total) => setProgress({ done, total })));
          setStage('results');
        } else {
          setStage('confirm');
        }
      } catch (e) {
        setError((e as Error).message);
        setStage('vin');
      }
    })();
  }, []);

  const decode = useCallback(async (value: string) => {
    setError(null);
    setStage('decoding');
    try {
      const v = await api.decode(value);
      setVin(value);
      setVehicle(v);
      setOptions(defaultsFor(v));
      setStage('confirm');
    } catch (e) {
      setError((e as Error).message);
      setStage('vin');
    }
  }, []);

  const valuate = useCallback(async () => {
    if (!vehicle) return;
    setError(null);
    setStage('valuing');
    setProgress(null);
    try {
      const r = await api.valuateJob(vin, options, zip, (done, total) => setProgress({ done, total }));
      setResult(r);
      setStage('results');
    } catch (e) {
      setError((e as Error).message);
      setStage('confirm');
    }
  }, [vehicle, vin, options, zip]);

  const reset = () => {
    setStage('vin');
    setVehicle(null);
    setResult(null);
    setError(null);
  };

  return (
    <ConfigProvider theme={{ token: { fontFamily: FONT_BODY } }}>
      <div className="cs-app">
        <header className="cs-bar">
          <div className="cs-brand">
            Chop Shop
            <small>what your car is worth in pieces</small>
          </div>
          <div className="cs-bar-right">
            {status && (
              <span>{status.ebay_configured ? "eBay pricing live" : "reference prices"}</span>
            )}
            {stage !== 'vin' && (
              <button type="button" onClick={reset}>
                Start over
              </button>
            )}
          </div>
        </header>

        {(stage === 'vin' || stage === 'decoding') && (
          <VinEntry
            busy={stage === 'decoding'}
            error={error}
            onSubmit={decode}
            initial={vin}
          />
        )}

        {vehicle && stage !== 'vin' && stage !== 'decoding' && (
          <VehicleSheet
            vehicle={vehicle}
            options={options}
            zip={zip}
            onZip={setZip}
            onChange={setOptions}
            onValuate={valuate}
            busy={stage === 'valuing'}
            locked={stage === 'results'}
            error={stage === 'confirm' ? error : null}
          />
        )}

        {stage === 'valuing' && (
          <div className="cs-sheet">
            <h2>Pricing every sellable part</h2>
            <p className="cs-sub">
              {status?.ebay_configured
                ? 'Searching eBay for used listings that fit this vehicle. A first run takes up to a minute; results are cached for a week.'
                : 'Using built-in reference prices. Add eBay credentials to the backend for live market data.'}
            </p>
            <p className="cs-sub" aria-live="polite">
              {progress && progress.total > 0
                ? `Priced ${progress.done} of ${progress.total} parts`
                : 'Finding the parts that fit this car'}
            </p>
            <div className="cs-vbar" role="progressbar" aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={progress && progress.total > 0 ? Math.round((100 * progress.done) / progress.total) : 0}>
              <i style={{ width: progress && progress.total > 0 ? `${(100 * progress.done) / progress.total}%` : '0%' }} />
            </div>
            <div className="cs-loading">
              {[92, 80, 86, 64, 72, 58].map((w) => (
                <div key={w} className="cs-skel" style={{ width: `${w}%` }} />
              ))}
            </div>
          </div>
        )}

        {result && stage === 'results' && (
          <>
            <Ledger result={result} />
            <CompareBoard result={result} />
            <div className="cs-sheet">
              <h2>Before you pick up a wrench</h2>
              <p className="cs-sub">Rules that apply to this car in {status?.state ?? 'your state'}.</p>
              <VehicleFlags flags={result.vehicle_flags} />
            </div>
          </>
        )}

        <footer className="cs-footer">
          Estimates use asking-price medians with a haircut, not sold prices. Vehicle identity comes from the NHTSA
          vPIC decoder; it cannot see factory options, so confirm them above. Nothing here is legal advice.
        </footer>
      </div>
      <ThemeSettings />
      <DocsViewer files={docFiles} title="Chop Shop docs" />
    </ConfigProvider>
  );
}
