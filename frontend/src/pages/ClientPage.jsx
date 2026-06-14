import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, GEOCODE_RU, STATUS_RU } from '../api.js'

export default function ClientPage() {
  const { id } = useParams()
  const [client, setClient] = useState(null)
  const [orders, setOrders] = useState([])
  const [districts, setDistricts] = useState([])
  const [error, setError] = useState('')
  const [edit, setEdit] = useState(null) // адрес в редактировании
  const [newAddr, setNewAddr] = useState(null)
  const [geocoding, setGeocoding] = useState(null) // id геокодируемого адреса
  const [info, setInfo] = useState('')

  const load = useCallback(() => {
    api(`/clients/${id}`).then(setClient).catch((e) => setError(e.message))
    api('/orders', { params: { client_id: id, limit: 50 } }).then((d) => setOrders(d.items))
  }, [id])

  useEffect(() => {
    api('/districts').then(setDistricts)
  }, [])
  useEffect(load, [load])

  if (error && !client) return <div className="error">{error}</div>
  if (!client) return <p>Загрузка…</p>

  async function geocode(addressId) {
    setError('')
    setInfo('')
    setGeocoding(addressId)
    try {
      const r = await api(`/addresses/${addressId}/geocode`, { method: 'POST' })
      const msgs = {
        ok: r.imprecise
          ? `Координаты найдены, но неточно (${r.confidence}). Заказы отправлены на проверку: ${r.needs_review_order_ids.join(', ') || '—'}.`
          : `Координаты найдены (точность ${r.confidence}).`,
        pending: 'Геокодер недоступен — адрес помечен «ожидает», попробуйте позже.',
        failed: 'Адрес не найден геокодером — впишите координаты вручную.',
        skipped_manual: 'Координаты заданы вручную — пропущено (для переразбора жмите ещё раз с force).',
        already_has_coords: 'Координаты уже есть — пропущено.',
      }
      setInfo(msgs[r.status] || `Статус: ${r.status}`)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setGeocoding(null)
    }
  }

  async function saveAddress(addr, isNew) {
    setError('')
    const body = {
      raw_address: addr.raw_address,
      district_id: addr.district_id ? Number(addr.district_id) : null,
      latitude: addr.latitude || null,
      longitude: addr.longitude || null,
      entrance: addr.entrance || null,
      floor: addr.floor || null,
    }
    try {
      if (isNew) await api(`/clients/${id}/addresses`, { method: 'POST', body })
      else await api(`/addresses/${addr.id}`, { method: 'PATCH', body })
      setEdit(null)
      setNewAddr(null)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  function AddressForm({ addr, isNew }) {
    const [a, setA] = useState(addr)
    const set = (k) => (e) => setA((x) => ({ ...x, [k]: e.target.value }))
    return (
      <div className="row" style={{ marginBottom: 8 }}>
        <label style={{ flex: 1 }}>Адрес<input value={a.raw_address} onChange={set('raw_address')} /></label>
        <label>
          Район
          <select value={a.district_id || ''} onChange={set('district_id')}>
            <option value="">—</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <label>Широта<input value={a.latitude || ''} onChange={set('latitude')} /></label>
        <label>Долгота<input value={a.longitude || ''} onChange={set('longitude')} /></label>
        <label>Подъезд<input value={a.entrance || ''} onChange={set('entrance')} /></label>
        <label>Этаж<input value={a.floor || ''} onChange={set('floor')} /></label>
        <button onClick={() => saveAddress(a, isNew)}>Сохранить</button>
        <button className="secondary" onClick={() => { setEdit(null); setNewAddr(null) }}>Отмена</button>
      </div>
    )
  }

  return (
    <div>
      <h2>Клиент: {client.name}</h2>
      {error && <div className="error">{error}</div>}
      {info && <div className="success">{info}</div>}
      <div className="card">
        <p><b>Телефон:</b> {client.phone_primary}</p>
        {client.comment && <p><b>Комментарий:</b> {client.comment}</p>}
      </div>

      <div className="card">
        <h3>Адреса</h3>
        {client.addresses.map((a) =>
          edit === a.id ? (
            <AddressForm key={a.id} addr={a} isNew={false} />
          ) : (
            <div className="row" key={a.id} style={{ marginBottom: 8 }}>
              <span style={{ flex: 1 }}>
                {a.raw_address}
                {a.latitude && a.longitude && (
                  <span className="muted"> ({a.latitude}, {a.longitude})</span>
                )}
                <span className="muted">
                  {' '}— {GEOCODE_RU[a.geocode_status] || a.geocode_status}
                  {a.geocode_confidence != null && ` (точность ${a.geocode_confidence})`}
                </span>
              </span>
              <button className="secondary" onClick={() => geocode(a.id)} disabled={geocoding === a.id}>
                {geocoding === a.id ? 'Геокодинг…' : 'Геокодировать'}
              </button>
              <button className="secondary" onClick={() => setEdit(a.id)}>Изменить</button>
            </div>
          )
        )}
        {newAddr ? (
          <AddressForm addr={newAddr} isNew />
        ) : (
          <button className="secondary" onClick={() => setNewAddr({ raw_address: '' })}>+ Добавить адрес</button>
        )}
      </div>

      <div className="card">
        <h3>История заказов</h3>
        <table>
          <thead><tr><th>№</th><th>Дата</th><th>Адрес</th><th>Сумма</th><th>Статус</th></tr></thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id}>
                <td><Link to={`/orders/${o.id}`}>{o.id}</Link></td>
                <td>{o.delivery_date}</td>
                <td>{o.address_text}</td>
                <td>{o.total_amount} ₽</td>
                <td><span className={`badge ${o.status}`}>{STATUS_RU[o.status]}</span></td>
              </tr>
            ))}
            {orders.length === 0 && <tr><td colSpan="5" className="muted">Заказов не было</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}
