import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => 'session_' + Date.now().toString(36))
  const [modelProvider, setModelProvider] = useState('deepseek')
  const [isDark, setIsDark] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const apiBase = import.meta.env.VITE_API_URL || ''
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId, model_provider: modelProvider }),
      })

      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }])
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `请求失败：${e.message}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className={`flex flex-col h-dvh ${isDark ? "bg-gray-950 text-gray-100" : "bg-white text-gray-800"}`}>
      {/* 顶栏 */}
      <header className={`shrink-0 border-b px-4 py-3 ${isDark ? "border-gray-800" : "border-gray-200"}`}>
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <h1 className={`text-lg font-semibold ${isDark ? "text-gray-100" : "text-gray-800"}`}>
            AI Agent
          </h1>
          <div className="flex items-center gap-2">
            <select
              value={modelProvider}
              onChange={(e) => setModelProvider(e.target.value)}
              className={`text-xs rounded px-2 py-1 cursor-pointer ${isDark ? "bg-gray-800 text-gray-200 border-gray-600" : "bg-gray-100 text-gray-700 border-gray-300"} border`}
            >
              <option value="deepseek">DeepSeek</option>
              <option value="glm">智谱 GLM</option>
              <option value="qwen">通义千问</option>
              <option value="yi">零一万物</option>
            </select>
            <button
              onClick={() => setIsDark(!isDark)}
              className={`text-xs px-2 py-1 rounded transition cursor-pointer ${isDark ? "text-yellow-400 hover:text-yellow-300" : "text-gray-400 hover:text-gray-600"}`}
              title={isDark ? "切换到浅色" : "切换到深色"}
            >
              {isDark ? "☀️" : "🌙"}
            </button>
            <span className="text-xs text-gray-400 font-mono">
              {sessionId.slice(0, 12)}
            </span>
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                className="text-xs text-gray-400 hover:text-red-500 transition cursor-pointer"
                title="清空对话"
              >
                清空
              </button>
            )}
          </div>
        </div>
      </header>

      {/* 消息列表 */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className={`flex flex-col items-center justify-center h-full mt-20 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
              <p className="text-4xl mb-4">🤖</p>
              <p className="text-lg">开始对话吧</p>
              <p className="text-sm mt-1">支持天气查询、数学计算、热榜查看等</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`group max-w-[75%] rounded-2xl px-4 py-2.5 whitespace-pre-wrap leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : `bg-gray-100 text-gray-800 rounded-bl-md ${isDark ? "!bg-gray-800 !text-gray-100" : ""}`
                }`}
              >
                <div className="relative">
                  {msg.content}
                  <button
                    onClick={() => navigator.clipboard.writeText(msg.content)}
                    className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition text-xs bg-gray-300 hover:bg-gray-400 text-gray-700 rounded px-1.5 py-0.5 cursor-pointer"
                    title="复制"
                  >
                    复制
                  </button>
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className={`rounded-2xl rounded-bl-md px-4 py-3 ${isDark ? "bg-gray-800" : "bg-gray-100"}`}>
                <span className="inline-flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.1s]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* 输入区 */}
      <footer className={`shrink-0 border-t px-4 py-3 ${isDark ? "border-gray-800 bg-gray-950" : "border-gray-200 bg-white"}`}>
        <div className="max-w-3xl mx-auto flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息..."
            rows={1}
            className={`flex-1 resize-none rounded-xl border px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 ${isDark ? "border-gray-700 bg-gray-900 text-gray-100 placeholder-gray-500" : "border-gray-300 bg-white text-gray-800 placeholder-gray-400"}`}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="shrink-0 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            发送
          </button>
        </div>
      </footer>
    </div>
  )
}

export default App
