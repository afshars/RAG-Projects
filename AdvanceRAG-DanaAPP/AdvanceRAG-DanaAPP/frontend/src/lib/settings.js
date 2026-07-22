import { getSettings, updateSettings } from '@/api/settings';

export const DEFAULT_SETTINGS = {
  llm: {
    baseUrl: 'https://api.gapgpt.app/v1',
    model: 'gapgpt-qwen-3.6',
    apiKey: '',
    embeddingModel: 'text-embedding-3-small',
  },
  vision: {
    baseUrl: '',
    model: '',
    apiKey: '',
  },
  rag: {
    chunkSize: 800,
    chunkOverlap: 150,
    hybridAlpha: 0.6,
    mmrLambda: 0.7,
    topK: 5,
    useCrossEncoderRerank: true,
    relevanceThreshold: 0.08,
    useSemanticChunking: true,
    useQueryDecomposition: true,
    useHyde: true,
    fusionMethod: 'rrf',
    rrfK: 60,
  },
};

// Preset models shown in Settings — the user can still type any other
// model name into the "custom" option.
export const MODEL_PRESETS = [
  'gapgpt-qwen-3.6',
  'gapgpt-qwen-3.6-thinking',
  'gemini-3.1-flash-lite',
  'gemini-3-flash-preview',
  'grok-4.3',
];

// Settings now live server-side (per-user), fetched/saved through the RAG
// backend's /settings endpoint instead of localStorage.
export async function loadSettings() {
  try {
    return await getSettings();
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(settings) {
  return updateSettings(settings);
}
