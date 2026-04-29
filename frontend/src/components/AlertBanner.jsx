import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function AlertBanner({ alert, anomaly }) {
  const hasAnomaly = Boolean(
    anomaly
    && anomaly !== 'No active anomaly alerts.'
    && anomaly !== 'No stream data yet'
    && anomaly !== 'No anomaly data yet',
  );
  const shouldShow = Boolean(alert || hasAnomaly);

  if (!shouldShow) {
    return null;
  }

  return (
    <section className="mb-5 flex items-start gap-3 rounded-lg border border-red-400/40 bg-red-950/80 p-4 text-red-100 shadow-2xl shadow-red-950/30">
      <AlertTriangle className="mt-0.5 shrink-0" size={20} />
      <div>
        <p className="font-semibold">{alert || 'HIGH PRIORITY ISSUE DETECTED'}</p>
        <p className="mt-1 text-sm text-red-200">{anomaly || 'An anomaly is active in the operations stream.'}</p>
      </div>
    </section>
  );
}
