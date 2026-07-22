import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Send, Sparkles, BookOpen } from 'lucide-react';
import { streamChat } from '@/api/chat';
import * as sessionsApi from '@/api/sessions';
import { useToast } from '@/components/ui/use-toast';
import ChatMessage from '@/components/dana/ChatMessage';
import ChatHistorySidebar from '@/components/dana/ChatHistorySidebar';

// Maps a saved session's stored messages (backend shape) into the shape
// ChatMessage/this component render.
function fromStoredMessages(stored) {
  return (stored || []).map((m) => ({
    id: crypto.randomUUID(),
    role: m.role,
    content: m.content || '',
    sources: m.sources || undefined,
    confidence: m.confidence || undefined,
  }));
}

export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlSessionId = searchParams.get('session');

  const [activeSessionId, setActiveSessionId] = useState(urlSessionId || null);
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionLoading, setSessionLoading] = useState(false);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const scrollRef = useRef(null);
  // Set right before we switch activeSessionId to a session we just created
  // inline (first message of a brand-new chat). Prevents the session-load
  // effect below from re-fetching that session — it's still empty on the
  // backend at this point (messages persist only after streaming finishes)
  // and would wipe out the optimistic messages we're about to render.
  const skipNextSessionLoadRef = useRef(false);
  const { toast } = useToast();

  const refreshSessions = useCallback(async () => {
    try {
      const list = await sessionsApi.listSessions();
      setSessions(list);
    } catch {
      /* silently ignore — history list is a nice-to-have, not core chat */
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // Load the selected session's saved messages whenever it changes.
  useEffect(() => {
    let cancelled = false;
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    if (skipNextSessionLoadRef.current) {
      skipNextSessionLoadRef.current = false;
      return;
    }
    setSessionLoading(true);
    sessionsApi
      .getSession(activeSessionId)
      .then(async (data) => {
        if (cancelled) return;
        const loaded = fromStoredMessages(data.messages);
        setMessages(loaded);
        // Feedback is stored separately (by message position), so merge it
        // in once both have loaded — a failure here just means the
        // 👍/👎 state won't be pre-highlighted, chat itself still works.
        try {
          const feedbackList = await sessionsApi.listFeedback(activeSessionId);
          if (cancelled || !feedbackList.length) return;
          const byIndex = new Map(feedbackList.map((f) => [f.message_index, f]));
          setMessages((prev) =>
            prev.map((m, i) => {
              const f = byIndex.get(i);
              if (!f) return m;
              return {
                ...m,
                feedback: f.rating,
                detailedFeedback: {
                  usefulness: f.usefulness,
                  correctness: f.correctness,
                  completeness: f.completeness,
                },
              };
            })
          );
        } catch {
          /* best-effort */
        }
      })
      .catch(() => {
        if (!cancelled) {
          toast({
            title: 'خطا',
            description: 'بارگذاری این گفتگو ناموفق بود.',
            variant: 'destructive',
          });
        }
      })
      .finally(() => {
        if (!cancelled) setSessionLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const updateMsg = (id, updates) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...updates } : m)));
  };

  const appendToMsg = (id, token) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: m.content + token } : m))
    );
  };

  const selectSession = (id) => {
    setActiveSessionId(id);
    setSearchParams(id ? { session: id } : {});
  };

  const startNewChat = () => {
    setActiveSessionId(null);
    setSearchParams({});
    setMessages([]);
  };

  const handleDeleteSession = async (id) => {
    try {
      await sessionsApi.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (id === activeSessionId) {
        startNewChat();
      }
    } catch {
      toast({ title: 'خطا', description: 'حذف گفتگو ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isProcessing) return;

    const userText = input.trim();
    const assistantId = crypto.randomUUID();

    // A brand-new (unsaved) chat gets a session created on the first
    // message, so it immediately shows up in the history list on the left.
    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const created = await sessionsApi.createSession();
        sessionId = created.id;
        skipNextSessionLoadRef.current = true;
        setActiveSessionId(sessionId);
        setSearchParams({ session: sessionId });
        setSessions((prev) => [
          { id: sessionId, title: created.title, updated_at: created.updated_at },
          ...prev,
        ]);
      } catch {
        // History is best-effort — the chat itself still works without it.
      }
    }

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: userText },
      { id: assistantId, role: 'assistant', content: '', loading: true, streaming: false },
    ]);
    setInput('');
    setIsProcessing(true);

    try {
      // Retrieval + LLM orchestration now happens entirely on the backend
      // (/chat): it loads the user's knowledge base, runs hybrid RAG
      // retrieval, and streams the answer back over SSE.
      const history = [...messages, { role: 'user', content: userText }]
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }));

      let gotAnyToken = false;
      let sources = [];

      await streamChat(history, {
        sessionId,
        onCitations: (citations, confidence) => {
          sources = citations.map((c) => ({
            title: `${c.source_name}`,
            content: c.content,
            score: c.score,
            author: c.author,
            documentDate: c.document_date,
          }));
          updateMsg(assistantId, {
            loading: false,
            streaming: true,
            sources,
            confidence: confidence || undefined,
          });
        },
        onToken: (token) => {
          gotAnyToken = true;
          appendToMsg(assistantId, token);
        },
      });

      if (!gotAnyToken && sources.length === 0) {
        updateMsg(assistantId, {
          loading: false,
          streaming: false,
          content:
            'هیچ منبعی بارگذاری نشده یا پاسخ این سوال در منابع موجود یافت نشد. لطفاً ابتدا در بخش «منابع» فایل‌های خود را بارگذاری کنید.',
        });
      } else {
        updateMsg(assistantId, { streaming: false });
      }

      refreshSessions();
    } catch (error) {
      updateMsg(assistantId, {
        loading: false,
        streaming: false,
        content: `متأسفانه خطایی رخ داد: ${error.message || 'خطای ناشناخته'}. لطفاً تنظیمات LLM را در بخش «تنظیمات» بررسی کنید.`,
      });
      toast({
        title: 'خطا',
        description: 'پردازش درخواست ناموفق بود.',
        variant: 'destructive',
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFeedback = async (msgId, type) => {
    const index = messages.findIndex((m) => m.id === msgId);
    if (index === -1) return;

    if (!activeSessionId) {
      toast({ title: 'خطا', description: 'این گفتگو هنوز ذخیره نشده است.', variant: 'destructive' });
      return;
    }

    const alreadySet = messages[index]?.feedback === type;

    try {
      if (alreadySet) {
        await sessionsApi.clearFeedback(activeSessionId, index);
        setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: undefined } : m)));
        return;
      }

      await sessionsApi.setFeedback(activeSessionId, index, type);
      setMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, feedback: type } : m)));
      toast({
        title: type === 'up' ? 'بازخورد مثبت ثبت شد' : 'بازخورد منفی ثبت شد',
        description: 'سپاس از شما! برای بهبود مستمر سیستم استفاده می‌شود.',
      });
    } catch {
      toast({ title: 'خطا', description: 'ثبت بازخورد ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleDetailedFeedback = async (msgId, scores) => {
    const index = messages.findIndex((m) => m.id === msgId);
    if (index === -1) return;

    if (!activeSessionId) {
      toast({ title: 'خطا', description: 'این گفتگو هنوز ذخیره نشده است.', variant: 'destructive' });
      return;
    }

    // The rating column is required by the backend schema — if the user
    // hasn't given a quick 👍/👎 yet, default to 'up' so the detailed
    // scores (which are the actual signal here) can still be saved.
    const rating = messages[index]?.feedback || 'up';

    try {
      await sessionsApi.setFeedback(activeSessionId, index, rating, null, scores);
      setMessages((prev) =>
        prev.map((m) => (m.id === msgId ? { ...m, feedback: rating, detailedFeedback: scores } : m))
      );
      toast({ title: 'ارزیابی ثبت شد', description: 'سپاس از ارزیابی دقیق شما.' });
    } catch {
      toast({ title: 'خطا', description: 'ثبت ارزیابی ناموفق بود.', variant: 'destructive' });
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-row h-full bg-background">
      <div className="flex flex-col flex-1 min-w-0">
        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {sessionLoading && (
              <div className="flex justify-center py-10">
                <div className="w-6 h-6 border-2 border-slate-200 border-t-slate-800 rounded-full animate-spin" />
              </div>
            )}

            {!sessionLoading && messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
                <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20 mb-5">
                  <Sparkles className="w-8 h-8 text-primary-foreground" />
                </div>
                <h2 className="text-2xl font-bold text-foreground mb-2">سلام، من دانا هستم</h2>
                <p className="text-sm text-muted-foreground max-w-md leading-relaxed">
                  سیستم پیشرفته بازیابی و تولید متن. سوال خود را بپرسید تا بر اساس منابع بارگذاری‌شده
                  با ارجاعات دقیق پاسخ دهم.
                </p>
                <div className="mt-6 w-full max-w-2xl text-start bg-accent rounded-xl px-5 py-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-foreground mb-1">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>راهنمای شروع کار با دانا</span>
                  </div>
                  <p className="text-xs text-foreground/70 mb-2.5">
                    برای شروع، مراحل زیر را به‌ترتیب انجام دهید:
                  </p>
                  <ol className="space-y-2 text-xs text-foreground/80 leading-relaxed">
                    <li className="flex gap-1.5">
                      <span className="flex-shrink-0 font-semibold text-foreground/80">1.</span>
                      <span>
                        <span className="font-semibold text-foreground">افزودن منابع</span> — الزامی:
                        فایل‌ها و اسناد موردنظر را در بخش «منابع» بارگذاری کنید.
                      </span>
                    </li>
                    <li className="flex gap-1.5">
                      <span className="flex-shrink-0 font-semibold text-foreground/80">2.</span>
                      <span>
                        <span className="font-semibold text-foreground">انتخاب مدل زبانی</span> — الزامی:
                        در بخش «تنظیمات»، مدل زبانی (LLM) موردنظر را انتخاب یا پیکربندی کنید.
                        <br />
                        توجه: بدون انتخاب مدل زبانی، دانا قادر به پاسخ‌گویی نخواهد بود.
                      </span>
                    </li>
                    <li className="flex gap-1.5">
                      <span className="flex-shrink-0 font-semibold text-foreground/80">3.</span>
                      <span>
                        <span className="font-semibold text-foreground">پرسیدن سؤال</span>: سؤال خود را
                        در بخش «گفت‌وگو» وارد کنید تا دانا بر اساس منابع بارگذاری‌شده پاسخ دهد.
                      </span>
                    </li>
                    <li className="flex gap-1.5">
                      <span className="flex-shrink-0 font-semibold text-foreground/80">4.</span>
                      <span>
                        <span className="font-semibold text-foreground">تنظیم پارامترهای RAG</span> —
                        اختیاری: برای بهینه‌سازی فرایند بازیابی و پاسخ‌گویی، پارامترهای RAG را در بخش
                        «تنظیمات» تغییر دهید و نتایج را آزمایش کنید.
                      </span>
                    </li>
                    <li className="flex gap-1.5">
                      <span className="flex-shrink-0 font-semibold text-foreground/80">5.</span>
                      <span>
                        <span className="font-semibold text-foreground">ارزیابی عملکرد</span> — اختیاری:
                        برای سنجش کیفیت بازیابی اطلاعات و تولید پاسخ، به بخش «ارزیابی» مراجعه کنید.
                      </span>
                    </li>
                  </ol>
                </div>
              </div>
            )}

            {!sessionLoading &&
              messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onFeedback={handleFeedback}
                  onDetailedFeedback={handleDetailedFeedback}
                />
              ))}
          </div>
        </div>

        {/* Input Area */}
        <div className="flex-shrink-0 border-t border-border bg-white/80 backdrop-blur-md">
          <div className="max-w-3xl mx-auto px-4 py-4">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="سوال خود را اینجا بنویسید..."
                rows={1}
                className="flex-1 resize-none rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all max-h-32"
                style={{ minHeight: '40px' }}
              />

              <button
                onClick={handleSend}
                disabled={isProcessing || !input.trim()}
                className="flex-shrink-0 w-10 h-10 rounded-xl bg-primary text-primary-foreground flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary/90 active:scale-95 transition-all shadow-md shadow-primary/20"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[11px] text-muted-foreground text-center mt-2">
              ساخته شده توسط مهندس سارا افشار
            </p>
          </div>
        </div>
      </div>

      <ChatHistorySidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={selectSession}
        onNew={startNewChat}
        onDelete={handleDeleteSession}
        loading={sessionsLoading}
      />
    </div>
  );
}
