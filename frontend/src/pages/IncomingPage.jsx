import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, PART_RU, today } from '../api.js'

const STATUS_RU = { new: 'Новая', converted: 'В заказе', ignored: 'Игнор' }
const SOURCE_RU = { telegram: 'Telegram', sms: 'SMS', max: 'MAX', whatsapp: 'WhatsApp', phone: 'Телефон' }

function ConvertForm({ msg, districts, onDone, onError }) {
  const f = (msg.parsed && msg.parsed.fields) || {}
  const [form, setForm] = useState({
    name: f.name || msg.sender_name || '',
    phone: f.phone || msg.sender || '',
    address: f.address || '',
    district_id: '',
    delivery_date: f.delivery_date || today(),
    time_window_type: f.time_window_type || 'any',
    bottles_pc_qty: f.bottles_pc_qty || 0,
    bottles_pet_qty: 0,
    pumps_qty: 0,
    total_amount: '0',
    comment: '',
  })
  const set = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    onError('')
    try {
      await api(`/incoming/${msg.id}/convert`, {
        method: 'POST',
        body: {
          ...form,
          district_id: form.district_id ? Number(form.district_id) : null,
          bottles_pc_qty: Number(form.bottles_pc_qty),
          bottles_pet_qty: Number(form.bottles_pet_qty),
          pumps_qty: Number(form.pumps_qty),
          total_amount: String(form.total_amount),
          comment: form.comment || null,
        },
      })
      onDone()
    } catch (err) {
      onError(err.message)
    }
  }

  return (
    <form className="card" onSubmit={submit} style={{ background: '#f5f9fd' }}>
      <h4>Создать заказ из заявки №{msg.id}</h4>
      <div className="row">
        <label>Имя<input value={form.name} onChange={set('name')} required /></label>
        <label>Телефон<input value={form.phone} onChange={set('phone')} required /></label>
        <label style={{ flex: 1 }}>Адрес<input value={form.address} onChange={set('address')} required /></label>
        <label>
          Район
          <select value={form.district_id} onChange={set('district_id')}>
            <option value="">—</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <label>Дата<input type="date" value={form.delivery_date} onChange={set('delivery_date')} /></label>
        <label>
          Часть дня
          <select value={form.time_window_type} onChange={set('time_window_type')}>
            {Object.entries(PART_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Бут. ПК<input type="number" min="0" value={form.bottles_pc_qty} onChange={set('bottles_pc_qty')} /></label>
        <label>Бут. ПЭТ<input type="number" min="0" value={form.bottles_pet_qty} onChange={set('bottles_pet_qty')} /></label>
        <label>Помпы<input type="number" min="0" value={form.pumps_qty} onChange={set('pumps_qty')} /></label>
        <label>Сумма<input type="number" min="0" step="0.01" value={form.total_amount} onChange={set('total_amount')} /></label>
        <button type="submit">Создать заказ</button>
      </div>
    </form>
  )
}

export default function IncomingPage() {
  const [status, setStatus] = useState('new')
  const [data, setData] = useState({ items: [], total: 0 })
  const [districts, setDistricts] = useState([])
  const [openId, setOpenId] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    api('/incoming', { params: { status, limit: 200 } })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [status])

  useEffect(() => { api('/districts').then(setDistricts) }, [])
  useEffect(load, [load])

  async function ignore(id) {
    setError('')
    try {
      await api(`/incoming/${id}/ignore`, { method: 'POST' })
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <h2>Входящие заявки</h2>
      <div className="card row">
        <label>
          Статус
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="new">Новые</option>
            <option value="converted">В заказе</option>
            <option value="ignored">Игнорированные</option>
            <option value="">Все</option>
          </select>
        </label>
        <span className="muted">Всего: {data.total}</span>
      </div>
      {error && <div className="error">{error}</div>}

      <table>
        <thead>
          <tr><th>№</th><th>Канал</th><th>Отправитель</th><th>Текст</th><th>Распознано</th><th>Статус</th><th></th></tr>
        </thead>
        <tbody>
          {data.items.map((m) => {
            const f = (m.parsed && m.parsed.fields) || {}
            return (
              <tr key={m.id}>
                <td>{m.id}</td>
                <td>{SOURCE_RU[m.source_type] || m.source_type}</td>
                <td>{m.sender_name || m.sender || '—'}</td>
                <td style={{ maxWidth: 280 }}>{m.raw_text}</td>
                <td className="muted">
                  {f.phone_normalized && <div>тел: {f.phone}</div>}
                  {f.address && <div>адрес: {f.address}</div>}
                  {f.bottles_pc_qty != null && <div>бутыли: {f.bottles_pc_qty}</div>}
                  {f.delivery_date && <div>дата: {f.delivery_date}</div>}
                </td>
                <td>
                  {m.status === 'converted' && m.order_id
                    ? <Link to={`/orders/${m.order_id}`}>заказ №{m.order_id}</Link>
                    : STATUS_RU[m.status]}
                </td>
                <td className="row">
                  {m.status === 'new' && (
                    <>
                      <button onClick={() => setOpenId(openId === m.id ? null : m.id)}>
                        {openId === m.id ? 'Скрыть' : 'В заказ'}
                      </button>
                      <button className="danger" onClick={() => ignore(m.id)}>Игнор</button>
                    </>
                  )}
                </td>
              </tr>
            )
          })}
          {data.items.length === 0 && <tr><td colSpan="7" className="muted">Заявок нет</td></tr>}
        </tbody>
      </table>

      {openId && (
        <ConvertForm
          msg={data.items.find((m) => m.id === openId)}
          districts={districts}
          onError={setError}
          onDone={() => { setOpenId(null); load() }}
        />
      )}
    </div>
  )
}
