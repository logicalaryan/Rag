import { useChatContext } from '../context/ChatContext';

export function useChat() {
  const {
    activeSession,
    activeSessionId,
    sessions,
    isGenerating,
    sendMessage,
    createNewSession,
    selectSession,
  } = useChatContext();

  return {
    messages: activeSession?.messages || [],
    sessionTitle: activeSession?.title || 'New Conversation',
    activeSessionId,
    sessions,
    isGenerating,
    sendMessage,
    createNewSession,
    selectSession,
  };
}
