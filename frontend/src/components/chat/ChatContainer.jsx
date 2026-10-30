import React from 'react';
import { useChat } from '../../hooks/useChat';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export function ChatContainer() {
  const { messages } = useChat();

  return (
    <div className="chat-container">
      <MessageList messages={messages} />
      <ChatInput />
    </div>
  );
}
