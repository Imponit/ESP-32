import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, STATUS_RU, PART_RU, today } from '../api.js'

export default function PlanningPage() {
  const [date, setDate] = useState(today())
  const [filters, setFilters] = useState({ district_id: '', part: '', status: '' })
  const [unassigned, setUnassigned] = useState([])
  const [assigned, setAssigned] = useState([])
  const [drivers, setDrivers] = useState([])
  const [districts, setDistricts] = useState([])
  const [batches, setBatches] = useState([])
  const [selDriver, setSelDriver] = useState('')
  const [selOrders, setSelOrders] = useState([])
  const [dayPart, setDayPart] = useState('any')
  const [batchDistrict, setBatchDistrict] = useState('')
  const [message, setMessage] = useState(null) // {type, text}

  const load = useCallback(async () => {
    const params = { date, limit: 500 }
    const all = (await api('/orders', { params })).items
    const f = (o) =>
      (!filters.district_id || o.district_id === Number(filters.district_id)) &&
      (!filters.part || o.time_window_type === filters.part) &&
      (!filters.status || o.status === filters.status)
    setUnassigned(all.filter((o) => ['new', 'needs_review', 'planned'].includes(o.status)).filter(f))
    setAssigned(all.filter((o) => o.status === 'assigned' && !o.route_batch_id))
    setDrivers(await api('/drivers'))
    setDistricts(await api('/districts'))
    setBatches(await api('/route-batches', { params: { date } }))
  }, [date, filters])

  useEffect(() => {
    load().catch((e) => setMessage({ type: 'error', text: e.message }))
  }, [load])

  function driverLoad(driverId) {
    const all = [...assigned, ...batches.flatMap((b) => b.orders)].filter(
      (o) => o.assigned_driver_id === driverId
    )
    return {
      orders: all.length,
      bottles: all.reduce((s, o) => s + o.bottles_pc_qty + o.bottles_pet_qty, 0),
    }
  }

  async function assignTo(orderId, driverId) {
    setMessage(null)
    try {
      await api(`/orders/${orderId}/assign-driver`, { method: 'POST', body: { driver_id: driverId } })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  async function createBatch() {
    setMessage(null)
    try {
      const resp = await api('/planning/batches', {
        method: 'POST',
        body: {
          date,
          day_part: dayPart,
          district_id: batchDistrict ? Number(batchDistrict) : null,
          driver_id: Number(selDriver),
          order_ids: selOrders,
        },
      })
      setSelOrders([])
      setMessage({
        type: resp.warnings.length ? 'error' : 'success',
        text: `Пакет №${resp.batch.id} создан. ${resp.warnings.join(' ')}`,
      })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  async function sendBatch(batchId) {
    setMessage(null)
    try {
      await api(`/dispatch/send/${batchId}`, { method: 'POST' })
      setMessage({ type: 'success', text: `Пакет №${batchId} отправлен водителю (в dry-run — в лог backend).` })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  const setF = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))
  const toggleOrder = (id) =>
    setSelOrders((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const batchCandidates = assigned.filter(
    (o) => selDriver && o.assigned_driver_id === Number(selDriver)
  )

  return (
    <div>
      <h2>Планирование</h2>
      <div className="card row">
        <label>Дата<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <label>
          Район
          <select value={filters.district_id} onChange={setF('district_id')}>
            <option value="">Все</option>
            {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
        <label>
          Часть дня
          <select value={filters.part} onChange={setF('part')}>
            <option value="">Любая</option>
            {Object.entries(PART_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>
          Статус
          <select value={filters.status} onChange={setF('status')}>
            <option value="">Все</option>
            <option value="new">Новый</option>
            <option value="needs_review">Требует проверки</option>
            <option value="planned">Запланирован</option>
          </select>
        </label>
      </div>
      {message && <div className={message.type}>{message.text}</div>}

      <div className="grid2">
        <div className="card">
          <h3>Нераспределённые заказы</h3>
          <table>
            <thead><tr><th>№</th><th>Адрес</th><th>Бут.</th><th>Статус</th><th>Назначить</th></tr></thead>
            <tbody>
              {unassigned.map((o) => (
                <tr key={o.id}>
                  <td><Link to={`/orders/${o.id}`}>{o.id}</Link></td>
                  <td>{o.address_text}</td>
                  <td>{o.bottles_pc_qty + o.bottles_pet_qty}</td>
                  <td><span className={`badge ${o.status}`}>{STATUS_RU[o.status]}</span></td>
                  <td className="row">
                    <select id={`drv-${o.id}`} defaultValue="">
                      <option value="" disabled>водитель…</option>
                      {drivers.filter((d) => d.is_active).map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => {
                        const v = document.getElementById(`drv-${o.id}`).value
                        if (v) assignTo(o.id, Number(v))
                      }}
                    >
                      Назначить
                    </button>
                  </td>
                </tr>
              ))}
              {unassigned.length === 0 && <tr><td colSpan="5" className="muted">Пусто</td></tr>}
            </tbody>
          </table>
        </div>

        <div>
          <div className="card">
            <h3>Водители и загрузка</h3>
            <table>
              <thead><tr><th>Водитель</th><th>Заказов</th><th>Бутылей / вместимость</th></tr></thead>
              <tbody>
                {drivers.filter((d) => d.is_active).map((d) => {
                  const l = driverLoad(d.id)
                  const over = d.capacity_bottles && l.bottles > d.capacity_bottles
                  return (
                    <tr key={d.id}>
                      <td>{d.name}</td>
                      <td>{l.orders}</td>
                      <td className={over ? 'error' : ''}>{l.bottles} / {d.capacity_bottles}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>Сформировать пакет</h3>
            <div className="row">
              <label>
                Водитель
                <select value={selDriver} onChange={(e) => { setSelDriver(e.target.value); setSelOrders([]) }}>
                  <option value="">—</option>
                  {drivers.filter((d) => d.is_active).map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Часть дня
                <select value={dayPart} onChange={(e) => setDayPart(e.target.value)}>
                  <option value="any">Любая</option>
                  <option value="first_half">Первая половина</option>
                  <option value="second_half">Вторая половина</option>
                </select>
              </label>
              <label>
                Район
                <select value={batchDistrict} onChange={(e) => setBatchDistrict(e.target.value)}>
                  <option value="">—</option>
                  {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </label>
            </div>
            {selDriver && (
              <>
                <p className="muted">Назначенные заказы (порядок выбора = порядок маршрута, до 9):</p>
                {batchCandidates.map((o) => (
                  <label key={o.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <input
                      type="checkbox"
                      checked={selOrders.includes(o.id)}
                      onChange={() => toggleOrder(o.id)}
                    />
                    №{o.id} {o.address_text} ({o.bottles_pc_qty + o.bottles_pet_qty} бут.)
                    {selOrders.includes(o.id) && <b>#{selOrders.indexOf(o.id) + 1}</b>}
                  </label>
                ))}
                {batchCandidates.length === 0 && <p className="muted">Нет назначенных заказов вне пакетов.</p>}
                <p>
                  <button disabled={!selOrders.length} onClick={createBatch}>
                    Сформировать пакет ({selOrders.length})
                  </button>
                </p>
              </>
            )}
          </div>

          <div className="card">
            <h3>Пакеты на {date}</h3>
            {batches.map((b) => (
              <div key={b.id} style={{ borderBottom: '1px solid #e6ecf2', paddingBottom: 8, marginBottom: 8 }}>
                <p>
                  <b>Пакет №{b.id}</b> — {drivers.find((d) => d.id === b.driver_id)?.name},{' '}
                  {PART_RU[b.day_part]}, статус: {b.status}
                  {b.route_url && <> — <a href={b.route_url} target="_blank" rel="noreferrer">маршрут</a></>}
                </p>
                <ul className="muted">
                  {b.orders.map((o) => (
                    <li key={o.id}>
                      {o.route_position}. №{o.id} {o.address_text} —{' '}
                      <span className={`badge ${o.status}`}>{STATUS_RU[o.status]}</span>
                    </li>
                  ))}
                </ul>
                {b.status === 'draft' && (
                  <button onClick={() => sendBatch(b.id)}>Отправить водителю</button>
                )}
              </div>
            ))}
            {batches.length === 0 && <p className="muted">Пакетов нет.</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
