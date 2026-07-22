import React, { useState } from 'react';
import { Copy, Check, ThumbsUp, ThumbsDown, ClipboardList, Star } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';

const DIMENSIONS = [
  { key: 'usefulness', label: 'مفید بودن' },
  { key: 'correctness', label: 'صحت' },
  { key: 'completeness', label: 'کامل بودن' },
];

function StarPicker({ value, onChange }) {
  return (
    <div className="flex items-center gap-0.5" dir="ltr">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          className="p-0.5"
          aria-label={`${n} از ۵`}
        >
          <Star
            className={`w-4 h-4 transition-colors ${
              value && n <= value ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/40'
            }`}
          />
        </button>
      ))}
    </div>
  );
}

export default function FeedbackButtons({ text, onFeedback, currentFeedback, detailedFeedback, onDetailedFeedback }) {
  const [copied, setCopied] = useState(false);
  const [draft, setDraft] = useState(detailedFeedback || {});
  const [open, setOpen] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const btnBase =
    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200';

  const hasDetailed = DIMENSIONS.some((d) => detailedFeedback?.[d.key]);

  const handleSubmitDetailed = () => {
    onDetailedFeedback?.(draft);
    setOpen(false);
  };

  return (
    <div className="flex items-center gap-1.5 mt-2">
      <button
        onClick={handleCopy}
        className={`${btnBase} ${
          copied
            ? 'bg-green-50 text-green-600'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        }`}
      >
        {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
        {copied ? 'کپی شد' : 'کپی متن'}
      </button>

      <div className="w-px h-4 bg-border mx-0.5" />

      <button
        onClick={() => onFeedback('up')}
        className={`${btnBase} ${
          currentFeedback === 'up'
            ? 'bg-green-50 text-green-600'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        }`}
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => onFeedback('down')}
        className={`${btnBase} ${
          currentFeedback === 'down'
            ? 'bg-red-50 text-red-600'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        }`}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>

      {onDetailedFeedback && (
        <Popover open={open} onOpenChange={(o) => {
          setOpen(o);
          if (o) setDraft(detailedFeedback || {});
        }}>
          <PopoverTrigger asChild>
            <button
              className={`${btnBase} ${
                hasDetailed
                  ? 'bg-accent text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              <ClipboardList className="w-3.5 h-3.5" />
              ارزیابی دقیق
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64">
            <p className="text-xs font-medium text-foreground mb-3">
              این پاسخ را از سه جنبه ارزیابی کنید
            </p>
            <div className="space-y-3">
              {DIMENSIONS.map((d) => (
                <div key={d.key} className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{d.label}</span>
                  <StarPicker
                    value={draft[d.key]}
                    onChange={(v) => setDraft((prev) => ({ ...prev, [d.key]: v }))}
                  />
                </div>
              ))}
            </div>
            <Button size="sm" className="w-full mt-4" onClick={handleSubmitDetailed}>
              ثبت ارزیابی
            </Button>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}