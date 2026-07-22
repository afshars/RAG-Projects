import { API_BASE } from './client';

// Streams a RAG chat response from the backend. Calls onCitations once
// (with the retrieved source chunks) and onToken for every streamed token.
export async function streamChat(messages, { onCitations, onToken, sessionId } = {}) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ messages, session_id: sessionId || null }),
  });

  if (!response.ok) {
    let detail = `خطای سرور (${response.status})`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data:')) continue;
      const data = trimmed.slice(5).trim();
      if (data === '[DONE]') return;

      try {
        const event = JSON.parse(data);
        if (event.type === 'citations') {
          onCitations?.(event.citations || [], event.confidence || null);
        } else if (event.type === 'token') {
          onToken?.(event.content);
        } else if (event.type === 'error') {
          throw new Error(event.message);
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue; // malformed chunk, skip
        throw e;
      }
    }
  }
}
