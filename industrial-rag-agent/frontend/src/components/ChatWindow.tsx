import React, { useState, useRef, useEffect, useCallback } from 'react';
import MarkdownIt from 'markdown-it';
import 'github-markdown-css/github-markdown.css';
import './ChatWindow.css';

// 初始化 markdown-it
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true, // 关键：开启单换行解释为 <br>
});

// 处理markdown内容，强制在标题和列表符号前后添加必要的换行和空格
const processMarkdown = (content: string): string => {
  let processed = content;

  // 1. 补全未闭合的代码块
  const codeBlockCount = (processed.match(/```/g) || []).length;
  if (codeBlockCount % 2 !== 0) {
    processed += '\n\n```';
  }

  // 2. 修正标题：只有当 ### 前面没有换行，且后面有空格时才补换行
  // 避免匹配到文本中间的 # 字符
  processed = processed.replace(/([^\n])(#{1,6}\s+)/g, '$1\n$2');

  // 3. 修正无序列表：只有当 - 或 * 后面有空格，且前面紧跟标点符号时才换行
  // 这样可以避免拆散加粗语法 **bold** 和单词间的连字符
  processed = processed.replace(/([。！？：；])([-*]\s+)/g, '$1\n$2');

  // 4. 修正有序列表：只有当 数字. 后面有空格，且前面紧跟标点符号时才换行
  processed = processed.replace(/([。！？：；])(\d+\.\s+)/g, '$1\n$2');

  return processed;
};

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: '您好！我是工业设备售后智能客服助手。请问有什么关于电机、变频器等设备的问题我可以帮您解答？',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [threadId] = useState(() => `thread_${Date.now()}`);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 使用 useMemo 避免重复渲染，仅在内容变化时重新解析
  const renderMarkdown = useCallback((content: string) => {
    const processedContent = processMarkdown(content);
    return { __html: md.render(processedContent) };
  }, []);

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 流式发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    // 创建 AbortController 用于取消请求
    abortControllerRef.current = new AbortController();

    // 创建 Assistant 消息占位
    const assistantMessageId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant' as const,
      content: '',
      timestamp: new Date()
    }]);

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage.content,
          thread_id: threadId
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取响应流');
      }

      const decoder = new TextDecoder();
      let assistantContent = '';
      let leftover = ''; // 处理跨块截断问题

      // 读取流式响应
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 将缓冲区内容与新块合并，处理跨块截断问题
        const chunk = decoder.decode(value, { stream: true });
        const lines = (leftover + chunk).split('\n');
        leftover = lines.pop() || ''; // 最后一行可能不完整，留到下一轮处理

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine || trimmedLine === 'data: [DONE]') continue;

          if (line.startsWith('data: ')) {
            // 修复：不要使用 slice(6) 后再处理空格，
            // 直接使用正则移除开头的 "data: " 标记，保留 AI 返回的所有原始空格
            const data = line.replace(/^data: ?/, '');

            if (data === '[DONE]') break;

            assistantContent += data;

            // 更新消息内容
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, content: assistantContent }
                : msg
            ));
          }
        }
      }

      // 处理最后可能残留的换行
      if (leftover.trim()) {
        assistantContent += leftover;
      }

      // 完成响应后更新消息
      setMessages(prev => prev.map(msg =>
        msg.id === assistantMessageId
          ? { ...msg, content: assistantContent || '抱歉，未能获取有效响应。' }
          : msg
      ));

    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('请求已取消');
        setMessages(prev => prev.filter(msg => msg.id !== assistantMessageId));
      } else {
        console.error('发送消息失败:', error);
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: '抱歉，处理您的请求时出现了问题。请稍后重试或拨打客服热线获得人工支持。' }
            : msg
        ));
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  // 处理回车发送
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 取消当前请求
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return (
    <div className="chat-container">
      {/* 消息列表区域 */}
      <div className="messages-area">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message-wrapper ${message.role}`}
          >
            {/* 角色图标 */}
            <div className="message-avatar">
              {message.role === 'assistant' ? (
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
              )}
            </div>

            {/* 消息内容 */}
            <div className="message-content">
              <div className="message-header">
                <span className="message-role">
                  {message.role === 'assistant' ? '智能客服' : '您'}
                </span>
                <span className="message-time">
                  {message.timestamp.toLocaleTimeString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
                {message.role === 'assistant' && isLoading && message.content === '' && (
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                )}
              </div>
              {message.content ? (
                <div
                  className="message-bubble markdown-body"
                  dangerouslySetInnerHTML={renderMarkdown(message.content)}
                />
              ) : (
                <div className="message-bubble loading-text">
                  正在生成回复...
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="input-area">
        <div className="input-container">
          <textarea
            className="message-input"
            placeholder="输入您的问题..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isLoading}
          />
          {isLoading ? (
            <button
              className="send-button cancel-button-inline"
              onClick={handleCancel}
              title="取消生成"
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 6h12v12H6z"/>
              </svg>
            </button>
          ) : (
            <button
              className="send-button"
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
            >
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
              </svg>
            </button>
          )}
        </div>
        <div className="input-hint">
          按 Enter 发送，Shift+Enter 换行
        </div>
      </div>

      {/* 底部状态栏 */}
      <div className="status-bar">
        <div className="status-item">
          <span className="status-dot online"></span>
          <span>在线服务</span>
        </div>
        <div className="status-item">
          <span className="status-label">会话ID:</span>
          <span className="status-value">{threadId.slice(0, 12)}...</span>
        </div>
      </div>
    </div>
  );
};
