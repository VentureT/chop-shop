import type { Flag } from '../types';

export default function VehicleFlags({ flags }: { flags: Flag[] }) {
  return (
    <div className="cs-flaglist">
      {flags.map((f) => (
        <div key={f.code} className={`cs-flagline ${f.severity}`}>
          <i aria-hidden="true" />
          <div>
            <b>{f.title}.</b> <span>{f.detail}</span>
            {f.source && <span style={{ display: 'block', fontSize: 12.5, marginTop: 2 }}>{f.source}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
