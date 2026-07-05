import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react';

// Types
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface Session {
  id: string;
  name: string;
  subject: string;
  messages: Message[];
  createdAt: number;
}

type Subject = '语文' | '数学' | '英语';

const SUBJECT_ICONS: Record<Subject, string> = {
  '语文': '📗',
  '数学': '📘',
  '英语': '📙',
};

function App() {
  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Session state
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);

  // Input state
  const [inputValue, setInputValue] = useState('');

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);


  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Current session
  const currentSession = sessions.find(s => s.id === currentSessionId) || null;

  // Auto scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentSession?.messages]);

  // ESC to close modal
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape' && modalOpen) {
        setModalOpen(false);
        setSelectedSubject(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalOpen]);

  // Create new session
  const createSession = useCallback((subject: Subject) => {
    const subjectCount = sessions.filter(s => s.subject === subject).length + 1;
    const newSession: Session = {
      id: `session-${Date.now()}`,
      name: `${subject} · 会话${subjectCount}`,
      subject,
      messages: [],
      createdAt: Date.now(),
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setInputValue('');
  }, [sessions]);

  // Delete session
  const deleteSession = useCallback((sessionId: string) => {
    setSessions(prev => {
      const newSessions = prev.filter(s => s.id !== sessionId);
      if (currentSessionId === sessionId) {
        setCurrentSessionId(newSessions.length > 0 ? newSessions[0].id : null);
      }
      return newSessions;
    });
  }, [currentSessionId]);

  // Send message to a specific session (SSE stream from backend)
  const sendMessageToSession = useCallback(async (sessionId: string, text: string, subject?: string) => {
    if (!text.trim() || isStreaming) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
    };

    // Create a placeholder assistant message
    const assistantMsgId = `msg-${Date.now()}-ai`;
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
    };

    // Add both user message and empty assistant message to session
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        return { ...s, messages: [...s.messages, userMessage, assistantMessage] };
      }
      return s;
    }));

    setIsStreaming(true);

    try {
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, subject: subject || null }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        // Parse SSE lines: "data: {...}\n\n"
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.done) {
                break;
              }
              if (data.content) {
                accumulated += data.content;
                setSessions(prev => prev.map(s => {
                  if (s.id === sessionId) {
                    return {
                      ...s,
                      messages: s.messages.map(m =>
                        m.id === assistantMsgId ? { ...m, content: accumulated } : m
                      ),
                    };
                  }
                  return s;
                }));
              }
            } catch {
              // Skip malformed JSON lines
            }
          }
        }
      }
    } catch {
      setSessions(prev => prev.map(s => {
        if (s.id === sessionId) {
          return {
            ...s,
            messages: s.messages.map(m =>
              m.id === assistantMsgId
                ? { ...m, content: '⚠️ 后端连接失败，请确认后端服务已启动（端口 8000）。' }
                : m
            ),
          };
        }
        return s;
      }));
    } finally {
      setIsStreaming(false);
    }
  }, [isStreaming]);

  // Send message (uses current session)
  const sendMessage = useCallback(() => {
    if (!inputValue.trim() || !currentSessionId) return;
    const text = inputValue.trim();
    setInputValue('');
    sendMessageToSession(currentSessionId, text, currentSession?.subject);
  }, [inputValue, currentSessionId, currentSession?.subject, sendMessageToSession]);

  // Handle input key down
  const handleInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      sendMessage();
    }
  };

  // Handle modal confirm
  const handleModalConfirm = () => {
    if (selectedSubject) {
      createSession(selectedSubject);
      setModalOpen(false);
      setSelectedSubject(null);
    }
  };

  // Handle input area send (for empty state centered input)
  const handleEmptyStateSend = () => {
    if (!inputValue.trim()) return;
    const text = inputValue.trim();
    setInputValue('');

    if (!currentSessionId) {
      // Auto create a session with default subject, then send message
      const subject: Subject = '语文';
      const subjectCount = sessions.filter(s => s.subject === subject).length + 1;
      const newSession: Session = {
        id: `session-${Date.now()}`,
        name: `${subject} · 会话${subjectCount}`,
        subject,
        messages: [],
        createdAt: Date.now(),
      };
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      // Send message directly with the new session ID (no timing issue)
      sendMessageToSession(newSession.id, text, subject);
    } else {
      sendMessageToSession(currentSessionId, text, currentSession?.subject);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className="flex flex-col h-full border-r flex-shrink-0 transition-all duration-300"
        style={{
          width: sidebarCollapsed ? 60 : 260,
          background: 'var(--bg-card)',
          borderColor: 'var(--border)',
          padding: sidebarCollapsed ? '16px 8px' : '16px 12px',
        }}
      >
        {/* Sidebar Header */}
        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="flex items-center justify-center rounded-lg hover:opacity-80 transition"
            style={{
              width: 36,
              height: 36,
              background: 'transparent',
              border: '1px solid var(--border)',
              color: 'var(--text-m)',
              fontSize: 18,
              cursor: 'pointer',
              flexShrink: 0,
            }}
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            ☰
          </button>
        </div>

        {/* New Chat Button - below header, above history */}
        {!sidebarCollapsed && (
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center justify-center gap-1 rounded-lg text-white font-medium transition hover:opacity-90"
            style={{
              height: 40,
              background: 'var(--accent)',
              border: 'none',
              fontSize: 14,
              cursor: 'pointer',
              padding: '8px 16px',
              marginBottom: 12,
            }}
          >
            ＋ 新对话
          </button>
        )}
        {sidebarCollapsed && (
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center justify-center rounded-lg text-white font-medium transition hover:opacity-90 mx-auto"
            style={{
              width: 36,
              height: 36,
              background: 'var(--accent)',
              border: 'none',
              fontSize: 18,
              cursor: 'pointer',
              marginBottom: 12,
            }}
            title="新对话"
          >
            ＋
          </button>
        )}

        {/* History List */}
        {!sidebarCollapsed && (
          <>
            <div
              className="mb-2 font-medium"
              style={{ fontSize: 12, color: 'var(--text-light)', margin: '20px 0 8px' }}
            >
              历史对话
            </div>
            <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
              {sessions.length === 0 && (
                <div
                  className="text-center py-4"
                  style={{ fontSize: 13, color: 'var(--text-light)' }}
                >
                  暂无对话记录
                </div>
              )}
              {sessions.map(session => (
                <div
                  key={session.id}
                  className="group flex items-center rounded-md cursor-pointer transition relative"
                  style={{
                    padding: '8px 12px',
                    marginBottom: 4,
                    background: currentSessionId === session.id ? 'var(--accent-bg)' : 'transparent',
                    borderLeft: currentSessionId === session.id ? '3px solid var(--accent)' : '3px solid transparent',
                    fontSize: 14,
                    color: 'var(--text-m)',
                  }}
                  onClick={() => setCurrentSessionId(session.id)}
                  onMouseEnter={e => {
                    if (currentSessionId !== session.id) {
                      (e.currentTarget as HTMLDivElement).style.background = 'var(--social-bg)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (currentSessionId !== session.id) {
                      (e.currentTarget as HTMLDivElement).style.background = 'transparent';
                    }
                  }}
                >
                  <span className="flex-1 truncate">{session.name}</span>
                  <button
                    className="opacity-0 group-hover:opacity-100 transition ml-1 flex items-center justify-center rounded-full hover:bg-red-100"
                    style={{
                      width: 20,
                      height: 20,
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--text-light)',
                      fontSize: 14,
                      cursor: 'pointer',
                      flexShrink: 0,
                    }}
                    onClick={e => {
                      e.stopPropagation();
                      deleteSession(session.id);
                    }}
                    title="删除对话"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {sidebarCollapsed && <div className="flex-1" />}


        {/* Sidebar Footer */}
        <div
          className="flex items-center gap-3"
          style={{
            paddingTop: 16,
            borderTop: '1px solid var(--border)',
            justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
          }}
        >
          <img
            src="/defaultuser.png"
            alt="avatar"
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              objectFit: 'cover',
              flexShrink: 0,
            }}
          />
          {!sidebarCollapsed && (
            <span style={{ fontSize: 14, color: 'var(--text-h)', fontWeight: 500 }}>
              User
            </span>
          )}
        </div>
      </aside>

      {/* Main Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden" style={{ background: '#ffffff' }}>
        {!currentSession || currentSession.messages.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center" style={{ padding: '40px 20px', gap: 24 }}>
            <img
              src="/StudyAgent.png"
              alt="Study Agent"
              className="animate-image-fade"
              style={{
                width: 200,
                height: 'auto',
                borderRadius: 16,
                boxShadow: 'var(--shadow)',
              }}
            />
            <h1
              style={{
                fontSize: 28,
                fontWeight: 600,
                color: 'var(--text-h)',
                textAlign: 'center',
              }}
            >
              今天想学什么？
            </h1>

            {/* Centered Input Bar */}
            <div
              className="flex items-center"
              style={{
                width: 'min(640px, 90%)',
                height: 56,
                background: '#ffffff',
                border: '2px solid var(--border)',
                borderRadius: 28,
                padding: '4px 4px 4px 20px',
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleEmptyStateSend();
                  }
                }}
                placeholder="输入你的问题..."
                style={{
                  flex: 1,
                  border: 'none',
                  outline: 'none',
                  fontSize: 16,
                  color: 'var(--text-h)',
                  background: 'transparent',
                }}
              />
              <button
                onClick={handleEmptyStateSend}
                disabled={!inputValue.trim()}
                className="flex items-center justify-center transition hover:scale-105"
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: 20,
                  cursor: inputValue.trim() ? 'pointer' : 'default',
                  opacity: inputValue.trim() ? 1 : 0.4,
                  flexShrink: 0,
                }}
              >
                ➤
              </button>
            </div>

            {/* New Subject Button */}
            <button
              onClick={() => setModalOpen(true)}
              className="transition"
              style={{
                background: 'transparent',
                border: '2px dashed var(--border)',
                borderRadius: 12,
                padding: '10px 24px',
                fontSize: 15,
                color: 'var(--text-m)',
                cursor: 'pointer',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--accent)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-m)';
              }}
            >
              📖 学习新科目
            </button>

            {/* Recent Session Tags */}
            {sessions.length > 0 && (
              <div className="flex flex-wrap gap-2 justify-center" style={{ marginTop: 8 }}>
                {sessions.slice(0, 5).map(session => (
                  <button
                    key={session.id}
                    onClick={() => setCurrentSessionId(session.id)}
                    className="transition hover:opacity-80"
                    style={{
                      padding: '4px 12px',
                      borderRadius: 16,
                      background: 'var(--social-bg)',
                      border: 'none',
                      fontSize: 13,
                      color: 'var(--text-m)',
                      cursor: 'pointer',
                    }}
                  >
                    {session.subject}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Chat State */
          <>
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto" style={{ padding: '24px 20px' }}>
              <div style={{ maxWidth: 800, margin: '0 auto' }}>
                {currentSession.messages.map(msg => (
                  <div
                    key={msg.id}
                    className="flex"
                    style={{
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      marginBottom: 16,
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '80%',
                        padding: '10px 16px',
                        borderRadius: msg.role === 'user'
                          ? '16px 16px 4px 16px'
                          : '16px 16px 16px 4px',
                        background: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-card)',
                        color: msg.role === 'user' ? '#ffffff' : 'var(--text-h)',
                        fontSize: 15,
                        lineHeight: 1.6,
                        wordBreak: 'break-word',
                      }}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input Footer */}
            <div
              style={{
                padding: '16px 20px',
                borderTop: '1px solid var(--border)',
                background: 'rgba(255, 255, 255, 0.9)',
                backdropFilter: 'blur(12px)',
              }}
            >
              <div
                className="flex items-center"
                style={{
                  maxWidth: 800,
                  margin: '0 auto',
                  height: 56,
                  background: '#ffffff',
                  border: '2px solid var(--border)',
                  borderRadius: 28,
                  padding: '4px 4px 4px 20px',
                }}
              >
                <input
                  type="text"
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={handleInputKeyDown}
                  placeholder="输入你的问题..."
                  style={{
                    flex: 1,
                    border: 'none',
                    outline: 'none',
                    fontSize: 16,
                    color: 'var(--text-h)',
                    background: 'transparent',
                  }}
                />
                <button
                  onClick={sendMessage}
                  disabled={!inputValue.trim()}
                  className="flex items-center justify-center transition hover:scale-105"
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: '50%',
                    background: 'var(--accent)',
                    color: '#ffffff',
                    border: 'none',
                    fontSize: 20,
                    cursor: inputValue.trim() ? 'pointer' : 'default',
                    opacity: inputValue.trim() ? 1 : 0.4,
                    flexShrink: 0,
                  }}
                >
                  ➤
                </button>
              </div>
            </div>
          </>
        )}
      </main>

      {/* Subject Modal */}
      {modalOpen && (
        <>
          {/* Overlay */}
          <div
            className="animate-fade-in"
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0, 0, 0, 0.4)',
              zIndex: 1000,
            }}
            onClick={() => {
              setModalOpen(false);
              setSelectedSubject(null);
            }}
          />

          {/* Modal Card */}
          <div
            className="animate-scale-up"
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: '#ffffff',
              borderRadius: 20,
              padding: '40px 48px 32px',
              maxWidth: 420,
              width: '90%',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.2)',
              zIndex: 1001,
            }}
          >
            <h2
              style={{
                fontSize: 22,
                fontWeight: 600,
                color: 'var(--text-h)',
                textAlign: 'center',
                marginBottom: 24,
              }}
            >
              选择科目
            </h2>

            {/* Subject Options */}
            <div className="flex gap-3 justify-center">
              {(Object.keys(SUBJECT_ICONS) as Subject[]).map(subject => (
                <button
                  key={subject}
                  onClick={() => setSelectedSubject(subject)}
                  className="flex flex-col items-center justify-center transition"
                  style={{
                    flex: 1,
                    padding: '16px 0',
                    borderRadius: 12,
                    background: selectedSubject === subject ? 'var(--accent-bg)' : 'var(--social-bg)',
                    border: selectedSubject === subject
                      ? '2px solid var(--accent)'
                      : '2px solid transparent',
                    cursor: 'pointer',
                    fontSize: 18,
                    fontWeight: 500,
                    color: 'var(--text-h)',
                  }}
                  onMouseEnter={e => {
                    if (selectedSubject !== subject) {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--accent-border)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (selectedSubject !== subject) {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
                    }
                  }}
                >
                  <span style={{ fontSize: 28, marginBottom: 4 }}>{SUBJECT_ICONS[subject]}</span>
                  <span>{subject}</span>
                </button>
              ))}
            </div>

            {/* Confirm Button */}
            <button
              onClick={handleModalConfirm}
              disabled={!selectedSubject}
              className="w-full transition hover:opacity-85"
              style={{
                marginTop: 24,
                padding: 14,
                borderRadius: 12,
                background: 'var(--accent)',
                color: '#ffffff',
                border: 'none',
                fontSize: 17,
                fontWeight: 500,
                cursor: selectedSubject ? 'pointer' : 'not-allowed',
                opacity: selectedSubject ? 1 : 0.4,
              }}
            >
              确定
            </button>
          </div>
        </>
      )}

    </div>
  );
}

export default App;
