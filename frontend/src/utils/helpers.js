/**
 * Utility helper functions for Frontend Client
 */

export function generateId() {
  return 'id_' + Math.random().toString(36).substring(2, 9) + Date.now().toString(36);
}

export function formatTimestamp(date = new Date()) {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: 'numeric',
    hour12: true,
  }).format(date);
}

export function extractCitations(text) {
  if (!text) return { cleanText: '', citations: [] };

  // Match pattern like [Doc: filename.pdf | Page 2] or [Source: ...]
  const citationRegex = /\[(Source|Doc|Citation):\s*([^\]]+)\]/gi;
  const citations = [];
  let match;

  while ((match = citationRegex.exec(text)) !== null) {
    if (!citations.includes(match[2].trim())) {
      citations.push(match[2].trim());
    }
  }

  return {
    cleanText: text.replace(citationRegex, '').trim(),
    citations,
  };
}
