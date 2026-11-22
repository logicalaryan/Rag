import React, { useState } from 'react';
import { useChatContext } from './context/ChatContext';
import { Sidebar } from './components/common/Sidebar';
import { Header } from './components/common/Header';
import { ChatContainer } from './components/chat/ChatContainer';
import { DocumentUpload } from './components/documents/DocumentUpload';
import { DocumentList } from './components/documents/DocumentList';

export function App() {
  const { activeTab } = useChatContext();
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="app-container">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <main className="main-content">
        <Header onMenu={() => setNavOpen(true)} />
        {activeTab === 'chat' ? (
          <ChatContainer />
        ) : (
          <div className="page-container">
            <h3 className="page-title">Knowledge Base</h3>
            <p className="page-subtitle">
              Files uploaded here are parsed, chunked, and embedded into the vector store for hybrid search.
            </p>
            <div className="doc-panel">
              <DocumentUpload />
              <h4 className="page-section-title">Indexed documents</h4>
              <DocumentList />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
