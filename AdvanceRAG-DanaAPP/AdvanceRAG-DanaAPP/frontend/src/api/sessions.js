import { apiJson, apiFetch } from './client';

export async function listSessions() {
  return apiJson('/chat/sessions');
}

export async function createSession(title) {
  return apiJson('/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ title: title || null }),
  });
}

export async function getSession(sessionId) {
  return apiJson(`/chat/sessions/${sessionId}`);
}

export async function renameSession(sessionId, title) {
  return apiJson(`/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
}

export async function deleteSession(sessionId) {
  return apiFetch(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function listFeedback(sessionId) {
  return apiJson(`/chat/sessions/${sessionId}/feedback`);
}

export async function setFeedback(sessionId, messageIndex, rating, comment, detailed) {
  // detailed: optional { usefulness, correctness, completeness } (each 1-5).
  // Left as null/undefined fields, the backend keeps whatever was already
  // stored for those — so quick 👍/👎 and the detailed rating panel can be
  // submitted independently without overwriting each other.
  return apiJson(`/chat/sessions/${sessionId}/messages/${messageIndex}/feedback`, {
    method: 'PUT',
    body: JSON.stringify({
      rating,
      comment: comment || null,
      usefulness: detailed?.usefulness ?? null,
      correctness: detailed?.correctness ?? null,
      completeness: detailed?.completeness ?? null,
    }),
  });
}

export async function clearFeedback(sessionId, messageIndex) {
  return apiFetch(`/chat/sessions/${sessionId}/messages/${messageIndex}/feedback`, {
    method: 'DELETE',
  });
}
