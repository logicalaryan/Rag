import React, { createContext, useContext, useState, useEffect } from 'react';
import { generateId } from '../utils/helpers';
import { streamChatResponse } from '../services/sseClient';
import { fetchDocuments, checkBackendHealth } from '../services/api';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const initialSessionId = generateId();
  const [sessions, setSessions] = useState([
    {
      id: initialSessionId,
      title: 'New Conversation',
      createdAt: new Date(),
      messages: [],
    },
  ]);
  const [activeSessionId, setActiveSessionId] = useState(initialSessionId);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'documents'
  const [isGenerating, setIsGenerating] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [systemOnline, setSystemOnline] = useState(false);

  // Poll backend health & fetch docs on mount
  useEffect(() => {
    checkBackendHealth().then((res) => {
      setSystemOnline(res.status === 'ok' || res.status === 'healthy');
    });

    fetchDocuments().then((docs) => {
      setDocuments(docs || []);
    });
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];

  function createNewSession() {
    const newId = generateId();
    const newSession = {
      id: newId,
      title: 'New Conversation',
      createdAt: new Date(),
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newId);
    setActiveTab('chat');
  }

  function selectSession(id) {
    setActiveSessionId(id);
    setActiveTab('chat');
  }

  async function sendMessage(text) {
    if (!text.trim() || isGenerating) return;

    const targetSessionId = activeSessionId;
    const historyBuffer = (activeSession?.messages || [])
      .slice(-6)
      .map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
      .join('\n');

    const userMsgId = generateId();
    const assistantMsgId = generateId();

    const userMessage = {
      id: userMsgId,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    const assistantPlaceholder = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      thinking: 'Router analyzing intent & rewriting query...',
      citations: [],
      timestamp: new Date(),
    };

    // Update session title on first message
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id === targetSessionId) {
          const isFirstMessage = session.messages.length === 0;
          return {
            ...session,
            title: isFirstMessage ? text.slice(0, 32) + (text.length > 32 ? '...' : '') : session.title,
            messages: [...session.messages, userMessage, assistantPlaceholder],
          };
        }
        return session;
      })
    );

    setIsGenerating(true);

    await streamChatResponse({
      query: text,
      sessionId: targetSessionId,
      chatHistory: historyBuffer,
      onToken: (token) => {
        setSessions((prev) =>
          prev.map((session) => {
            if (session.id === targetSessionId) {
              const updatedMessages = session.messages.map((msg) => {
                if (msg.id === assistantMsgId) {
                  return {
                    ...msg,
                    content: msg.content + token,
                    thinking: null,
                  };
                }
                return msg;
              });
              return { ...session, messages: updatedMessages };
            }
            return session;
          })
        );
      },
      onThinking: (thinkingText) => {
        setSessions((prev) =>
          prev.map((session) => {
            if (session.id === targetSessionId) {
              const updated = session.messages.map((m) =>
                m.id === assistantMsgId ? { ...m, thinking: thinkingText } : m
              );
              return { ...session, messages: updated };
            }
            return session;
          })
        );
      },
      onCitations: (sources) => {
        setSessions((prev) =>
          prev.map((session) => {
            if (session.id === targetSessionId) {
              const updated = session.messages.map((m) =>
                m.id === assistantMsgId ? { ...m, citations: sources } : m
              );
              return { ...session, messages: updated };
            }
            return session;
          })
        );
      },
      onDone: () => {
        setIsGenerating(false);
      },
      onError: (err) => {
        setSessions((prev) =>
          prev.map((session) => {
            if (session.id === targetSessionId) {
              const updated = session.messages.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: `Error: ${err.message}`, thinking: null }
                  : m
              );
              return { ...session, messages: updated };
            }
            return session;
          })
        );
        setIsGenerating(false);
      },
    });
  }

  function addDocument(doc) {
    setDocuments((prev) => [doc, ...prev]);
  }

  return (
    <ChatContext.Provider
      value={{
        sessions,
        activeSession,
        activeSessionId,
        activeTab,
        setActiveTab,
        isGenerating,
        documents,
        systemOnline,
        createNewSession,
        selectSession,
        sendMessage,
        addDocument,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
}
