import React from 'react';
import { useChatContext } from '../../context/ChatContext';

export function Sidebar() {
  const {
    sessions,
    activeSessionId,
    selectSession,
    createNewSession,
    activeTab,
    setActiveTab,
    systemOnline,
    documents,
  } = useChatContext();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-logo">RAG</div>
          <div>
            <div className="brand-title">Enterprise</div>
          </div>
        </div>
        <span className="brand-badge">v6.0</span>
      </div>

      <div style={{ padding: '0 16px' }}>
        <button className="sidebar-action-btn" onClick={createNewSession}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New Chat
        </button>
      </div>

      <div className="sidebar-nav">
        <button
          className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Conversations ({sessions.length})
        </button>
        <button
          className={`nav-tab ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          Knowledge ({documents.length})
        </button>
      </div>

      <div className="sidebar-content">
        {activeTab === 'chat' ? (
          <div>
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                onClick={() => selectSession(session.id)}
              >
                <span className="session-title">{session.title}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
            Browse and upload PDF / TXT / Markdown files using the Knowledge tab.
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <div className="system-status">
          <div className="status-dot"></div>
          <span>{systemOnline ? 'Cluster Active' : 'Ready'}</span>
        </div>
        <span>Decoupled API</span>
      </div>
    </aside>
  );
}
