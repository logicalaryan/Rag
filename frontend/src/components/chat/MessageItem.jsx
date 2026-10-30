import React from 'react';
import { formatTimestamp } from '../../utils/helpers';

export function MessageItem({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-item ${isUser ? 'user' : 'assistant'}`}>
      <span className="message-role">
        {isUser ? 'User' : 'Assistant / Critic'}
      </span>

      <div className="message-bubble">
        {message.thinking && !message.content ? (
          <div className="thinking-indicator">
            <div className="spinner"></div>
            <span>{message.thinking}</span>
          </div>
        ) : (
          <div style={{ whiteSpace: 'pre-wrap' }}>
            {message.content}
          </div>
        )}

        {/* Citations section if present */}
        {message.citations && message.citations.length > 0 && (
          <div className="citations-container">
            {message.citations.map((cite, idx) => (
              <div key={idx} className="citation-chip">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span>{cite}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
