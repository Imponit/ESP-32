import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

export default function DriversPage() {
  const [drivers, setDrivers] = useState([])
  const [districts, setDistricts] = useState([])
  const [error, setError] = useState('')
  const [edit, setEdit] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(() => {
    api('/drivers').then(setDrivers).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    api('/districts').then(setDistricts)
  }, [])
  useEffect(load, [load])

  async function save(d, isNew) {
    setError('')
    const body = {
      name: d.name,
      phone: d.phone,
      telegram_id: d.telegram_id ? Number(d.telegram_id) : null,
      district_default_id: d.district_default_id ? Number(d.district_default_id) : null,
      vehicle: d.vehicle || null,
      capacity_bottles: Number(d.capacity_bottles || 0),
      comment: d.comment || null,
    }
    try {
      if (isNew) await api('/drivers', { method: 'POST', body })
      else await api(`/drivers/${d.id}`, { method: 'PATCH', body })
      setEdit(null)
      setShowForm(false)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function toggleActive(d) {
    await api(`/drivers/${d.id}`, { method: 'PATCH', body: { is_active: !d.is_active } })
    load()
  }

  function DriverForm({ initial, isNew }) {
    const [d, setD] = useState(initial)
    const set = (k) => (e) => setD((x) => ({ ...x, [k]: e.target.value }))
    return (
      <div className="card row">
        <label>Имя<input value={d.name || ''} onChange={set('name')} /></label>
        <label>Телефон<input value={d.phone || ''} onChange={set('phone')} /></label>
        <label>Telegram ID<input value={d.telegram_id || ''} onChange={set('telegram_id')} placeholder="вручную" /></label>
        <label>Машина<input value={d.vehicle || ''} onChange={set('vehicle')} /></label>
        <label>Вместимость, бут.<input type="number" min="0" value={d.capacity_bottles || 0} onChange={set('capacity_bottles')} /></label>
        <label>
          Район по умолчанию
          <select value={d.district_default_id || ''} onChange={set('district_default_id')}>
            <option value="">—</option>
            {districts.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <button onClick={() => save(d, isNew)}>Сохранить</button>
        <button className="secondary" onClick={() => { setEdit(null); setShowForm(false) }}>Отмена</button>
      </div>
    )
  }

  return (
    <div>
      <h2>Водители</h2>
      {error && <div className="error">{error}</div>}
      {!showForm && <p><button onClick={() => setShowForm(true)}>+ Новый водитель</button></p>}
      {showForm && <DriverForm initial={{ capacity_bottles: 40 }} isNew />}
      <table>
        <thead>
          <tr>
            <th>№</th><th>Имя</th><th>Телефон</th><th>Telegram</th><th>Машина</th>
            <th>Вместимость</th><th>Статус</th><th>Активен</th><th></th>
          </tr>
        </thead>
        <tbody>
          {drivers.map((d) => (
            <tr key={d.id}>
              <td>{d.id}</td>
              <td>{d.name}</td>
              <td>{d.phone}</td>
              <td>{d.telegram_id || <span className="muted">не привязан</span>}</td>
              <td>{d.vehicle || '—'}</td>
              <td>{d.capacity_bottles}</td>
              <td>{d.work_status === 'on_route' ? '🚚 на маршруте' : 'свободен'}</td>
              <td>{d.is_active ? 'да' : <span className="error">нет</span>}</td>
              <td className="row">
                <button className="secondary" onClick={() => setEdit(d.id)}>Изменить</button>
                <button className={d.is_active ? 'danger' : ''} onClick={() => toggleActive(d)}>
                  {d.is_active ? 'Деактивировать' : 'Активировать'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {edit && <DriverForm initial={drivers.find((d) => d.id === edit)} isNew={false} />}
    </div>
  )
}
