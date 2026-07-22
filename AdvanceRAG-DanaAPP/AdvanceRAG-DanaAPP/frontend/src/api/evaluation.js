import { apiJson, apiFetch } from './client';

export async function listEvalItems() {
  return apiJson('/evaluation/items');
}

export async function createEvalItem(item) {
  return apiJson('/evaluation/items', {
    method: 'POST',
    body: JSON.stringify(item),
  });
}

export async function importEvalItems(items) {
  return apiJson('/evaluation/items/import', {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

export async function deleteEvalItem(itemId) {
  return apiFetch(`/evaluation/items/${itemId}`, { method: 'DELETE' });
}

export async function listEvalRuns() {
  return apiJson('/evaluation/runs');
}

export async function getEvalRun(runId) {
  return apiJson(`/evaluation/runs/${runId}`);
}

export async function deleteEvalRun(runId) {
  return apiFetch(`/evaluation/runs/${runId}`, { method: 'DELETE' });
}

export async function deleteAllEvalRuns() {
  return apiFetch('/evaluation/runs', { method: 'DELETE' });
}

export async function runEvaluation({ kValues, evaluateGeneration = true } = {}) {
  return apiJson('/evaluation/run', {
    method: 'POST',
    body: JSON.stringify({
      k_values: kValues || [1, 3, 5, 10],
      evaluate_generation: evaluateGeneration,
    }),
  });
}
