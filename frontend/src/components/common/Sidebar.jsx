import React from 'react';
import { useChatContext } from '../../context/ChatContext';

export function Sidebar({ open, onClose }) {
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

  function go(fn) {
    return (...args) => {
      fn(...args);
      onClose();
    };
  }

  return (
    <>
      <div className={`sidebar-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-logo">RAG</div>
            <div className="brand-title">Enterprise</div>
          </div>
          <span className="brand-badge">v5.0</span>
        </div>

        <div className="sidebar-top">
          <button className="sidebar-action-btn" onClick={go(createNewSession)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            New Chat
          </button>

          <nav className="sidebar-nav">
            <button
              className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={go(() => setActiveTab('chat'))}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <span className="nav-label">Conversations</span>
              <span className="nav-count">{sessions.length}</span>
            </button>
            <button
              className={`nav-item ${activeTab === 'documents' ? 'active' : ''}`}
              onClick={go(() => setActiveTab('documents'))}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
              </svg>
              <span className="nav-label">Knowledge Base</span>
              <span className="nav-count">{documents.length}</span>
            </button>
          </nav>
        </div>

        <div className="sidebar-section-label">Recent</div>
        <div className="sidebar-content">
          {sessions.map((session) => (
            <div
              key={session.id}
              role="button"
              tabIndex={0}
              className={`session-item ${session.id === activeSessionId && activeTab === 'chat' ? 'active' : ''}`}
              onClick={go(() => selectSession(session.id))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  go(() => selectSession(session.id))();
                }
              }}
            >
              <span className="session-title">{session.title}</span>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="system-status">
            <div className={`status-dot ${systemOnline ? '' : 'offline'}`}></div>
            <span>{systemOnline ? 'Cluster Active' : 'Connecting'}</span>
          </div>
          <span>Decoupled API</span>
        </div>
      </aside>
    </>
  );
}
