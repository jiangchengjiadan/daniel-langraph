import React from 'react';
import { ChatWindow } from './components/ChatWindow';

function App() {
  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg-primary)'
    }}>
      {/* 顶部标题栏 */}
      <header style={{
        padding: '16px 24px',
        background: 'linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%)',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        {/* 状态指示灯 */}
        <div style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          background: 'var(--success)',
          boxShadow: '0 0 10px var(--success)',
          animation: 'pulse 2s infinite'
        }} />

        {/* 标题 */}
        <div>
          <h1 style={{
            fontSize: '18px',
            fontWeight: '700',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '1px',
            color: 'var(--accent-primary)'
          }}>
            INDUSTRIAL RAG AGENT
          </h1>
          <p style={{
            fontSize: '12px',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)'
          }}>
            工业设备售后智能客服系统
          </p>
        </div>
      </header>

      {/* 主聊天区域 */}
      <ChatWindow />
    </div>
  );
}

export default App;
