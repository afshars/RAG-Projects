import React, { useState } from 'react';
import { ChevronDown, FileText, ExternalLink, Quote } from 'lucide-react';

export default function CitationsExpander({ sources }) {
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border border-border overflow-hidden bg-muted/30 w-full max-w-[80%]">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-sm font-medium text-foreground hover:bg-muted/60 transition-colors"
      >
        <span className="flex items-center gap-2">
          <Quote className="w-4 h-4 text-primary" />
          چانک‌ها و منابع ({sources.length})
        </span>
        <ChevronDown
          className={`w-4 h-4 text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <div className="border-t border-border divide-y divide-border animate-fade-in">
          {sources.map((src, idx) => (
            <div key={idx} className="p-4 hover:bg-white/50 transition-colors">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                  {idx + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <FileText className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                    <h4 className="text-sm font-semibold text-foreground">{src.title}</h4>
                    {(src.author || src.documentDate) && (
                      <span className="text-[10px] text-muted-foreground">
                        {[src.author, src.documentDate].filter(Boolean).join(' · ')}
                      </span>
                    )}
                    {src.score != null && (
                      <span className="text-[10px] font-mono bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                        امتیاز: {typeof src.score === 'number' ? src.score.toFixed(3) : src.score}
                      </span>
                    )}
                    {src.url && (
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-shrink-0 text-primary hover:text-primary/70"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed line-clamp-4">
                    {src.content}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}