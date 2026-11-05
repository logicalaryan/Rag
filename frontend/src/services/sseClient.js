/**
 * Server-Sent Events (SSE) Client for real-time RAG streaming
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function streamChatResponse({ query, sessionId, chatHistory = '', onToken, onThinking, onCitations, onDone, onError }) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        chat_history: chatHistory,
      }),
    });

    if (!response.ok) {
      throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep remainder

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;

        const dataStr = trimmed.replace(/^data:\s*/, '');
        if (dataStr === '[DONE]') {
          if (onDone) onDone();
          return;
        }

        try {
          const payload = JSON.parse(dataStr);
          if (payload.type === 'token' && onToken) {
            onToken(payload.content);
          } else if (payload.type === 'thinking' && onThinking) {
            onThinking(payload.content);
          } else if (payload.type === 'citations' && onCitations) {
            onCitations(payload.sources);
          }
        } catch {
          if (onToken) onToken(dataStr);
        }
      }
    }

    if (onDone) onDone();
  } catch (err) {
    if (onError) onError(err);
  }
}
