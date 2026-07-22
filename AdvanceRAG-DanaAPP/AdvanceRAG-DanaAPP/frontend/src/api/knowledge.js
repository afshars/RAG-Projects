import { apiJson, apiFetch } from './client';

export async function listChunks() {
  return apiJson('/knowledge');
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return apiJson('/knowledge/upload', { method: 'POST', body: formData });
}

export async function ingestUrl(url) {
  return apiJson('/knowledge/url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export async function deleteDocument(documentId) {
  return apiFetch(`/knowledge/document/${documentId}`, { method: 'DELETE' });
}

export async function deleteAllDocuments() {
  return apiFetch('/knowledge/all', { method: 'DELETE' });
}
