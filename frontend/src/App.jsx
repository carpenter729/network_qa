import { useState, useRef, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { Send, User, Bot, Loader2, LogOut } from 'lucide-react'
import Login from './Login'

// 聊天主界面组件
function ChatRoom() {
  const [messages, setMessages] = useState([]) 
  const [input, setInput] = useState("")       
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null) 
  const navigate = useNavigate()
  
  // 从本地获取 Token
  const token = localStorage.getItem("token")
  const username = localStorage.getItem("username")

  // 如果没有 Token，踢回登录页
  useEffect(() => {
    if (!token) navigate("/")
  }, [token, navigate])

  // 加载历史记录
  useEffect(() => {
    if (!token) return
    fetch('/api/history', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => {
        if(res.status === 401) { logout(); return [] }
        return res.json()
    })
    .then(data => {
        if(Array.isArray(data)) setMessages(data)
    })
  }, [])

  const logout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("username")
    navigate("/")
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }
  useEffect(scrollToBottom, [messages])

  const handleSend = async () => {
    if (!input.trim()) return

    const userMsg = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setIsLoading(true)

    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}` // 带上 Token
        },
        body: JSON.stringify({ question: input })
      })

      if (response.status === 401) { logout(); return; }
      if (!response.ok) throw new Error("API Error")
      if (!response.body) return

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      
      setMessages(prev => [...prev, { role: 'assistant', content: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        setMessages(prev => {
          const newMsgs = [...prev]
          const lastMsg = { ...newMsgs[newMsgs.length - 1] } 
          lastMsg.content += chunk
          newMsgs[newMsgs.length - 1] = lastMsg
          return newMsgs
        })
      }
    } catch (error) {
      console.error(error)
      setMessages(prev => [...prev, { role: 'assistant', content: "⚠️ 网络错误" }])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white shadow p-4 flex justify-between items-center z-10">
        <div className="font-bold text-xl text-blue-600">Network QA</div>
        <div className="flex items-center gap-4">
            <span className="text-gray-600 text-sm">Hi, {username}</span>
            <button onClick={logout} className="text-red-500 hover:bg-red-50 p-2 rounded"><LogOut size={18}/></button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex items-start max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`p-2 rounded-full mx-2 shadow-sm ${msg.role === 'user' ? 'bg-blue-500' : 'bg-emerald-500'} text-white flex-shrink-0`}>
                {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
              </div>
              <div className={`p-3 rounded-lg shadow-sm text-sm leading-relaxed overflow-hidden ${msg.role === 'user' ? 'bg-blue-100 text-blue-900' : 'bg-white text-gray-800'}`}>
                {msg.content ? (
                  <div className="prose prose-sm break-words"><ReactMarkdown>{msg.content}</ReactMarkdown></div>
                ) : <span className="animate-pulse">...</span>}
              </div>
            </div>
          </div>
        ))}
        {isLoading && <div className="text-center text-gray-400 text-xs"><Loader2 className="animate-spin inline mr-1"/>思考中...</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-white border-t">
        <div className="flex gap-2 max-w-4xl mx-auto">
          <input
            type="text" className="flex-1 p-3 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="输入问题..." value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isLoading && handleSend()} disabled={isLoading}
          />
          <button onClick={handleSend} disabled={isLoading} className="bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}

// 根组件：定义路由
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/chat" element={<ChatRoom />} />
        {/* 默认跳转 */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App