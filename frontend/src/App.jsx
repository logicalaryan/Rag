import React from 'react';
import { useChatContext } from './context/ChatContext';
import { Sidebar } from './components/common/Sidebar';
import { Header } from './components/common/Header';
import { ChatContainer } from './components/chat/ChatContainer';
import { DocumentUpload } from './components/documents/DocumentUpload';
import { DocumentList } from './components/documents/DocumentList';

export function App() {
  const { activeTab } = useChatContext();

  return (
    <div className="app-container">
      <Sidebar />
      <main className="main-content">
        <Header />
        {activeTab === 'chat' ? (
          <ChatContainer />
        ) : (
          <div style={{ maxWidth: '800px', width: '100%', margin: '0 auto', padding: '32px 24px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
              Knowledge Base Ingestion
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: '24px' }}>
              Files uploaded here are parsed, chunked, and embedded into the vector store for hybrid search.
            </p>
            <div className="doc-panel">
              <DocumentUpload />
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                  Indexed Documents
                </h4>
                <DocumentList />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
