import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, STATUS_RU, today } from '../api.js'

const ACTOR_RU = { dispatcher: 'Диспетчер', driver: 'Водитель', system: 'Система' }
const EVENT_RU = {
  created: 'Создан',
  status_change: 'Смена статуса',
  payment: 'Оплата',
  comment: 'Комментарий',
}

function weekAgo() {
  const d = new Date()
  d.setDate(d.getDate() - 6)
  return d.toISOString().slice(0, 10)
}

export default function EventsPage() {
  const [filters, setFilters] = useState({
    date_from: weekAgo(), date_to: today(), order_id: '', actor_type: '', event_type: '',
  })
  const [data, setData] = useState({ items: [], total: 0 })
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState('')
  const limit = 100

  const load = useCallback(() => {
    setError('')
    api('/events', { params: { ...filters, limit, offset } })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [filters, offset])

  useEffect(load, [load])

  const set = (k) => (e) => { setOffset(0); setFilters((f) => ({ ...f, [k]: e.target.value })) }

  function describe(ev) {
    if (ev.event_type === 'status_change') {
      const from = STATUS_RU[ev.old_status] || ev.old_status || '—'
      const to = STATUS_RU[ev.new_status] || ev.new_status
      return `${from} → ${to}`
    }
    return EVENT_RU[ev.event_type] || ev.event_type
  }

  return (
    <div>
      <h2>Журнал событий</h2>
      <div className="card row">
        <label>С<input type="date" value={filters.date_from} onChange={set('date_from')} /></label>
        <label>По<input type="date" value={filters.date_to} onChange={set('date_to')} /></label>
        <label>Заказ №<input type="number" value={filters.order_id} onChange={set('order_id')} style={{ width: 90 }} /></label>
        <label>
          Кто
          <select value={filters.actor_type} onChange={set('actor_type')}>
            <option value="">Все</option>
            <option value="dispatcher">Диспетчер</option>
            <option value="driver">Водитель</option>
            <option value="system">Система</option>
          </select>
        </label>
        <label>
          Тип события
          <select value={filters.event_type} onChange={set('event_type')}>
            <option value="">Все</option>
            <option value="created">Создан</option>
            <option value="status_change">Смена статуса</option>
            <option value="payment">Оплата</option>
            <option value="comment">Комментарий</option>
          </select>
        </label>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="muted" style={{ marginBottom: 8 }}>Всего событий: {data.total}</div>
      <table>
        <thead>
          <tr>
            <th>Когда</th><th>Заказ</th><th>Клиент</th><th>Событие</th><th>Кто</th><th>Комментарий</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((ev) => (
            <tr key={ev.id}>
              <td className="muted">{new Date(ev.created_at).toLocaleString('ru-RU')}</td>
              <td><Link to={`/orders/${ev.order_id}`}>№{ev.order_id}</Link></td>
              <td>{ev.order_client_name || '—'}</td>
              <td>{describe(ev)}</td>
              <td>{ACTOR_RU[ev.actor_type]}{ev.actor_name ? ` (${ev.actor_name})` : ''}</td>
              <td>{ev.comment || ''}</td>
            </tr>
          ))}
          {data.items.length === 0 && <tr><td colSpan="6" className="muted">Событий нет</td></tr>}
        </tbody>
      </table>

      {data.total > limit && (
        <div className="row" style={{ marginTop: 10 }}>
          <button className="secondary" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - limit))}>← Назад</button>
          <span className="muted">{offset + 1}–{Math.min(offset + limit, data.total)} из {data.total}</span>
          <button className="secondary" disabled={offset + limit >= data.total} onClick={() => setOffset((o) => o + limit)}>Вперёд →</button>
        </div>
      )}
    </div>
  )
}
