import { apiJson } from './client';

// Maps backend snake_case <-> frontend camelCase shape used by Settings.jsx / Home.jsx.
export function toFrontend(s) {
  return {
    llm: {
      baseUrl: s.llm_base_url,
      model: s.llm_model,
      apiKey: s.llm_api_key,
      embeddingModel: s.embedding_model,
    },
    vision: {
      baseUrl: s.vision_llm_base_url,
      model: s.vision_llm_model,
      apiKey: s.vision_llm_api_key,
    },
    rag: {
      chunkSize: s.chunk_size,
      chunkOverlap: s.chunk_overlap,
      hybridAlpha: s.hybrid_alpha,
      mmrLambda: s.mmr_lambda,
      topK: s.top_k,
      useCrossEncoderRerank: s.use_cross_encoder_rerank,
      relevanceThreshold: s.relevance_threshold,
      useSemanticChunking: s.use_semantic_chunking,
      useQueryDecomposition: s.use_query_decomposition,
      useHyde: s.use_hyde,
      fusionMethod: s.fusion_method,
      rrfK: s.rrf_k,
    },
  };
}

export function toBackend(settings) {
  return {
    llm_base_url: settings.llm.baseUrl,
    llm_model: settings.llm.model,
    llm_api_key: settings.llm.apiKey,
    embedding_model: settings.llm.embeddingModel,
    vision_llm_base_url: settings.vision.baseUrl,
    vision_llm_model: settings.vision.model,
    vision_llm_api_key: settings.vision.apiKey,
    chunk_size: settings.rag.chunkSize,
    chunk_overlap: settings.rag.chunkOverlap,
    hybrid_alpha: settings.rag.hybridAlpha,
    mmr_lambda: settings.rag.mmrLambda,
    top_k: settings.rag.topK,
    use_cross_encoder_rerank: settings.rag.useCrossEncoderRerank,
    relevance_threshold: settings.rag.relevanceThreshold,
    use_semantic_chunking: settings.rag.useSemanticChunking,
    use_query_decomposition: settings.rag.useQueryDecomposition,
    use_hyde: settings.rag.useHyde,
    fusion_method: settings.rag.fusionMethod,
    rrf_k: settings.rag.rrfK,
  };
}

export async function getSettings() {
  const data = await apiJson('/settings');
  return toFrontend(data);
}

export async function updateSettings(settings) {
  const data = await apiJson('/settings', {
    method: 'PATCH',
    body: JSON.stringify(toBackend(settings)),
  });
  return toFrontend(data);
}
