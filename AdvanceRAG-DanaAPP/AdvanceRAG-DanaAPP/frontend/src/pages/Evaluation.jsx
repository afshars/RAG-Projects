import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Plus, Trash2, PlayCircle, Loader2, ClipboardList, History, ChevronDown, ChevronUp } from 'lucide-react';
import {
  listEvalItems,
  createEvalItem,
  deleteEvalItem,
  listEvalRuns,
  getEvalRun,
  deleteEvalRun,
  deleteAllEvalRuns,
  runEvaluation,
} from '@/api/evaluation';
import { listChunks } from '@/api/knowledge';
import { toUtcDate } from '@/lib/utils';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const K_OPTIONS = [1, 3, 5, 10];

function pct(v) {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;
}

export default function Evaluation() {
  const [items, setItems] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [runs, setRuns] = useState([]);
  const [activeRun, setActiveRun] = useState(null);
  const [expandedItem, setExpandedItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [deletingRun, setDeletingRun] = useState(false);

  // new item form
  const [query, setQuery] = useState('');
  const [selectedChunkIds, setSelectedChunkIds] = useState([]);
  const [addingChunk, setAddingChunk] = useState('');

  const { toast } = useToast();

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [itemsData, chunksData, runsData] = await Promise.all([
        listEvalItems(),
        listChunks(),
        listEvalRuns(),
      ]);
      setItems(itemsData);
      setChunks(chunksData);
      setRuns(runsData);
      if (runsData.length && !activeRun) {
        const full = await getEvalRun(runsData[0].id);
        setActiveRun(full);
      }
    } catch {
      toast({ title: 'خطا', description: 'بارگذاری اطلاعات ارزیابی ناموفق بود.', variant: 'destructive' });
    }
    setLoading(false);
  };

  const handleAddItem = async () => {
    if (!query.trim()) return;
    try {
      await createEvalItem({
        query: query.trim(),
        relevant_chunk_ids: selectedChunkIds,
      });
      setQuery('');
      setSelectedChunkIds([]);
      toast({ title: 'اضافه شد', description: 'مورد آزمایشی ذخیره شد.' });
      const itemsData = await listEvalItems();
      setItems(itemsData);
    } catch (err) {
      toast({ title: 'خطا', description: err.message || 'ذخیره ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleDeleteItem = async (id) => {
    try {
      await deleteEvalItem(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch {
      toast({ title: 'خطا', description: 'حذف ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleRun = async () => {
    if (!items.length) {
      toast({ title: 'خطا', description: 'ابتدا حداقل یک مورد آزمایشی اضافه کنید.', variant: 'destructive' });
      return;
    }
    setRunning(true);
    try {
      const run = await runEvaluation({ kValues: K_OPTIONS, evaluateGeneration: true });
      setActiveRun(run);
      const runsData = await listEvalRuns();
      setRuns(runsData);
      toast({ title: 'اجرا کامل شد', description: `ارزیابی روی ${run.item_count} مورد انجام شد.` });
    } catch (err) {
      toast({ title: 'خطا', description: err.message || 'اجرای ارزیابی ناموفق بود.', variant: 'destructive' });
    }
    setRunning(false);
  };

  const handleSelectRun = async (id) => {
    try {
      const full = await getEvalRun(id);
      setActiveRun(full);
    } catch {
      toast({ title: 'خطا', description: 'بارگذاری اجرا ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleDeleteRun = async (id) => {
    setDeletingRun(true);
    try {
      await deleteEvalRun(id);
      const runsData = await listEvalRuns();
      setRuns(runsData);
      if (activeRun?.id === id) {
        setActiveRun(runsData.length ? await getEvalRun(runsData[0].id) : null);
      }
      toast({ title: 'حذف شد', description: 'اجرای ارزیابی حذف شد.' });
    } catch {
      toast({ title: 'خطا', description: 'حذف اجرا ناموفق بود.', variant: 'destructive' });
    }
    setDeletingRun(false);
  };

  const handleDeleteAllRuns = async () => {
    if (!window.confirm('همهٔ تاریخچهٔ اجراهای ارزیابی حذف شود؟ این کار قابل بازگشت نیست.')) return;
    setDeletingRun(true);
    try {
      await deleteAllEvalRuns();
      setRuns([]);
      setActiveRun(null);
      toast({ title: 'حذف شد', description: 'همهٔ تاریخچهٔ ارزیابی پاک شد.' });
    } catch {
      toast({ title: 'خطا', description: 'حذف تاریخچه ناموفق بود.', variant: 'destructive' });
    }
    setDeletingRun(false);
  };

  const toggleChunk = (id) => {
    setSelectedChunkIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const summary = activeRun?.summary || {};
  const retrievalRows = K_OPTIONS.map((k) => ({
    k,
    precision: summary[`precision@${k}`],
    recall: summary[`recall@${k}`],
    ndcg: summary[`ndcg@${k}`],
  }));

  return (
    <div className="h-full overflow-y-auto p-4 md:p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-bold text-foreground flex items-center gap-2">
          <ClipboardList className="w-5 h-5" />
          ارزیابی بازیابی و تولید
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          مجموعه تست بسازید (سوال + منابع درست) و پایپ‌لاین RAG را روی آن اجرا کنید تا معیارهای
          بازیابی (Precision@k, Recall@k, MRR, NDCG@k) و تولید (Faithfulness, Answer Relevance) محاسبه شود.
        </p>
      </div>

      {/* Add test item */}
      <section className="border border-border rounded-xl p-4 space-y-3">
        <h2 className="text-sm font-semibold text-foreground">افزودن مورد آزمایشی</h2>
        <Textarea
          placeholder="سوال..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={2}
        />
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            منابع درست (چانک‌هایی که باید بازیابی شوند) — اختیاری؛ بدون آن فقط معیارهای تولید محاسبه می‌شود.
          </p>
          <div className="flex gap-2">
            <Select value={addingChunk} onValueChange={setAddingChunk}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="یک بخش را انتخاب کنید..." />
              </SelectTrigger>
              <SelectContent>
                {chunks.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.source_name} — {c.content.slice(0, 60)}…
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="outline"
              disabled={!addingChunk}
              onClick={() => {
                if (addingChunk) toggleChunk(addingChunk);
                setAddingChunk('');
              }}
            >
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          {selectedChunkIds.length > 0 && (
            <ul className="text-xs space-y-1">
              {selectedChunkIds.map((id) => {
                const c = chunks.find((ch) => ch.id === id);
                return (
                  <li key={id} className="flex items-center justify-between bg-muted rounded px-2 py-1">
                    <span className="truncate">{c ? `${c.source_name} — ${c.content.slice(0, 60)}…` : id}</span>
                    <button onClick={() => toggleChunk(id)} className="text-destructive shrink-0 ms-2">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <Button onClick={handleAddItem} disabled={!query.trim()} size="sm">
          <Plus className="w-4 h-4 me-1" /> افزودن
        </Button>
      </section>

      {/* Test set list */}
      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">مجموعه تست ({items.length})</h2>
          <Button onClick={handleRun} disabled={running || !items.length} size="sm">
            {running ? <Loader2 className="w-4 h-4 me-1 animate-spin" /> : <PlayCircle className="w-4 h-4 me-1" />}
            اجرای ارزیابی
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">در حال بارگذاری...</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">هنوز موردی اضافه نشده است.</p>
        ) : (
          <ul className="space-y-1">
            {items.map((it) => (
              <li key={it.id} className="flex items-center justify-between border border-border rounded-lg px-3 py-2 text-sm">
                <div>
                  <p className="text-foreground">{it.query}</p>
                  <p className="text-xs text-muted-foreground">{it.relevant_chunk_ids.length} منبع درست</p>
                </div>
                <button onClick={() => handleDeleteItem(it.id)} className="text-destructive shrink-0">
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Runs history */}
      {runs.length > 0 && (
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <History className="w-4 h-4" /> اجراهای قبلی
            </h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-destructive"
              disabled={deletingRun}
              onClick={handleDeleteAllRuns}
            >
              <Trash2 className="w-3.5 h-3.5 me-1" /> پاک کردن همه
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Select value={activeRun?.id || ''} onValueChange={handleSelectRun}>
              <SelectTrigger className="w-full md:w-80">
                <SelectValue placeholder="یک اجرا را انتخاب کنید" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {toUtcDate(r.created_at).toLocaleString('fa-IR')} — {r.item_count} مورد
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {activeRun && (
              <button
                type="button"
                disabled={deletingRun}
                onClick={() => handleDeleteRun(activeRun.id)}
                className="text-destructive shrink-0 p-2 hover:bg-muted rounded-lg"
                title="حذف این اجرا"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </section>
      )}

      {/* Results */}
      {activeRun && (
        <section className="space-y-6">
          <div>
            <h2 className="text-sm font-semibold text-foreground mb-2">معیارهای بازیابی</h2>
            <div className="overflow-x-auto border border-border rounded-lg">
              <table className="w-full text-sm text-center">
                <thead className="bg-muted">
                  <tr>
                    <th className="p-2 text-start">k</th>
                    <th className="p-2">Precision@k</th>
                    <th className="p-2">Recall@k</th>
                    <th className="p-2">NDCG@k</th>
                  </tr>
                </thead>
                <tbody>
                  {retrievalRows.map((row) => (
                    <tr key={row.k} className="border-t border-border">
                      <td className="p-2 text-start font-medium">{row.k}</td>
                      <td className="p-2">{pct(row.precision)}</td>
                      <td className="p-2">{pct(row.recall)}</td>
                      <td className="p-2">{pct(row.ndcg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground mt-1">MRR: {pct(summary.mrr)}</p>
          </div>

          {(summary.faithfulness !== undefined || summary.answer_relevance !== undefined) && (
            <div>
              <h2 className="text-sm font-semibold text-foreground mb-2">معیارهای تولید (قضاوت مدل زبانی)</h2>
              <div className="grid grid-cols-2 gap-3 max-w-md">
                <div className="border border-border rounded-lg p-3 text-center">
                  <p className="text-xs text-muted-foreground">Faithfulness</p>
                  <p className="text-lg font-bold">{pct(summary.faithfulness)}</p>
                </div>
                <div className="border border-border rounded-lg p-3 text-center">
                  <p className="text-xs text-muted-foreground">Answer Relevance</p>
                  <p className="text-lg font-bold">{pct(summary.answer_relevance)}</p>
                </div>
              </div>
            </div>
          )}

          <div>
            <h2 className="text-sm font-semibold text-foreground mb-2">جزئیات هر مورد</h2>
            <ul className="space-y-2">
              {(activeRun.details || []).map((d) => (
                <li key={d.item_id} className="border border-border rounded-lg">
                  <button
                    className="w-full flex items-center justify-between p-3 text-start"
                    onClick={() => setExpandedItem(expandedItem === d.item_id ? null : d.item_id)}
                  >
                    <span className="text-sm text-foreground truncate">{d.query}</span>
                    {expandedItem === d.item_id ? (
                      <ChevronUp className="w-4 h-4 shrink-0" />
                    ) : (
                      <ChevronDown className="w-4 h-4 shrink-0" />
                    )}
                  </button>
                  {expandedItem === d.item_id && (
                    <div className="px-3 pb-3 text-xs space-y-2 text-muted-foreground">
                      {d.retrieval && (
                        <p>
                          Precision@5: {pct(d.retrieval['precision@5'])} · Recall@5: {pct(d.retrieval['recall@5'])} ·
                          {' '}NDCG@5: {pct(d.retrieval['ndcg@5'])} · MRR: {pct(d.retrieval.mrr)}
                        </p>
                      )}
                      {d.generation && (
                        <p>
                          Faithfulness: {pct(d.generation.faithfulness)} · Answer Relevance:{' '}
                          {pct(d.generation.answer_relevance)}
                        </p>
                      )}
                      {d.answer && (
                        <div>
                          <p className="font-medium text-foreground/80 mb-1">پاسخ تولید شده:</p>
                          <div className="markdown-body">
                            <ReactMarkdown>{d.answer}</ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <p className="text-[11px] text-muted-foreground text-center">
        ساخته شده توسط مهندس سارا افشار
      </p>
    </div>
  );
}
