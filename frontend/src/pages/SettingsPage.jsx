import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SettingsPage() {
  const [districts, setDistricts] = useState([])
  const [settings, setSettings] = useState([])
  const [newDistrict, setNewDistrict] = useState('')
  const [maxPoints, setMaxPoints] = useState('')
  const [geoThreshold, setGeoThreshold] = useState('')
  const [message, setMessage] = useState(null)

  const load = useCallback(async () => {
    setDistricts(await api('/districts'))
    const s = await api('/settings')
    setSettings(s)
    const mp = s.find((x) => x.key === 'max_route_points')
    setMaxPoints(mp ? String(mp.value) : '9')
    const gt = s.find((x) => x.key === 'geocode_confidence_threshold')
    setGeoThreshold(gt ? String(gt.value) : '0.7')
  }, [])

  useEffect(() => {
    load().catch((e) => setMessage({ type: 'error', text: e.message }))
  }, [load])

  async function addDistrict(e) {
    e.preventDefault()
    try {
      await api('/districts', { method: 'POST', body: { name: newDistrict } })
      setNewDistrict('')
      load()
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  async function toggleDistrict(d) {
    await api(`/districts/${d.id}`, { method: 'PATCH', body: { is_active: !d.is_active } })
    load()
  }

  async function saveSetting(key, value) {
    setMessage(null)
    try {
      await api(`/settings/${key}`, { method: 'PUT', body: { value } })
      setMessage({ type: 'success', text: 'Сохранено.' })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message + ' (нужна роль admin)' })
    }
  }

  return (
    <div>
      <h2>Настройки</h2>
      {message && <div className={message.type}>{message.text}</div>}
      <div className="grid2">
        <div className="card">
          <h3>Районы</h3>
          <table>
            <thead><tr><th>Название</th><th>Активен</th><th></th></tr></thead>
            <tbody>
              {districts.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.is_active ? 'да' : <span className="error">нет</span>}</td>
                  <td>
                    <button className="secondary" onClick={() => toggleDistrict(d)}>
                      {d.is_active ? 'Отключить' : 'Включить'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <form className="row" style={{ marginTop: 10 }} onSubmit={addDistrict}>
            <label>Новый район<input value={newDistrict} onChange={(e) => setNewDistrict(e.target.value)} required /></label>
            <button type="submit">Добавить</button>
          </form>
        </div>
        <div className="card">
          <h3>Параметры</h3>
          <div className="row">
            <label>
              Лимит точек в пакете
              <input type="number" min="1" max="20" value={maxPoints} onChange={(e) => setMaxPoints(e.target.value)} />
            </label>
            <button onClick={() => saveSetting('max_route_points', Number(maxPoints))}>Сохранить</button>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <label>
              Порог точности геокодера (0–1)
              <input type="number" min="0" max="1" step="0.05" value={geoThreshold} onChange={(e) => setGeoThreshold(e.target.value)} />
            </label>
            <button onClick={() => saveSetting('geocode_confidence_threshold', Number(geoThreshold))}>Сохранить</button>
          </div>
          <p className="muted">
            Ниже порога геокодинг считается неточным, и заказы адреса уходят на проверку (needs_review).
          </p>
          <p className="muted" style={{ marginTop: 16 }}>
            Прочие настройки: {settings.filter((s) => !['max_route_points', 'geocode_confidence_threshold'].includes(s.key)).map((s) => `${s.key}=${JSON.stringify(s.value)}`).join(', ') || '—'}
          </p>
          <p className="muted">Правила баллов появятся позже (MVP-2).</p>
        </div>
      </div>
    </div>
  )
}
