import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Lock, ArrowRight } from 'lucide-react'

export default function Login() {
  const [isRegister, setIsRegister] = useState(false) // 切换登录/注册
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")

    // 1. 准备数据
    const endpoint = isRegister ? "/register" : "/token"
    
    // 如果是登录，OAuth2 标准要求用 form-data 格式
    // 如果是注册，我们自己定义的 json 格式
    let body, headers
    if (isRegister) {
      body = JSON.stringify({ username, password })
      headers = { 'Content-Type': 'application/json' }
    } else {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)
      body = formData
      headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    }

    try {
      const res = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: headers,
        body: body
      })
      
      const data = await res.json()
      
      if (!res.ok) throw new Error(data.detail || "操作失败")

      // 2. 保存 Token 到本地
      localStorage.setItem("token", data.access_token)
      localStorage.setItem("username", data.username)

      // 3. 跳转到聊天页
      navigate("/chat")

    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-gray-100">
      <div className="w-full max-w-md bg-white p-8 rounded-xl shadow-lg">
        <h2 className="text-2xl font-bold text-center text-blue-600 mb-6">
          {isRegister ? "注册新账户" : "登录 Network QA"}
        </h2>
        
        {error && <div className="bg-red-100 text-red-600 p-2 rounded mb-4 text-sm">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-center border rounded-lg p-2">
            <User className="text-gray-400 mr-2" size={20} />
            <input 
              type="text" placeholder="用户名" className="flex-1 outline-none"
              value={username} onChange={e=>setUsername(e.target.value)} required
            />
          </div>
          <div className="flex items-center border rounded-lg p-2">
            <Lock className="text-gray-400 mr-2" size={20} />
            <input 
              type="password" placeholder="密码" className="flex-1 outline-none"
              value={password} onChange={e=>setPassword(e.target.value)} required
            />
          </div>

          <button type="submit" className="w-full bg-blue-600 text-white p-2 rounded-lg hover:bg-blue-700 flex justify-center items-center">
            {isRegister ? "注册并登录" : "登录"} <ArrowRight size={16} className="ml-2"/>
          </button>
        </form>

        <div className="mt-4 text-center text-sm text-gray-500">
          <button onClick={() => setIsRegister(!isRegister)} className="hover:underline">
            {isRegister ? "已有账号？去登录" : "没有账号？去注册"}
          </button>
        </div>
      </div>
    </div>
  )
}