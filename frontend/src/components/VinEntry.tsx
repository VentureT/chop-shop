import { useState } from 'react';
import { Button } from 'antd';

interface Props {
  busy: boolean;
  error: string | null;
  initial?: string;
  onSubmit: (vin: string) => void;
}

const clean = (s: string) => s.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, '').slice(0, 17);

export default function VinEntry({ busy, error, initial = '', onSubmit }: Props) {
  const [value, setValue] = useState(initial);
  const ready = value.length === 17;

  return (
    <section className="cs-hero">
      <h1>Your car, priced by the piece.</h1>
      <p>
        Enter a VIN. We identify the car, list the parts that actually resell, estimate what each one nets after
        fees and shipping, and compare that to just selling the car.
      </p>

      <form
        className="cs-vin"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready && !busy) onSubmit(value);
        }}
      >
        <label htmlFor="vin">Vehicle identification number</label>
        <div className="cs-vin-field">
          <input
            id="vin"
            value={value}
            onChange={(e) => setValue(clean(e.target.value))}
            placeholder="WAUCFAFR5FA000000"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            inputMode="text"
            aria-describedby="vin-hint"
            disabled={busy}
          />
          <div className="cs-vin-meter" aria-hidden="true">
            {Array.from({ length: 17 }, (_, i) => (
              <span key={i} className={i < value.length ? 'on' : ''} />
            ))}
          </div>
        </div>
        <div className="cs-vin-actions">
          <Button type="primary" size="large" htmlType="submit" disabled={!ready} loading={busy}>
            Identify this car
          </Button>
          <span className="cs-hint" id="vin-hint">
            {ready ? 'Ready.' : `${17 - value.length} characters to go. It's on the driver's door jamb and the dash.`}
          </span>
        </div>
        {error && (
          <div className="cs-vin-error" role="alert">
            {error}
          </div>
        )}
      </form>
    </section>
  );
}
