import React from 'react';
import { Gauge } from 'lucide-react';

const STYLES = {
  'بالا': 'bg-green-50 text-green-700 border-green-200',
  'متوسط': 'bg-amber-50 text-amber-700 border-amber-200',
  'پایین': 'bg-orange-50 text-orange-700 border-orange-200',
  'بدون منبع': 'bg-muted text-muted-foreground border-border',
};

export default function ConfidenceBadge({ confidence }) {
  if (!confidence || !confidence.label) return null;

  const style = STYLES[confidence.label] || STYLES['بدون منبع'];
  const pct = Math.round((confidence.score || 0) * 100);

  return (
    <span
      title={`میزان همخوانی منابع بازیابی‌شده با این پاسخ: ${pct}٪`}
      className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${style}`}
    >
      <Gauge className="w-3 h-3" />
      اطمینان: {confidence.label} ({pct}٪)
    </span>
  );
}
