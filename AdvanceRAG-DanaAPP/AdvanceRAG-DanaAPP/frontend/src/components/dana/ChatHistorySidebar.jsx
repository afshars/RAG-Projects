import React, { useState } from 'react';
import { Plus, MessageCircle, Trash2, Loader2 } from 'lucide-react';
import { toUtcDate } from '@/lib/utils';

function timeAgo(iso) {
  if (!iso) return '';
  const diffMs = Date.now() - toUtcDate(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'همین الان';
  if (mins < 60) return `${mins} دقیقه پیش`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} ساعت پیش`;
  const days = Math.round(hours / 24);
  return `${days} روز پیش`;
}

export default function ChatHistorySidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  onDelete,
  loading,
}) {
  const [deletingId, setDeletingId] = useState(null);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    setDeletingId(id);
    try {
      await onDelete(id);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <aside className="w-16 md:w-64 bg-sidebar border-r border-sidebar-border flex flex-col flex-shrink-0 h-full">
      <div className="p-2 md:p-3 border-b border-sidebar-border">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 justify-center md:justify-start px-3 py-2.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4 flex-shrink-0" />
          <span className="hidden md:inline">گفتگوی جدید</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 md:p-3 space-y-1">
        {loading && (
          <div className="flex justify-center py-6">
            <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
          </div>
        )}

        {!loading && sessions.length === 0 && (
          <p className="hidden md:block text-xs text-muted-foreground text-center px-2 py-4">
            هنوز گفتگویی ذخیره نشده است
          </p>
        )}

        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`group w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-right transition-colors justify-center md:justify-start ${
              s.id === activeSessionId
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
            }`}
          >
            <MessageCircle className="w-4 h-4 flex-shrink-0" />
            <span className="hidden md:flex flex-col flex-1 min-w-0 items-start">
              <span className="truncate w-full">{s.title}</span>
              <span className="text-[10px] text-muted-foreground">{timeAgo(s.updated_at)}</span>
            </span>
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => handleDelete(e, s.id)}
              className="hidden md:flex flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-destructive/10 hover:text-destructive"
            >
              {deletingId === s.id ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Trash2 className="w-3.5 h-3.5" />
              )}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
