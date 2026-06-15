import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, STATUS_RU, PART_RU, PAY_RU } from '../api.js'

// Переходы, доступные диспетчеру из панели (машина состояний — на сервере)
const DISPATCHER_TRANSITIONS = {
  draft: ['new'],
  new: ['needs_review', 'planned', 'cancelled'],
  needs_review: ['new', 'planned', 'cancelled'],
  planned: ['cancelled'],
  assigned: ['planned', 'cancelled'],
  sent_to_driver: ['accepted_by_driver', 'cancelled'],
  accepted_by_driver: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'failed', 'refused', 'postponed', 'cancelled'],
  postponed: ['new', 'cancelled'],
}

export default function OrderPage() {
  const { id } = useParams()
  const [order, setOrder] = useState(null)
  const [drivers, setDrivers] = useState([])
  const [error, setError] = useState('')
  const [comment, setComment] = useState('')
  const [driverId, setDriverId] = useState('')
  const [pay, setPay] = useState({ method: 'cash', amount: '' })

  const load = useCallback(() => {
    api(`/orders/${id}`).then(setOrder).catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    api('/drivers').then(setDrivers)
  }, [])
  useEffect(load, [load])

  if (error && !order) return <div className="error">{error}</div>
  if (!order) return <p>Загрузка…</p>

  async function transition(status) {
    setError('')
    try {
      await api(`/orders/${id}/transition`, { method: 'POST', body: { status, comment: comment || null } })
      setComment('')
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function assign() {
    setError('')
    try {
      await api(`/orders/${id}/assign-driver`, {
        method: 'POST',
        body: { driver_id: driverId ? Number(driverId) : null },
      })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function addPayment(e) {
    e.preventDefault()
    setError('')
    try {
      await api(`/orders/${id}/payment`, {
        method: 'POST',
        body: { method: pay.method, amount: String(pay.amount || order.total_amount) },
      })
      setPay({ method: 'cash', amount: '' })
      load()
    } catch (e2) {
      setError(e2.message)
    }
  }

  const next = DISPATCHER_TRANSITIONS[order.status] || []

  return (
    <div>
      <h2>
        Заказ №{order.id} <span className={`badge ${order.status}`}>{STATUS_RU[order.status]}</span>
      </h2>
      {error && <div className="error">{error}</div>}
      <div className="grid2">
        <div className="card">
          <h3>Данные заказа</h3>
          <p><b>Клиент:</b> <Link to={`/clients/${order.client_id}`}>{order.client_name}</Link>, {order.phone}</p>
          <p><b>Адрес:</b> {order.address_text}
            {order.entrance && `, подъезд ${order.entrance}`}{order.floor && `, этаж ${order.floor}`}
            {order.point_url && <> — <a href={order.point_url} target="_blank" rel="noreferrer">на карте</a></>}
          </p>
          <p><b>Дата:</b> {order.delivery_date} ({PART_RU[order.time_window_type]})</p>
          <p><b>Бутыли:</b> ПК {order.bottles_pc_qty}, ПЭТ {order.bottles_pet_qty}, помпы {order.pumps_qty}</p>
          <p><b>Сумма:</b> {order.total_amount} ₽ ({PAY_RU[order.payment_method_plan]}) —
            оплачено {order.paid_amount} ₽ ({{unpaid: 'не оплачен', paid: 'оплачен', partial: 'частично'}[order.payment_status]})</p>
          {order.comment && <p><b>Комментарий:</b> {order.comment}</p>}

          {order.items && order.items.length > 0 && (
            <>
              <h3>Позиции</h3>
              <table>
                <thead><tr><th>Товар</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr></thead>
                <tbody>
                  {order.items.map((it) => (
                    <tr key={it.id}>
                      <td>{it.name}</td>
                      <td>{it.qty}</td>
                      <td>{it.unit_price} ₽</td>
                      <td>{it.amount} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <h3>Смена статуса</h3>
          <div className="row">
            <label style={{ flex: 1 }}>
              Комментарий/причина (обязательно для «Ошибка» и «Отказ»)
              <input value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            {next.map((s) => (
              <button key={s} className={s === 'cancelled' ? 'danger' : ''} onClick={() => transition(s)}>
                {STATUS_RU[s]}
              </button>
            ))}
            {next.length === 0 && <span className="muted">Статус терминальный.</span>}
          </div>

          <h3>Водитель</h3>
          <div className="row">
            <label>
              Назначить
              <select value={driverId} onChange={(e) => setDriverId(e.target.value)}>
                <option value="">— снять назначение —</option>
                {drivers.filter((d) => d.is_active).map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
            <button onClick={assign}>Применить</button>
            <span className="muted">
              Сейчас: {order.assigned_driver_id
                ? drivers.find((d) => d.id === order.assigned_driver_id)?.name || order.assigned_driver_id
                : 'не назначен'}
            </span>
          </div>

          <h3>Оплата (вручную диспетчером)</h3>
          <form className="row" onSubmit={addPayment}>
            <label>
              Способ
              <select value={pay.method} onChange={(e) => setPay((p) => ({ ...p, method: e.target.value }))}>
                <option value="cash">Наличные</option>
                <option value="cashless">Карта/перевод</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label>
              Сумма (пусто — вся)
              <input type="number" step="0.01" min="0.01" value={pay.amount}
                onChange={(e) => setPay((p) => ({ ...p, amount: e.target.value }))} />
            </label>
            <button type="submit">Зафиксировать</button>
          </form>
        </div>

        <div className="card">
          <h3>История событий</h3>
          <table>
            <thead>
              <tr><th>Когда</th><th>Событие</th><th>Кто</th><th>Комментарий</th></tr>
            </thead>
            <tbody>
              {order.events.map((e) => (
                <tr key={e.id}>
                  <td className="muted">{new Date(e.created_at).toLocaleString('ru-RU')}</td>
                  <td>
                    {e.event_type === 'status_change'
                      ? `${STATUS_RU[e.old_status] || e.old_status || '—'} → ${STATUS_RU[e.new_status] || e.new_status}`
                      : e.event_type}
                  </td>
                  <td>{{ dispatcher: 'диспетчер', driver: 'водитель', system: 'система' }[e.actor_type]}</td>
                  <td>{e.comment || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
