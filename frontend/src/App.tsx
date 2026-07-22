import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function App() {
  // ── 认证状态 ──
  const [token, setToken] = useState(() => localStorage.getItem('token') || '')
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('session_id') || '')
  const [userId, setUserId] = useState(() => Number(localStorage.getItem('user_id') || '0'))
  const [username, setUsername] = useState(() => localStorage.getItem('username') || '')
  const [page, setPage] = useState<'auth' | 'chat' | 'profile'>(token ? 'chat' : 'auth')

  // ── 聊天状态 ──
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [modelProvider, setModelProvider] = useState('deepseek')
  const [isDark, setIsDark] = useState(false)
  const [toast, setToast] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // ── 认证表单状态 ──
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authUser, setAuthUser] = useState('')
  const [authEmail, setAuthEmail] = useState('')
  const [authPass, setAuthPass] = useState('')
  const [authPass2, setAuthPass2] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [showPass2, setShowPass2] = useState(false)
  const [profileInfo, setProfileInfo] = useState<any>(null)
  const [profileName, setProfileName] = useState('')
  const [pwdOld, setPwdOld] = useState('')
  const [pwdNew, setPwdNew] = useState('')
  const [pwdNew2, setPwdNew2] = useState('')
  const [profileMsg, setProfileMsg] = useState({ type: '', text: '' })
  const [sessions, setSessions] = useState<any[]>([])
  const [showSidebar, setShowSidebar] = useState(true)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  const apiBase = import.meta.env.VITE_API_URL || ''

  // 保存认证信息到 localStorage
  const saveAuth = (t: string, sid: string, uid: number, uname: string) => {
    setToken(t); setSessionId(sid); setUserId(uid); setUsername(uname)
    localStorage.setItem('token', t)
    localStorage.setItem('session_id', sid)
    localStorage.setItem('user_id', String(uid))
    localStorage.setItem('username', uname)
  }

  const clearAuth = () => {
    setToken(''); setSessionId(''); setUserId(0); setUsername('')
    localStorage.removeItem('token')
    localStorage.removeItem('session_id')
    localStorage.removeItem('user_id')
    localStorage.removeItem('username')
    setPage('auth')
    setMessages([])
  }

  // ── 模型信息 ──
  const MODEL_INFO: Record<string, { label: string; role: string; scene: string }> = {
    deepseek: { label: 'DeepSeek', role: '通用助手', scene: '日常对话、问答、工具调用' },
    glm: { label: '智谱 GLM', role: '创意写作', scene: '写文章、文案、翻译、故事' },
    qwen: { label: '通义千问', role: '逻辑分析', scene: '推理、代码、数学、技术问题' },
    yi: { label: '零一万物', role: '头脑风暴', scene: '灵感发散、快速生成、脑洞' },
  }

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(''), 2000)
    return () => clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── 认证操作 ──
  const authHeaders = (): Record<string, string> => ({
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  })

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError('')

    if (authMode === 'register') {
      if (!authUser.trim() || !authEmail.trim() || !authPass) {
        setAuthError('请填写所有字段'); return
      }
      if (authPass.length < 6) { setAuthError('密码至少 6 位'); return }
      if (authPass !== authPass2) { setAuthError('两次密码不一致'); return }
    } else {
      if (!authUser.trim() || !authPass) { setAuthError('请填写用户名和密码'); return }
    }

    setAuthLoading(true)
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/register'
      const body: any = { username: authUser.trim(), password: authPass }
      if (authMode === 'register') body.email = authEmail.trim()

      const res = await fetch(`${apiBase}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      // 先读成文本，再尝试 JSON 解析，防止后端返回 HTML 时崩溃
      const text = await res.text()
      let data: any
      try { data = JSON.parse(text) } catch { throw new Error('服务器返回了意外的响应，请检查后端是否已启动') }
      if (!res.ok) { setAuthError(data.detail || '操作失败'); return }

      saveAuth(data.token, data.session_id, data.user_id, authUser.trim())
      setPage('chat')
    } catch (e: any) {
      setAuthError(e.message || '网络错误')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await fetch(`${apiBase}/auth/logout`, {
        method: 'POST',
        headers: authHeaders(),
      })
    } catch { /* ignore */ }
    clearAuth()
  }

  // 切换账号：不清除 token，让登录页可以返回聊天
  const switchUser = () => {
    setPage('auth')
    setMessages([])
  }

  // ── 个人主页操作 ──
  const fetchProfile = async () => {
    try {
      const res = await fetch(`${apiBase}/user/profile`, { headers: authHeaders() })
      if (!res.ok) throw new Error('获取信息失败')
      const data = await res.json()
      setProfileInfo(data)
      setProfileName(data.display_name || '')
    } catch (e: any) {
      setProfileMsg({ type: 'error', text: e.message })
    }
  }

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileMsg({ type: '', text: '' })
    try {
      const res = await fetch(`${apiBase}/user/profile`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ display_name: profileName.trim() }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '修改失败')
      setProfileInfo((prev: any) => prev ? { ...prev, display_name: profileName.trim() } : prev)
      setProfileMsg({ type: 'success', text: data.message })
    } catch (e: any) {
      setProfileMsg({ type: 'error', text: e.message })
    }
  }

  const handleUpdatePwd = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileMsg({ type: '', text: '' })
    if (pwdNew.length < 6) { setProfileMsg({ type: 'error', text: '新密码至少 6 位' }); return }
    if (pwdNew !== pwdNew2) { setProfileMsg({ type: 'error', text: '两次密码不一致' }); return }
    try {
      const res = await fetch(`${apiBase}/user/password`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ old_password: pwdOld, new_password: pwdNew }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '修改失败')
      setProfileMsg({ type: 'success', text: data.message })
      setPwdOld(''); setPwdNew(''); setPwdNew2('')
    } catch (e: any) {
      setProfileMsg({ type: 'error', text: e.message })
    }
  }

  // ── 会话管理 ──
  const fetchSessions = async () => {
    try {
      const res = await fetch(`${apiBase}/user/sessions`, { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setSessions(data.sessions || [])
      }
    } catch {}
  }

  // 拉取指定会话的历史消息
  const fetchMessages = async (sid: string) => {
    setHistoryLoading(true)
    try {
      const res = await fetch(`${apiBase}/user/sessions/${sid}/messages?limit=200`, { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setMessages(data.messages || [])
      } else if (res.status === 401) {
        clearAuth()
      } else {
        setMessages([])
      }
    } catch {
      setMessages([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const switchSession = async (newId: string) => {
    if (newId === sessionId) return
    setSessionId(newId)
    setMessages([])
    localStorage.setItem('session_id', newId)
    // 移动端自动收起侧边栏
    if (window.innerWidth < 768) setShowSidebar(false)
    await fetchMessages(newId)
  }

  const newSession = async () => {
    try {
      const res = await fetch(`${apiBase}/user/sessions`, {
        method: 'POST',
        headers: authHeaders(),
      })
      if (res.ok) {
        const data = await res.json()
        await switchSession(data.session_id)
        await fetchSessions()
      }
    } catch {}
  }

  const deleteSession = async (sid: string) => {
    try {
      const res = await fetch(`${apiBase}/user/sessions/${sid}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (res.ok) {
        if (sid === sessionId) {
          // 如果删除的是当前会话，切换到第一个可用会话
          const remaining = sessions.filter((s: any) => s.session_id !== sid)
          if (remaining.length > 0) {
            await switchSession(remaining[0].session_id)
          }
        }
        await fetchSessions()
      }
    } catch {}
  }

  // 登录/切换页面时加载会话列表 + 当前会话历史
  useEffect(() => {
    if (token) {
      fetchSessions()
      if (sessionId) fetchMessages(sessionId)
    }
  }, [token])

  // ── 聊天操作 ──
  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '' },
    ])
    setLoading(true)

    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ message: text, session_id: sessionId, model_provider: modelProvider }),
      })

      if (!res.ok) {
        if (res.status === 401) { clearAuth(); throw new Error('登录已过期，请重新登录') }
        throw new Error(`请求失败: HTTP ${res.status}`)
      }

      const data = await res.json()
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: data.reply || '(未获取到回答)' }
        return next
      })
      // 刷新会话列表（更新预览文字）
      fetchSessions()
    } catch (e: any) {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last?.role === 'assistant' && !last.content) {
          next[next.length - 1] = { role: 'assistant', content: `请求失败：${e.message}` }
        } else {
          next.push({ role: 'assistant', content: `请求失败：${e.message}` })
        }
        return next
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  // ═══════════════════════════════════════
  //  渲染：登录/注册页
  // ═══════════════════════════════════════
  if (page === 'auth') {
    return (
      <div className="flex items-center justify-center min-h-dvh bg-gray-50 dark:bg-gray-950">
        <div className="w-full max-w-sm mx-4">
          <div className="text-center mb-8">
            <p className="text-5xl mb-3">🤖</p>
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">AI Agent</h1>
            <p className="text-sm text-gray-400 mt-1">登录以继续使用</p>
          </div>

          {/* 如果已登录（切换账号场景），显示返回聊天按钮 */}
          {token && (
            <div className="text-center mb-2">
              <button onClick={() => setPage('chat')}
                className="text-sm text-blue-500 hover:text-blue-400 transition cursor-pointer">
                ← 返回聊天
              </button>
            </div>
          )}
          <form onSubmit={handleAuth} className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 space-y-4">
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
              {authMode === 'login' ? '登录' : '注册'}
            </h2>

            <input
              type="text" placeholder="用户名" required
              value={authUser} onChange={(e) => setAuthUser(e.target.value)}
              className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
            />

            {authMode === 'register' && (
              <input
                type="email" placeholder="邮箱" required
                value={authEmail} onChange={(e) => setAuthEmail(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
            )}

            <div className="relative">
              <input
                type={showPass ? "text" : "password"} placeholder="密码" required
                value={authPass} onChange={(e) => setAuthPass(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2.5 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
              <button type="button" onClick={() => setShowPass(!showPass)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer text-sm select-none"
                title={showPass ? "隐藏密码" : "显示密码"}
              >
                {showPass ? "😀" : "🙈"}
              </button>
            </div>

            {authMode === 'register' && (
              <div className="relative">
                <input
                  type={showPass2 ? "text" : "password"} placeholder="确认密码" required
                  value={authPass2} onChange={(e) => setAuthPass2(e.target.value)}
                  className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2.5 pr-10 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
                />
                <button type="button" onClick={() => setShowPass2(!showPass2)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 cursor-pointer text-sm select-none"
                  title={showPass2 ? "隐藏密码" : "显示密码"}
                >
                  {showPass2 ? "😀" : "🙈"}
                </button>
              </div>
            )}

            {authError && (
              <p className="text-sm text-red-500">{authError}</p>
            )}

            <button
              type="submit" disabled={authLoading}
              className="w-full rounded-xl bg-blue-600 py-2.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40 transition"
            >
              {authLoading ? '处理中...' : authMode === 'login' ? '登录' : '注册'}
            </button>

            <p className="text-xs text-center text-gray-400">
              {authMode === 'login' ? (
                <>还没有账号？<button type="button" onClick={() => { setAuthMode('register'); setAuthError('') }} className="text-blue-500 hover:underline cursor-pointer">注册</button></>
              ) : (
                <>已有账号？<button type="button" onClick={() => { setAuthMode('login'); setAuthError('') }} className="text-blue-500 hover:underline cursor-pointer">登录</button></>
              )}
            </p>
          </form>
        </div>
      </div>
    )
  }

  // ═══════════════════════════════════════
  //  渲染：个人主页
  // ═══════════════════════════════════════
  if (page === 'profile') {
    return (
      <div className="flex flex-col h-dvh bg-gray-50 dark:bg-gray-950">
        <header className="shrink-0 border-b px-4 py-3 bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100">个人中心</h1>
            <button onClick={() => setPage('chat')}
              className="text-xs text-blue-500 hover:text-blue-400 transition cursor-pointer">
              返回聊天
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-lg mx-auto space-y-6">

            <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 p-6">
              <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-3">账号信息</h2>
              <div className="space-y-2 text-sm">
                <p className="text-gray-800 dark:text-gray-100">用户名：{profileInfo?.username || '...'}</p>
                <p className="text-gray-800 dark:text-gray-100">邮箱：{profileInfo?.email || '...'}</p>
                <p className="text-gray-800 dark:text-gray-100">显示名称：{profileInfo?.display_name || '...'}</p>
              </div>
            </div>

            <form onSubmit={handleUpdateName} className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 space-y-3">
              <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400">修改显示名称</h2>
              <input type="text" placeholder="新显示名称" required
                value={profileName} onChange={(e) => setProfileName(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
              <button type="submit" className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition">保存</button>
            </form>

            <form onSubmit={handleUpdatePwd} className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 p-6 space-y-3">
              <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400">修改密码</h2>
              <input type="password" placeholder="当前密码" required
                value={pwdOld} onChange={(e) => setPwdOld(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
              <input type="password" placeholder="新密码（至少 6 位）" required
                value={pwdNew} onChange={(e) => setPwdNew(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
              <input type="password" placeholder="确认新密码" required
                value={pwdNew2} onChange={(e) => setPwdNew2(e.target.value)}
                className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-gray-800 dark:text-gray-100 placeholder-gray-400"
              />
              <button type="submit" className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition">修改密码</button>
            </form>

            {profileMsg.text && (
              <div className={`text-sm px-4 py-2 rounded-xl ${
                profileMsg.type === 'success' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'}`}>
                {profileMsg.text}
              </div>
            )}

            <div className="text-center pt-2 pb-8">
              <button onClick={switchUser}
                className="text-sm text-gray-400 hover:text-red-500 transition cursor-pointer">
                切换用户
              </button>
            </div>
          </div>
        </main>
      </div>
    )
  }

  // ═══════════════════════════════════════
  //  渲染：聊天页
  // ═══════════════════════════════════════
  return (
    <div className="flex h-dvh">
      {/* 侧边栏 - 历史会话 */}
      <aside className={`${showSidebar ? "w-60" : "w-0"} flex-shrink-0 transition-all duration-200 overflow-hidden border-r ${isDark ? "border-gray-800 bg-gray-900" : "border-gray-200 bg-gray-50"}`}>
        <div className="flex flex-col h-full">
          <div className="p-3">
            <button onClick={newSession}
              className="w-full rounded-lg border border-dashed border-gray-400 dark:border-gray-600 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-blue-500 hover:border-blue-500 transition cursor-pointer">
              + 新建对话
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto px-2 pb-2 space-y-1">
            {sessions.map((s: any) => (
              <div key={s.session_id}
                className={`group flex items-center gap-1 rounded-lg px-3 py-2 text-sm cursor-pointer transition ${
                  s.session_id === sessionId
                    ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
                    : 'hover:bg-gray-200 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
                }`}
                onClick={() => switchSession(s.session_id)}
              >
                <span className="flex-1 truncate" title={s.preview || s.label}>
                  {s.preview || s.label}
                </span>
                <button onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id) }}
                  className="opacity-0 group-hover:opacity-100 text-xs text-gray-400 hover:text-red-500 transition cursor-pointer shrink-0"
                  title="删除">✕</button>
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="text-xs text-gray-400 text-center mt-4">暂无历史对话</p>
            )}
          </nav>
        </div>
      </aside>

      {/* 主聊天区 */}
      <div className={`flex flex-col flex-1 ${isDark ? "bg-gray-950 text-gray-100" : "bg-white text-gray-800"}`}>
      {/* 顶栏 */}
      <header className={`shrink-0 border-b px-4 py-3 ${isDark ? "border-gray-800" : "border-gray-200"}`}>
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowSidebar(!showSidebar)}
              className="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition cursor-pointer"
              title={showSidebar ? "收起侧边栏" : "展开侧边栏"}>
              {showSidebar ? "◁" : "▷"}
            </button>
            <h1 className={`text-lg font-semibold ${isDark ? "text-gray-100" : "text-gray-800"}`}>
              AI Agent
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <select
                value={modelProvider}
                onChange={(e) => {
                  const val = e.target.value
                  setModelProvider(val)
                  setToast(`已切换到 ${MODEL_INFO[val].label} · ${MODEL_INFO[val].role}`)
                }}
                className={`text-xs rounded px-2 py-1 cursor-pointer ${isDark ? "bg-gray-800 text-gray-200 border-gray-600" : "bg-gray-100 text-gray-700 border-gray-300"} border`}
                title="点击切换模型"
              >
                <option value="deepseek">DeepSeek · 通用助手</option>
                <option value="glm">智谱 GLM · 创意写作</option>
                <option value="qwen">通义千问 · 逻辑分析</option>
                <option value="yi">零一万物 · 头脑风暴</option>
              </select>
              {toast && (
                <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 z-50 whitespace-nowrap text-xs px-2 py-1 rounded shadow-lg bg-blue-600 text-white">
                  {toast}
                </div>
              )}
            </div>

            <span className="text-xs text-gray-400 hidden sm:inline">{MODEL_INFO[modelProvider]?.scene || ''}</span>

            {/* 用户信息 + 个人中心 + 退出 */}
            <span className="text-xs text-gray-400 font-mono hidden sm:inline">{username}</span>
            <span className="hidden">{userId}</span>
            <button
              onClick={() => { setPage("profile"); setTimeout(fetchProfile, 50) }}
              className="text-xs text-gray-400 hover:text-blue-500 transition cursor-pointer"
              title="个人中心"
            >
              个人中心
            </button>
            <button
              onClick={handleLogout}
              className="text-xs text-gray-400 hover:text-red-500 transition cursor-pointer"
              title="退出登录"
            >
              退出
            </button>

            <button
              onClick={() => setIsDark(!isDark)}
              className={`text-xs px-2 py-1 rounded transition cursor-pointer ${isDark ? "text-yellow-400 hover:text-yellow-300" : "text-gray-400 hover:text-gray-600"}`}
              title={isDark ? "切换到浅色" : "切换到深色"}
            >
              {isDark ? "☀️" : "🌙"}
            </button>

            {messages.length > 0 && (
              <button onClick={() => setMessages([])}
                className="text-xs text-gray-400 hover:text-red-500 transition cursor-pointer" title="清空对话">
                清空
              </button>
            )}
          </div>
        </div>
      </header>

      {/* 消息列表 */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && !historyLoading && (
            <div className={`flex flex-col items-center justify-center h-full mt-20 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
              <p className="text-4xl mb-4">🤖</p>
              <p className="text-lg">开始对话吧</p>
              <p className="text-sm mt-1">支持天气查询、数学计算、热榜查看等</p>
              <p className="text-xs mt-2 opacity-60">顶部可切换模型：DeepSeek（通用）· 智谱（写作）· 千问（分析）· 零一万物（创意）</p>
            </div>
          )}

          {historyLoading && (
            <div className={`flex justify-center mt-10 ${isDark ? "text-gray-500" : "text-gray-400"}`}>
              <p className="text-sm">加载历史对话中...</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`group max-w-[75%] rounded-2xl px-4 py-2.5 whitespace-pre-wrap leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-md'
                  : `bg-gray-100 text-gray-800 rounded-bl-md ${isDark ? "!bg-gray-800 !text-gray-100" : ""}`
              }`}>
                <div className="relative">
                  {msg.content}
                  <button
                    onClick={() => navigator.clipboard.writeText(msg.content)}
                    className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition text-xs bg-gray-300 hover:bg-gray-400 text-gray-700 rounded px-1.5 py-0.5 cursor-pointer"
                    title="复制">复制</button>
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
          >发送</button>
        </div>
      </footer>
    </div>
    </div>
  )
}

export default App
