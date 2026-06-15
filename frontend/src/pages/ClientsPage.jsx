import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

function NewClientForm({ districts, onCreated }) {
  const [form, setForm] = useState({
    name: '', phone_primary: '', comment: '',
    raw_address: '', district_id: '', latitude: '', longitude: '', entrance: '', floor: '',
  })
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await api('/clients', {
        method: 'POST',
        body: {
          name: form.name,
          phone_primary: form.phone_primary,
          comment: form.comment || null,
          addresses: form.raw_address
            ? [{
                raw_address: form.raw_address,
                district_id: form.district_id ? Number(form.district_id) : null,
                latitude: form.latitude || null,
                longitude: form.longitude || null,
                entrance: form.entrance || null,
                floor: form.floor || null,
              }]
            : [],
        },
      })
      onCreated()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h3>Новый клиент</h3>
      <div className="row">
        <label>Имя<input value={form.name} onChange={set('name')} required /></label>
        <label>Телефон<input value={form.phone_primary} onChange={set('phone_primary')} required /></label>
        <label style={{ flex: 1 }}>Комментарий<input value={form.comment} onChange={set('comment')} /></label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <label style={{ flex: 1 }}>Адрес<input value={form.raw_address} onChange={set('raw_address')} /></label>
        <label>
          Район
          <select value={form.district_id} onChange={set('district_id')}>
            <option value="">—</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <label>Широта<input value={form.latitude} onChange={set('latitude')} placeholder="47.09" /></label>
        <label>Долгота<input value={form.longitude} onChange={set('longitude')} placeholder="37.54" /></label>
        <label>Подъезд<input value={form.entrance} onChange={set('entrance')} /></label>
        <label>Этаж<input value={form.floor} onChange={set('floor')} /></label>
        <button type="submit">Создать</button>
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

function DedupPanel({ onMerged }) {
  const [groups, setGroups] = useState(null)
  const [targets, setTargets] = useState({}) // groupIndex -> target client id
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  async function load() {
    setError('')
    setInfo('')
    try {
      const g = await api('/clients/duplicates')
      setGroups(g)
      setTargets(Object.fromEntries(g.map((grp, i) => [i, grp.client_ids[0]])))
      if (g.length === 0) setInfo('Дубликатов не найдено.')
    } catch (e) {
      setError(e.message)
    }
  }

  async function merge(grp, i) {
    setError('')
    const target_id = targets[i]
    const source_ids = grp.client_ids.filter((id) => id !== target_id)
    try {
      const r = await api('/clients/merge', { method: 'POST', body: { target_id, source_ids } })
      setInfo(`Слито в карточку №${r.target_id}: заказов ${r.moved.orders}, адресов ${r.moved.addresses}, контактов ${r.moved.contacts}.`)
      load()
      onMerged()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="card">
      <div className="row">
        <h3 style={{ margin: 0 }}>Поиск дубликатов</h3>
        <button className="secondary" onClick={load}>Найти дубликаты</button>
      </div>
      {error && <div className="error">{error}</div>}
      {info && <div className="success">{info}</div>}
      {groups && groups.map((grp, i) => (
        <div key={i} style={{ borderTop: '1px solid #e6ecf2', paddingTop: 8, marginTop: 8 }}>
          <p className="muted">Совпадение: {grp.reasons.join(', ')}. Выберите основную карточку:</p>
          {grp.clients.map((c) => (
            <label key={c.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input
                type="radio"
                name={`target-${i}`}
                checked={targets[i] === c.id}
                onChange={() => setTargets((t) => ({ ...t, [i]: c.id }))}
              />
              №{c.id} {c.name} — {c.phone_primary} ({c.addresses_count} адр.)
            </label>
          ))}
          <p><button onClick={() => merge(grp, i)}>Слить в выбранную</button></p>
        </div>
      ))}
    </div>
  )
}

export default function ClientsPage() {
  const [clients, setClients] = useState([])
  const [districts, setDistricts] = useState([])
  const [q, setQ] = useState('')
  const [phone, setPhone] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [showDedup, setShowDedup] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = useCallback(() => {
    api('/clients', { params: { q, phone, limit: 100 } })
      .then(setClients)
      .catch((e) => setError(e.message))
  }, [q, phone])

  useEffect(() => {
    api('/districts').then(setDistricts)
  }, [])
  useEffect(load, [load])

  return (
    <div>
      <h2>Клиенты</h2>
      <div className="card row">
        <label>Поиск (имя/адрес)<input value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <label>Телефон<input value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <button className="secondary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? 'Скрыть форму' : '+ Новый клиент'}
        </button>
        <button className="secondary" onClick={() => setShowDedup((s) => !s)}>
          {showDedup ? 'Скрыть дубликаты' : 'Дубликаты'}
        </button>
      </div>
      {showForm && <NewClientForm districts={districts} onCreated={() => { setShowForm(false); load() }} />}
      {showDedup && <DedupPanel onMerged={load} />}
      {error && <div className="error">{error}</div>}
      <table>
        <thead><tr><th>№</th><th>Имя</th><th>Телефон</th><th>Комментарий</th></tr></thead>
        <tbody>
          {clients.map((c) => (
            <tr key={c.id} className="clickable" onClick={() => navigate(`/clients/${c.id}`)}>
              <td>{c.id}</td><td>{c.name}</td><td>{c.phone_primary}</td><td>{c.comment || ''}</td>
            </tr>
          ))}
          {clients.length === 0 && <tr><td colSpan="4" className="muted">Не найдено</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
