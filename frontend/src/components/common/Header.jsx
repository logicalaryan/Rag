import React from 'react';
import { useChatContext } from '../../context/ChatContext';

export function Header({ onMenu }) {
  const { activeSession, activeTab, systemOnline } = useChatContext();
  const title = activeTab === 'documents' ? 'Knowledge Base' : activeSession?.title || 'Agentic RAG';

  return (
    <header className="header">
      <div className="header-left">
        <button className="menu-button" onClick={onMenu} aria-label="Open navigation">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h2 className="header-title">{title}</h2>
      </div>
      <div className="header-badges">
        <div className="badge">
          <span className={`status-dot ${systemOnline ? '' : 'offline'}`}></span>
          {systemOnline ? 'Connected' : 'Offline'}
        </div>
      </div>
    </header>
  );
}
