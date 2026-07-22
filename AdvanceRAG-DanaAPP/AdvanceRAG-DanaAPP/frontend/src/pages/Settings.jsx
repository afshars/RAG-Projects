import React, { useState, useEffect } from 'react';
import { Save, Eye, EyeOff, RotateCcw, Cpu, SlidersHorizontal, Loader2, Image as ImageIcon } from 'lucide-react';
import { loadSettings, saveSettings, DEFAULT_SETTINGS, MODEL_PRESETS } from '@/lib/settings';
import { useToast } from '@/components/ui/use-toast';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const CUSTOM_MODEL_VALUE = '__custom__';

export default function Settings() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [activeView, setActiveView] = useState('llm'); // 'llm' | 'rag'
  const [showApiKey, setShowApiKey] = useState(false);
  const [showVisionApiKey, setShowVisionApiKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadSettings()
      .then(setSettings)
      .finally(() => setLoading(false));
  }, []);

  const updateLLM = (key, value) =>
    setSettings((s) => ({ ...s, llm: { ...s.llm, [key]: value } }));

  const updateVision = (key, value) =>
    setSettings((s) => ({ ...s, vision: { ...s.vision, [key]: value } }));

  const updateRAG = (key, value) =>
    setSettings((s) => ({ ...s, rag: { ...s.rag, [key]: value } }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const saved = await saveSettings(settings);
      setSettings(saved);
      toast({ title: 'تنظیمات ذخیره شد', description: 'تغییرات با موفقیت اعمال شد.' });
    } catch (err) {
      toast({ title: 'خطا', description: err.message || 'ذخیره ناموفق بود.', variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSettings(DEFAULT_SETTINGS);
    try {
      const saved = await saveSettings(DEFAULT_SETTINGS);
      setSettings(saved);
      toast({ title: 'بازنشانی شد', description: 'تنظیمات به حالت پیش‌فرض بازگشت.' });
    } catch (err) {
      toast({ title: 'خطا', description: err.message || 'بازنشانی ناموفق بود.', variant: 'destructive' });
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-muted-foreground animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">
              {activeView === 'llm' ? 'تنظیمات مدل‌های زبانی (LLM)' : 'تنظیمات پارامترهای RAG'}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {activeView === 'llm'
                ? 'پیکربندی مدل چت و مدل پردازش تصویر'
                : 'پیکربندی فرایند بازیابی و تولید پاسخ سیستم RAG'}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 ml-1.5" />
            بازنشانی
          </Button>
        </div>

        {/* Cross-navigation between the two settings views */}
        {activeView === 'llm' ? (
          <Card className="border-2 border-primary bg-primary/10">
            <CardContent className="flex items-center justify-between gap-4 py-5">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <SlidersHorizontal className="w-4.5 h-4.5 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">تنظیمات پارامترهای RAG</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    جهت پیکربندی فرایند بازیابی و تولید پاسخ سیستم RAG به بخش «تنظیمات پارامترهای
                    RAG» مراجعه نمایید.
                  </p>
                </div>
              </div>
              <Button size="sm" onClick={() => setActiveView('rag')} className="flex-shrink-0">
                ورود
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-2 border-primary bg-primary/10">
            <CardContent className="flex items-center justify-between gap-4 py-5">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <Cpu className="w-4.5 h-4.5 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">تنظیمات مدل‌های زبانی (LLM)</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    جهت پیکربندی مدل چت و مدل پردازش تصویر به بخش «تنظیمات مدل‌های زبانی (LLM)»
                    مراجعه نمایید.
                  </p>
                </div>
              </div>
              <Button size="sm" onClick={() => setActiveView('llm')} className="flex-shrink-0">
                ورود
              </Button>
            </CardContent>
          </Card>
        )}

        {activeView === 'llm' ? (
          <>
            {/* LLM Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Cpu className="w-4.5 h-4.5 text-primary" />
                  تنظیمات مدل زبانی (LLM)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Base URL</Label>
                  <Input
                    dir="ltr"
                    value={settings.llm.baseUrl}
                    onChange={(e) => updateLLM('baseUrl', e.target.value)}
                    placeholder="https://api.gapgpt.app/v1"
                    className="text-left font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    آدرس پایه هر API سازگار با OpenAI (OpenAI, vLLM, LM Studio, Groq, Together, ...)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>مدل چت (Model)</Label>
                  <Select
                    value={MODEL_PRESETS.includes(settings.llm.model) ? settings.llm.model : CUSTOM_MODEL_VALUE}
                    onValueChange={(v) => updateLLM('model', v === CUSTOM_MODEL_VALUE ? '' : v)}
                  >
                    <SelectTrigger dir="ltr" className="text-left font-mono text-sm">
                      <SelectValue placeholder="انتخاب مدل" />
                    </SelectTrigger>
                    <SelectContent>
                      {MODEL_PRESETS.map((m) => (
                        <SelectItem key={m} value={m} className="font-mono text-sm">
                          {m}
                        </SelectItem>
                      ))}
                      <SelectItem value={CUSTOM_MODEL_VALUE}>سایر (وارد کردن دستی)</SelectItem>
                    </SelectContent>
                  </Select>

                  {!MODEL_PRESETS.includes(settings.llm.model) && (
                    <Input
                      dir="ltr"
                      value={settings.llm.model}
                      onChange={(e) => updateLLM('model', e.target.value)}
                      placeholder="نام دقیق مدل را وارد کنید"
                      className="text-left font-mono text-sm"
                      autoFocus
                    />
                  )}
                  <p className="text-xs text-muted-foreground">
                    یکی از مدل‌های پیش‌فرض gapgpt.app را انتخاب کنید یا نام مدل دیگری را دستی وارد کنید.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>مدل Embedding</Label>
                  <Input
                    dir="ltr"
                    value={settings.llm.embeddingModel}
                    onChange={(e) => updateLLM('embeddingModel', e.target.value)}
                    placeholder="text-embedding-3-small"
                    className="text-left font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    برای بازیابی معنایی (semantic) در RAG استفاده می‌شود
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      dir="ltr"
                      type={showApiKey ? 'text' : 'password'}
                      value={settings.llm.apiKey}
                      onChange={(e) => updateLLM('apiKey', e.target.value)}
                      placeholder="sk-..."
                      className="text-left font-mono text-sm flex-1"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    کلید در بک‌اند و به‌صورت مرتبط با حساب کاربری شما ذخیره می‌شود.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Vision Model (VLLM) Settings — optional */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ImageIcon className="w-4.5 h-4.5 text-primary" />
                  مدل تصویر (VLLM) — اختیاری
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-xs text-muted-foreground -mt-1">
                  فقط برای پردازش تصاویر بارگذاری‌شده در بخش «منابع» استفاده می‌شود (نه چت متنی
                  معمولی). اگر خالی بماند، همان مدل چت بالا برای پردازش تصویر هم به کار می‌رود —
                  با این تفاوت که اگر آن مدل از ورودی تصویری پشتیبانی نکند، بارگذاری تصویر با خطا
                  مواجه می‌شود. با تنظیم یک مدل چندوجهی (multimodal) جدا در این بخش، می‌توانید
                  برای چت روزمره از یک مدل متنی سبک‌تر و ارزان‌تر استفاده کنید و فقط هزینهٔ مدل
                  تصویری را در لحظهٔ بارگذاری تصویر بپردازید.
                </p>

                <div className="space-y-2">
                  <Label>Base URL</Label>
                  <Input
                    dir="ltr"
                    value={settings.vision.baseUrl}
                    onChange={(e) => updateVision('baseUrl', e.target.value)}
                    placeholder="در صورت خالی‌بودن، از Base URL مدل چت استفاده می‌شود"
                    className="text-left font-mono text-sm"
                  />
                </div>

                <div className="space-y-2">
                  <Label>مدل تصویر (Vision Model)</Label>
                  <Input
                    dir="ltr"
                    value={settings.vision.model}
                    onChange={(e) => updateVision('model', e.target.value)}
                    placeholder="مثلاً gpt-4o-mini یا هر مدل چندوجهی دیگر"
                    className="text-left font-mono text-sm"
                  />
                </div>

                <div className="space-y-2">
                  <Label>API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      dir="ltr"
                      type={showVisionApiKey ? 'text' : 'password'}
                      value={settings.vision.apiKey}
                      onChange={(e) => updateVision('apiKey', e.target.value)}
                      placeholder="در صورت خالی‌بودن، از API Key مدل چت استفاده می‌شود"
                      className="text-left font-mono text-sm flex-1"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setShowVisionApiKey(!showVisionApiKey)}
                    >
                      {showVisionApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          /* RAG Parameters */
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <SlidersHorizontal className="w-4.5 h-4.5 text-primary" />
                پارامترهای RAG
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Chunk Size */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>اندازه چانک (Chunk Size)</Label>
                  <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                    {settings.rag.chunkSize}
                  </span>
                </div>
                <Slider
                  value={[settings.rag.chunkSize]}
                  onValueChange={([v]) => updateRAG('chunkSize', v)}
                  min={200}
                  max={2000}
                  step={100}
                />
                <p className="text-xs text-muted-foreground">
                  تعداد کاراکترهای هر بخش (روی اسناد جدید اعمال می‌شود)
                </p>
              </div>

              {/* Chunk Overlap */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>همپوشانی چانک (Overlap)</Label>
                  <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                    {settings.rag.chunkOverlap}
                  </span>
                </div>
                <Slider
                  value={[settings.rag.chunkOverlap]}
                  onValueChange={([v]) => updateRAG('chunkOverlap', v)}
                  min={0}
                  max={500}
                  step={25}
                />
                <p className="text-xs text-muted-foreground">
                  تعداد کاراکتر مشترک بین چانک‌های متوالی
                </p>
              </div>

              {/* Fusion Method */}
              <div className="space-y-2">
                <Label>روش ترکیب نتایج (Score Fusion)</Label>
                <Select
                  value={settings.rag.fusionMethod}
                  onValueChange={(v) => updateRAG('fusionMethod', v)}
                >
                  <SelectTrigger dir="rtl" className="text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="rrf">RRF (Reciprocal Rank Fusion) — پیشنهادی</SelectItem>
                    <SelectItem value="weighted">ترکیب وزنی ساده (α)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  RRF نتایج BM25 و بردار را فقط بر اساس رتبه (نه امتیاز خام) ترکیب می‌کند —
                  چون این دو امتیاز روی مقیاس‌های متفاوتی هستند، RRF نسبت به ترکیب وزنی پایدارتر است.
                </p>
              </div>

              {settings.rag.fusionMethod === 'rrf' ? (
                /* RRF k */
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>ثابت RRF (k)</Label>
                    <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                      {settings.rag.rrfK}
                    </span>
                  </div>
                  <Slider
                    value={[settings.rag.rrfK]}
                    onValueChange={([v]) => updateRAG('rrfK', v)}
                    min={10}
                    max={100}
                    step={5}
                  />
                  <p className="text-xs text-muted-foreground">
                    عدد بزرگ‌تر یعنی وزن‌دهی یکنواخت‌تر بین رتبه‌های بالا و پایین (مقدار متعارف: ۶۰)
                  </p>
                </div>
              ) : (
                /* Hybrid Search α */
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>جستجوی هیبرید (α)</Label>
                    <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                      {settings.rag.hybridAlpha.toFixed(2)}
                    </span>
                  </div>
                  <Slider
                    value={[settings.rag.hybridAlpha]}
                    onValueChange={([v]) => updateRAG('hybridAlpha', v)}
                    min={0}
                    max={1}
                    step={0.05}
                  />
                  <p className="text-xs text-muted-foreground">
                    وزن ترکیب شباهت معنایی (embedding) و تطابق لغوی (TF-IDF) — ۱ = فقط معنایی
                  </p>
                </div>
              )}

              {/* MMR λ */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>تنوع MMR (λ)</Label>
                  <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                    {settings.rag.mmrLambda.toFixed(2)}
                  </span>
                </div>
                <Slider
                  value={[settings.rag.mmrLambda]}
                  onValueChange={([v]) => updateRAG('mmrLambda', v)}
                  min={0}
                  max={1}
                  step={0.05}
                />
                <p className="text-xs text-muted-foreground">
                  ۱ = بیشترین ارتباط، ۰ = بیشترین تنوع بین چانک‌ها
                </p>
              </div>

              {/* Top K */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>تعداد نتایج (Top K)</Label>
                  <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                    {settings.rag.topK}
                  </span>
                </div>
                <Slider
                  value={[settings.rag.topK]}
                  onValueChange={([v]) => updateRAG('topK', v)}
                  min={1}
                  max={20}
                  step={1}
                />
                <p className="text-xs text-muted-foreground">تعداد چانک‌های بازیابی‌شده برای پاسخ</p>
              </div>

              {/* Relevance Threshold */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>آستانه ارتباط (Relevance Threshold)</Label>
                  <span className="text-sm font-mono font-medium text-primary bg-accent px-2 py-0.5 rounded">
                    {settings.rag.relevanceThreshold.toFixed(2)}
                  </span>
                </div>
                <Slider
                  value={[settings.rag.relevanceThreshold]}
                  onValueChange={([v]) => updateRAG('relevanceThreshold', v)}
                  min={0}
                  max={0.5}
                  step={0.01}
                />
                <p className="text-xs text-muted-foreground">
                  کمترین امتیازی که یک چانک باید داشته باشد تا مرتبط در نظر گرفته شود
                </p>
              </div>

              {/* Semantic Chunking Toggle */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <Label>Semantic Chunking</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    تقسیم اسناد بر اساس تغییر معنا (LangChain) به‌جای اندازه ثابت کاراکتر
                  </p>
                </div>
                <Switch
                  checked={settings.rag.useSemanticChunking}
                  onCheckedChange={(v) => updateRAG('useSemanticChunking', v)}
                />
              </div>

              {/* Query Decomposition Toggle */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <Label>Query Decomposition</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    شکستن سوالات چندبخشی به زیرسوال‌های دقیق‌تر پیش از جستجو
                  </p>
                </div>
                <Switch
                  checked={settings.rag.useQueryDecomposition}
                  onCheckedChange={(v) => updateRAG('useQueryDecomposition', v)}
                />
              </div>

              {/* HyDE Toggle */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <Label>HyDE (پاسخ فرضی برای بازیابی)</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    تولید پاسخ فرضی توسط مدل زبانی برای تقویت جستجوی معنایی
                  </p>
                </div>
                <Switch
                  checked={settings.rag.useHyde}
                  onCheckedChange={(v) => updateRAG('useHyde', v)}
                />
              </div>

              {/* Cross-Encoder Rerank Toggle */}
              <div className="flex items-center justify-between py-1">
                <div>
                  <Label>Cross-Encoder Rerank (دقیق‌تر)</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    مرتب‌سازی مجدد نتایج با مدل cross-encoder (یا مدل زبانی در صورت نبود آن) — کندتر ولی دقیق‌تر
                  </p>
                </div>
                <Switch
                  checked={settings.rag.useCrossEncoderRerank}
                  onCheckedChange={(v) => updateRAG('useCrossEncoderRerank', v)}
                />
              </div>
            </CardContent>
          </Card>
        )}

        <Button onClick={handleSave} className="w-full" size="lg" disabled={saving}>
          {saving ? (
            <Loader2 className="w-4 h-4 ml-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 ml-2" />
          )}
          ذخیره تنظیمات
        </Button>

        <p className="text-[11px] text-muted-foreground text-center">
          ساخته شده توسط مهندس سارا افشار
        </p>
      </div>
    </div>
  );
}
