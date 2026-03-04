'use client';

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import api from '@/lib/axios';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatPanelProps {
  fileId: string;
  fileType: string;
  userRole?: string;
}

const ChatPanel: React.FC<ChatPanelProps> = ({ fileId, fileType, userRole }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Set welcome message and suggestions based on file type and role
  useEffect(() => {
    const baseSuggestions = [
      'What is the total claim amount?',
      'List all patients',
      'Are there any errors?'
    ];

    if (fileType === '835') {
      setSuggestions([
        'How much was paid in total?',
        'Which claims were denied?',
        'Show me all adjustments'
      ]);
    } else if (fileType === '834') {
      setSuggestions([
        'List all members',
        'Who was added?',
        'Show effective dates'
      ]);
    } else {
      setSuggestions(baseSuggestions);
    }

    let roleHint = '';
    if (userRole === 'billing_specialist') {
      roleHint = ' You can ask about claim details, patient info, and charges.';
    } else if (userRole === 'benefits_admin') {
      roleHint = ' You can ask about member enrollment, coverage dates, and relationships.';
    }

    setMessages([{
      role: 'assistant',
      content: `👋 Hi! I'm your EDI assistant. Ask me anything about this **${fileType}** file.${roleHint}`,
      timestamp: new Date()
    }]);
  }, [fileType, userRole]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);
    const query = input;
    setInput('');
    setIsLoading(true);
    setStreamingMessage('');

    try {
      const response = await fetch(`http://localhost:8000/chat/${fileId}?query=${encodeURIComponent(query)}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Accept': 'text/event-stream',
        },
      });

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullMessage = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6);
            if (data === '[DONE]') {
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: fullMessage,
                timestamp: new Date()
              }]);
              setStreamingMessage('');
            } else if (data !== 'start') {
              fullMessage += data;
              setStreamingMessage(fullMessage);
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
      setStreamingMessage('');
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  return (
    <div className="flex flex-col h-[600px] border rounded-lg bg-white shadow-lg">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-3 rounded-t-lg flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <h3 className="font-semibold">AI Assistant</h3>
        </div>
        <span className="text-xs bg-blue-500 px-2 py-1 rounded-full">Streaming</span>
      </div>

      {/* Messages container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 shadow-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-white text-gray-800 rounded-bl-none border border-gray-200'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none text-sm">
                  <ReactMarkdown
                    components={{
                      strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              )}
              <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-400'}`}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}

        {/* Streaming message */}
        {streamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-[80%] bg-white text-gray-800 rounded-lg rounded-bl-none p-3 border border-gray-200 shadow-sm">
              <p className="text-sm whitespace-pre-wrap">{streamingMessage}</p>
              <span className="text-xs text-gray-400 animate-pulse">▊</span>
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && !streamingMessage && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg rounded-bl-none p-3 shadow-sm">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {suggestions.length > 0 && (
        <div className="px-4 py-2 border-t bg-gray-50">
          <p className="text-xs text-gray-500 mb-2">Suggested questions:</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((sugg, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestionClick(sugg)}
                className="text-xs bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 px-3 py-1 rounded-full transition-colors"
              >
                {sugg}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input form */}
      <form onSubmit={sendMessage} className="border-t p-3 flex gap-2 bg-white">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this file..."
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg disabled:opacity-50 transition-colors text-sm font-medium"
        >
          Send
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;