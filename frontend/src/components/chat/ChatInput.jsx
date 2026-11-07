import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../../hooks/useChat';

export function ChatInput() {
  const [text, setText] = useState('');
  const { sendMessage, isGenerating } = useChat();
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleSubmit() {
    if (!text.trim() || isGenerating) return;
    sendMessage(text);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-box">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder="Ask a question about your knowledge base... (Enter to send)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isGenerating}
        />
        <button
          className="send-button"
          onClick={handleSubmit}
          disabled={!text.trim() || isGenerating}
          aria-label="Send message"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      <div className="input-hint">
        Markdown supported &bull; Hybrid Dense + BM25 &bull; Critic Guardrails active
      </div>
    </div>
  );
}
