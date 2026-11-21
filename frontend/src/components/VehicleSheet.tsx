import { Button, Input, Segmented, Switch } from 'antd';
import type { Options, VehicleProfile } from '../types';

interface Props {
  vehicle: VehicleProfile;
  options: Options;
  zip: string;
  onZip: (z: string) => void;
  onChange: (o: Options) => void;
  onValuate: () => void;
  busy: boolean;
  locked: boolean;
  error: string | null;
}

const title = (s: string) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

export default function VehicleSheet({ vehicle, options, zip, onZip, onChange, onValuate, busy, locked, error }: Props) {
  const set = <K extends keyof Options>(k: K, v: Options[K]) => onChange({ ...options, [k]: v });
  const spec = [
    vehicle.body !== 'Unknown' ? vehicle.body : null,
    vehicle.drive || null,
    vehicle.displacement_l ? `${vehicle.displacement_l.toFixed(1)}L${vehicle.turbo ? ' turbo' : ''}` : null,
    vehicle.engine_cyl ? `${vehicle.engine_cyl}-cyl` : null,
    vehicle.transmission || null,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <section className="cs-sheet">
      <div className="cs-plate">
        <div className="cs-plate-title">
          {vehicle.year} {title(vehicle.make)} {vehicle.model}
          {vehicle.trim ? ` ${vehicle.trim}` : ''}
        </div>
        <div className="cs-plate-spec">{spec}</div>
        {vehicle.decode_warnings.length > 0 && (
          <div className="cs-plate-warn">Decoder note: {vehicle.decode_warnings.join('; ')}</div>
        )}
      </div>

      {!locked && (
        <>
          <p className="cs-sub" style={{ marginTop: 16 }}>
            The VIN can't see factory options. Set the ones that change part values.
          </p>
          <div className="cs-opts">
            <div className="cs-opt">
              <label>Headlights</label>
              <Segmented
                block
                value={options.headlights}
                onChange={(v) => set('headlights', v as Options['headlights'])}
                options={[
                  { label: 'Halogen', value: 'halogen' },
                  { label: 'Xenon', value: 'xenon' },
                  { label: 'LED', value: 'led' },
                ]}
              />
            </div>
            <div className="cs-opt">
              <label>Wheel size</label>
              <Segmented
                block
                value={options.wheel_size}
                onChange={(v) => set('wheel_size', v as Options['wheel_size'])}
                options={[17, 18, 19, 20].map((n) => ({ label: `${n}"`, value: n }))}
              />
            </div>
            <div className="cs-opt">
              <label>Audio</label>
              <Segmented
                block
                value={options.audio}
                onChange={(v) => set('audio', v as Options['audio'])}
                options={[
                  { label: 'Standard', value: 'standard' },
                  { label: 'Premium (B&O etc.)', value: 'premium' },
                ]}
              />
            </div>
            <div className="cs-opt">
              <label>Seats</label>
              <Segmented
                block
                value={options.seats}
                onChange={(v) => set('seats', v as Options['seats'])}
                options={[
                  { label: 'Standard', value: 'standard' },
                  { label: 'Sport', value: 'sport' },
                ]}
              />
            </div>
            <div className="cs-opt">
              <div className="cs-opt-row">
                <span>Navigation / MMI</span>
                <Switch checked={options.navigation} onChange={(v) => set('navigation', v)} />
              </div>
              <div className="cs-opt-row">
                <span>Sunroof</span>
                <Switch
                  checked={options.sunroof}
                  disabled={vehicle.body === 'Convertible'}
                  onChange={(v) => set('sunroof', v)}
                />
              </div>
              <div className="cs-opt-row">
                <span>Sport package (S line etc.)</span>
                <Switch checked={options.sport_package} onChange={(v) => set('sport_package', v)} />
              </div>
            </div>
            <div className="cs-opt">
              <label>Your ZIP (for shipping context)</label>
              <Input
                value={zip}
                onChange={(e) => onZip(e.target.value.replace(/\D/g, '').slice(0, 5))}
                placeholder="75201"
                inputMode="numeric"
                maxLength={5}
              />
            </div>
          </div>

          <div className="cs-vin-actions">
            <Button type="primary" size="large" onClick={onValuate} loading={busy}>
              Price the parts
            </Button>
            <span className="cs-hint">Around 100 part types. Airbags are included but valued at zero.</span>
          </div>
          {error && (
            <div className="cs-vin-error" role="alert">
              {error}
            </div>
          )}
        </>
      )}
    </section>
  );
}
