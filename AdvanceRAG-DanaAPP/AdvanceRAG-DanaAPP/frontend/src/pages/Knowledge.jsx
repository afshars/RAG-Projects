import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, Trash2, Loader2, Files, FileType2, Image as ImageIcon, Globe, Link as LinkIcon } from 'lucide-react';
import { listChunks, uploadDocument, deleteDocument, deleteAllDocuments, ingestUrl } from '@/api/knowledge';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const SUPPORTED = ['.pdf', '.txt', '.md', '.html', '.htm', '.docx', '.png', '.jpg', '.jpeg', '.webp', '.gif'];
const WEB_TYPES = ['web', 'api'];

export default function Knowledge() {
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [urlValue, setUrlValue] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);
  const inputRef = useRef(null);
  const { toast } = useToast();

  useEffect(() => {
    loadChunks();
  }, []);

  const loadChunks = async () => {
    setLoading(true);
    try {
      const data = await listChunks();
      setChunks(data);
    } catch {
      toast({ title: 'خطا', description: 'بارگذاری منابع ناموفق بود.', variant: 'destructive' });
    }
    setLoading(false);
  };

  const handleFiles = async (files) => {
    const fileArr = Array.from(files);
    setProcessing(true);

    for (const file of fileArr) {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!SUPPORTED.includes(ext)) {
        toast({
          title: 'فرمت پشتیبانی نمی‌شود',
          description: `«${file.name}»: فقط ${SUPPORTED.join(', ')} پشتیبانی می‌شود.`,
          variant: 'destructive',
        });
        continue;
      }

      try {
        // Upload sends the raw file to the backend, which extracts text,
        // chunks it, computes embeddings, and stores everything server-side.
        const records = await uploadDocument(file);
        toast({
          title: 'موفق',
          description: `«${file.name}»: ${records.length} بخش ایجاد شد.`,
        });
      } catch (err) {
        toast({
          title: 'خطا',
          description: `پردازش «${file.name}» ناموفق بود: ${err.message || ''}`,
          variant: 'destructive',
        });
      }
    }

    setProcessing(false);
    await loadChunks();
  };

  const handleIngestUrl = async () => {
    const url = urlValue.trim();
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) {
      toast({ title: 'خطا', description: 'آدرس باید با http:// یا https:// شروع شود.', variant: 'destructive' });
      return;
    }

    setUrlLoading(true);
    try {
      // Fetches the page/API endpoint server-side and runs it through the
      // same chunk/embed/index pipeline as an uploaded file.
      const records = await ingestUrl(url);
      toast({ title: 'موفق', description: `«${url}»: ${records.length} بخش ایجاد شد.` });
      setUrlValue('');
      await loadChunks();
    } catch (err) {
      toast({
        title: 'خطا',
        description: `دریافت آدرس ناموفق بود: ${err.message || ''}`,
        variant: 'destructive',
      });
    }
    setUrlLoading(false);
  };

  const handleDeleteDocument = async (docId, name) => {
    try {
      await deleteDocument(docId);
      toast({ title: 'حذف شد', description: `«${name}» حذف شد.` });
      await loadChunks();
    } catch {
      toast({ title: 'خطا', description: 'حذف ناموفق بود.', variant: 'destructive' });
    }
  };

  const clearAll = async () => {
    try {
      await deleteAllDocuments();
      toast({ title: 'پاک شد', description: 'تمام منابع حذف شدند.' });
      await loadChunks();
    } catch {
      toast({ title: 'خطا', description: 'عملیات ناموفق بود.', variant: 'destructive' });
    }
  };

  // Group chunks by document
  const documents = {};
  chunks.forEach((c) => {
    if (!documents[c.document_id]) {
      documents[c.document_id] = {
        name: c.source_name,
        type: c.source_type || 'unknown',
        count: 0,
        words: 0,
        author: c.author,
        documentDate: c.document_date,
      };
    }
    documents[c.document_id].count++;
    documents[c.document_id].words += c.word_count || 0;
  });
  const docList = Object.entries(documents);

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">منابع دانش</h2>
            <p className="text-sm text-muted-foreground mt-1">
              بارگذاری فایل‌ها برای بازیابی RAG
            </p>
          </div>
          {chunks.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearAll} className="text-destructive">
              <Trash2 className="w-4 h-4 ml-1.5" />
              پاک کردن همه
            </Button>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <Files className="w-4 h-4" />
              <span className="text-xs font-medium">اسناد</span>
            </div>
            <p className="text-2xl font-bold text-foreground">{docList.length}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-muted-foreground mb-1">
              <FileText className="w-4 h-4" />
              <span className="text-xs font-medium">بخش‌ها (چانک)</span>
            </div>
            <p className="text-2xl font-bold text-foreground">{chunks.length}</p>
          </div>
        </div>

        {/* Upload area */}
        <div
          onClick={() => !processing && inputRef.current?.click()}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (!processing) handleFiles(e.dataTransfer.files);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          className={`relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-10 cursor-pointer transition-all ${
            processing
              ? 'border-border opacity-60 cursor-wait'
              : isDragging
              ? 'border-primary bg-accent scale-[1.01]'
              : 'border-border hover:border-primary/40 hover:bg-muted/50'
          }`}
        >
          {processing ? (
            <>
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
              <p className="text-sm font-medium text-foreground">در حال پردازش فایل‌ها...</p>
              <p className="text-xs text-muted-foreground">استخراج متن، چانک‌بندی و embedding</p>
            </>
          ) : (
            <>
              <div className="flex items-center justify-center w-14 h-14 rounded-full bg-accent text-primary">
                <Upload className="w-6 h-6" />
              </div>
              <p className="text-sm font-medium text-foreground">
                فایل‌ها را رها کنید یا کلیک کنید
              </p>
              <div className="flex flex-wrap gap-1.5 justify-center max-w-md">
                {SUPPORTED.map((fmt) => (
                  <span
                    key={fmt}
                    className="text-[11px] font-mono bg-muted text-muted-foreground px-2 py-0.5 rounded"
                  >
                    {fmt}
                  </span>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground text-center max-w-sm">
                برای تصاویر، مدل انتخاب‌شده در تنظیمات باید از ورودی تصویری (vision) پشتیبانی کند —
                محتوای تصویر توسط همان مدل توصیف/رونویسی و قابل‌جستجو می‌شود.
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            accept={SUPPORTED.join(',')}
            onChange={(e) => {
              if (e.target.files.length) handleFiles(e.target.files);
              e.target.value = '';
            }}
          />
        </div>

        {/* URL / API ingestion */}
        <div className="rounded-2xl border border-border bg-card p-4 space-y-2">
          <div className="flex items-center gap-2 text-foreground">
            <Globe className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium">افزودن از یک آدرس اینترنتی (وب‌سایت یا API)</span>
          </div>
          <div className="flex gap-2">
            <Input
              dir="ltr"
              value={urlValue}
              onChange={(e) => setUrlValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !urlLoading) handleIngestUrl();
              }}
              placeholder="https://example.com/article"
              disabled={urlLoading}
              className="text-left text-sm flex-1"
            />
            <Button onClick={handleIngestUrl} disabled={urlLoading || !urlValue.trim()}>
              {urlLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <LinkIcon className="w-4 h-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            محتوای صفحه وب یا پاسخ JSON یک API گرفته و مثل بقیه منابع، چانک/embedding/ایندکس می‌شود.
          </p>
        </div>

        {/* Document list */}
        <div className="space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
            </div>
          ) : docList.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <FileType2 className="w-10 h-10 mx-auto mb-2 opacity-40" />
              <p className="text-sm">هنوز منبعی بارگذاری نشده است</p>
            </div>
          ) : (
            docList.map(([docId, doc]) => (
              <div
                key={docId}
                className="flex items-center gap-3 rounded-xl border border-border bg-card p-3.5 hover:shadow-sm transition-shadow"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-accent text-primary flex items-center justify-center">
                  {['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(doc.type) ? (
                    <ImageIcon className="w-5 h-5" />
                  ) : WEB_TYPES.includes(doc.type) ? (
                    <Globe className="w-5 h-5" />
                  ) : (
                    <FileText className="w-5 h-5" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{doc.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {doc.count} بخش • {doc.words.toLocaleString('fa-IR')} واژه • {doc.type.toUpperCase()}
                  </p>
                  {(doc.author || doc.documentDate) && (
                    <p className="text-[11px] text-muted-foreground/80 mt-0.5">
                      {[doc.author, doc.documentDate].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleDeleteDocument(docId, doc.name)}
                  className="flex-shrink-0 w-8 h-8 rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive flex items-center justify-center transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>

        <p className="text-[11px] text-muted-foreground text-center pt-2">
          ساخته شده توسط مهندس سارا افشار
        </p>
      </div>
    </div>
  );
}
