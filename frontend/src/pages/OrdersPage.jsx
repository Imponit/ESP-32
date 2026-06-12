import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, STATUS_RU, PART_RU, today } from '../api.js'

function NewOrderForm({ districts, onCreated }) {
  const [clients, setClients] = useState([])
  const [clientId, setClientId] = useState('')
  const [addresses, setAddresses] = useState([])
  const [form, setForm] = useState({
    address_id: '',
    delivery_date: today(),
    time_window_type: 'any',
    bottles_pc_qty: 0,
    bottles_pet_qty: 0,
    pumps_qty: 0,
    total_amount: '0',
    payment_method_plan: 'unknown',
    comment: '',
  })
  const [error, setError] = useState('')

  useEffect(() => {
    api('/clients', { params: { limit: 200 } }).then(setClients).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!clientId) { setAddresses([]); return }
    api(`/clients/${clientId}`).then((c) => {
      setAddresses(c.addresses)
      setForm((f) => ({ ...f, address_id: c.addresses[0]?.id || '' }))
    })
  }, [clientId])

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await api('/orders', {
        method: 'POST',
        body: {
          ...form,
          client_id: Number(clientId),
          address_id: Number(form.address_id),
          bottles_pc_qty: Number(form.bottles_pc_qty),
          bottles_pet_qty: Number(form.bottles_pet_qty),
          pumps_qty: Number(form.pumps_qty),
          total_amount: String(form.total_amount),
          comment: form.comment || null,
        },
      })
      onCreated()
    } catch (err) {
      setError(err.message)
    }
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <form className="card" onSubmit={submit}>
      <h3>Новый заказ</h3>
      <div className="row">
        <label>
          Клиент
          <select value={clientId} onChange={(e) => setClientId(e.target.value)} required>
            <option value="">— выбрать —</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({c.phone_primary})</option>
            ))}
          </select>
        </label>
        <label>
          Адрес
          <select value={form.address_id} onChange={set('address_id')} required>
            {addresses.map((a) => (
              <option key={a.id} value={a.id}>{a.raw_address}</option>
            ))}
          </select>
        </label>
        <label>Дата<input type="date" value={form.delivery_date} onChange={set('delivery_date')} /></label>
        <label>
          Часть дня
          <select value={form.time_window_type} onChange={set('time_window_type')}>
            {Object.entries(PART_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <label>Бутыли ПК<input type="number" min="0" value={form.bottles_pc_qty} onChange={set('bottles_pc_qty')} /></label>
        <label>Бутыли ПЭТ<input type="number" min="0" value={form.bottles_pet_qty} onChange={set('bottles_pet_qty')} /></label>
        <label>Помпы<input type="number" min="0" value={form.pumps_qty} onChange={set('pumps_qty')} /></label>
        <label>Сумма, ₽<input type="number" min="0" step="0.01" value={form.total_amount} onChange={set('total_amount')} /></label>
        <label>
          Оплата (план)
          <select value={form.payment_method_plan} onChange={set('payment_method_plan')}>
            <option value="cash">Наличные</option>
            <option value="cashless">Карта/перевод</option>
            <option value="unknown">Не известно</option>
          </select>
        </label>
        <label style={{ flex: 1 }}>Комментарий<input value={form.comment} onChange={set('comment')} /></label>
        <button type="submit">Создать</button>
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}

export default function OrdersPage() {
  const [orders, setOrders] = useState([])
  const [districts, setDistricts] = useState([])
  const [drivers, setDrivers] = useState([])
  const [filters, setFilters] = useState({ date: today(), district_id: '', part: '', status: '', driver_id: '' })
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = useCallback(() => {
    api('/orders', { params: { ...filters, limit: 200 } })
      .then((d) => setOrders(d.items))
      .catch((e) => setError(e.message))
  }, [filters])

  useEffect(() => {
    api('/districts').then(setDistricts)
    api('/drivers').then(setDrivers)
  }, [])
  useEffect(load, [load])

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))
  const driverName = (id) => drivers.find((d) => d.id === id)?.name || '—'
  const districtName = (id) => districts.find((d) => d.id === id)?.name || '—'

  return (
    <div>
      <h2>Заказы</h2>
      <div className="card row">
        <label>Дата<input type="date" value={filters.date} onChange={set('date')} /></label>
        <label>
          Район
          <select value={filters.district_id} onChange={set('district_id')}>
            <option value="">Все</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <label>
          Часть дня
          <select value={filters.part} onChange={set('part')}>
            <option value="">Любая</option>
            {Object.entries(PART_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>
          Статус
          <select value={filters.status} onChange={set('status')}>
            <option value="">Все</option>
            {Object.entries(STATUS_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>
          Водитель
          <select value={filters.driver_id} onChange={set('driver_id')}>
            <option value="">Все</option>
            {drivers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <button className="secondary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? 'Скрыть форму' : '+ Новый заказ'}
        </button>
      </div>

      {showForm && (
        <NewOrderForm districts={districts} onCreated={() => { setShowForm(false); load() }} />
      )}
      {error && <div className="error">{error}</div>}

      <table>
        <thead>
          <tr>
            <th>№</th><th>Клиент</th><th>Адрес</th><th>Район</th><th>Бутыли</th>
            <th>Сумма</th><th>Статус</th><th>Водитель</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} className="clickable" onClick={() => navigate(`/orders/${o.id}`)}>
              <td>{o.id}</td>
              <td>{o.client_name}</td>
              <td>{o.address_text}</td>
              <td>{districtName(o.district_id)}</td>
              <td>{o.bottles_pc_qty + o.bottles_pet_qty}</td>
              <td>{o.total_amount} ₽</td>
              <td><span className={`badge ${o.status}`}>{STATUS_RU[o.status]}</span></td>
              <td>{o.assigned_driver_id ? driverName(o.assigned_driver_id) : '—'}</td>
            </tr>
          ))}
          {orders.length === 0 && <tr><td colSpan="8" className="muted">Заказов нет</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
