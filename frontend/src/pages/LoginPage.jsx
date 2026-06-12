import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../api.js'

export default function LoginPage() {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await api('/auth/login', { method: 'POST', body: { login, password } })
      setToken(data.access_token)
      navigate('/today')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="login-page">
      <div className="card">
        <h2>Вход в систему</h2>
        <form onSubmit={submit}>
          <label>
            Логин
            <input value={login} onChange={(e) => setLogin(e.target.value)} autoFocus />
          </label>
          <label>
            Пароль
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="error">{error}</div>}
          <button type="submit">Войти</button>
        </form>
      </div>
    </div>
  )
}
