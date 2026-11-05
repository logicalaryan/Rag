/**
 * REST API Client for Production FastAPI Backend
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health`, { method: 'GET' });
    if (!res.ok) throw new Error('Health check failed');
    return await res.json();
  } catch (err) {
    return { status: 'offline', error: err.message };
  }
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/v1/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return await res.json();
}

export async function fetchDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/documents`);
    if (!res.ok) throw new Error('Fetch failed');
    return await res.json();
  } catch {
    return [];
  }
}
