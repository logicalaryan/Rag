import React from 'react';
import { useDocuments } from '../../hooks/useDocuments';

export function DocumentList() {
  const { documents } = useDocuments();

  if (!documents || documents.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', padding: '20px 0' }}>
        No documents indexed yet. Upload a document above.
      </div>
    );
  }

  return (
    <div className="doc-list">
      {documents.map((doc) => (
        <div key={doc.id} className="doc-item">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span className="doc-name">{doc.filename}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{doc.size || 'Auto'}</span>
            <span className={`doc-status ${doc.status === 'ready' || doc.status === 'indexed' ? 'ready' : 'indexing'}`}>
              {doc.status || 'ready'}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
