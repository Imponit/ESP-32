import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadReport, STATUS_RU, PAY_RU, today } from '../api.js'

function weekAgo() {
  const d = new Date()
  d.setDate(d.getDate() - 6)
  return d.toISOString().slice(0, 10)
}

function Analytics() {
  const [from, setFrom] = useState(weekAgo())
  const [to, setTo] = useState(today())
  const [a, setA] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    setError('')
    try {
      setA(await api('/reports/analytics', { params: { date_from: from, date_to: to } }))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="card">
      <h3>Аналитика за период</h3>
      <div className="row">
        <label>С<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>По<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <button onClick={load}>Построить</button>
      </div>
      {error && <div className="error">{error}</div>}
      {a && (
        <>
          <div className="stats" style={{ marginTop: 12 }}>
            <div className="card"><div className="muted">Заказов</div><div className="stat">{a.orders_total}</div></div>
            <div className="card"><div className="muted">Выполнено</div><div className="stat">{a.completed}</div><div className="muted">{a.fill_rate}%</div></div>
            <div className="card"><div className="muted">Отказы/ошибки</div><div className="stat">{a.refused + a.failed}</div><div className="muted">отказ {a.refusal_rate}% / ошибка {a.failure_rate}%</div></div>
            <div className="card"><div className="muted">Выручка собрана</div><div className="stat">{a.revenue_collected} ₽</div></div>
            <div className="card"><div className="muted">Средний чек</div><div className="stat">{a.avg_order_value} ₽</div></div>
            <div className="card"><div className="muted">Бутыли</div><div className="stat">{a.bottles.total}</div><div className="muted">ПК {a.bottles.pc} / ПЭТ {a.bottles.pet} / помпы {a.bottles.pumps}</div></div>
          </div>

          <div className="grid2" style={{ marginTop: 12 }}>
            <div className="card">
              <h4>По дням</h4>
              <table>
                <thead><tr><th>Дата</th><th>Заказов</th><th>Выполнено</th><th>Бутыли</th><th>Выручка</th></tr></thead>
                <tbody>
                  {a.by_day.map((d) => (
                    <tr key={d.date}><td>{d.date}</td><td>{d.orders}</td><td>{d.completed}</td><td>{d.bottles}</td><td>{d.revenue} ₽</td></tr>
                  ))}
                  {a.by_day.length === 0 && <tr><td colSpan="5" className="muted">Нет данных</td></tr>}
                </tbody>
              </table>
              <h4>Топ товаров</h4>
              <table>
                <thead><tr><th>Товар</th><th>Кол-во</th><th>Сумма</th></tr></thead>
                <tbody>
                  {a.top_products.map((p) => (
                    <tr key={p.name}><td>{p.name}</td><td>{p.qty}</td><td>{p.amount} ₽</td></tr>
                  ))}
                  {a.top_products.length === 0 && <tr><td colSpan="3" className="muted">Нет данных</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h4>По водителям</h4>
              <table>
                <thead><tr><th>Водитель</th><th>Вып.</th><th>Бут.</th><th>Нал.</th><th>Карта</th><th>Ош./отк.</th></tr></thead>
                <tbody>
                  {a.by_driver.map((d) => (
                    <tr key={d.driver_id}><td>{d.driver_name}</td><td>{d.completed}</td><td>{d.bottles}</td><td>{d.cash} ₽</td><td>{d.cashless} ₽</td><td>{d.failed}/{d.refused}</td></tr>
                  ))}
                  {a.by_driver.length === 0 && <tr><td colSpan="6" className="muted">Нет данных</td></tr>}
                </tbody>
              </table>
              <h4>По районам</h4>
              <table>
                <thead><tr><th>Район</th><th>Заказов</th><th>Выполнено</th><th>Бутыли</th><th>Выручка</th></tr></thead>
                <tbody>
                  {a.by_district.map((d) => (
                    <tr key={d.district_id ?? 'none'}><td>{d.district_name}</td><td>{d.orders}</td><td>{d.completed}</td><td>{d.bottles}</td><td>{d.revenue} ₽</td></tr>
                  ))}
                  {a.by_district.length === 0 && <tr><td colSpan="5" className="muted">Нет данных</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function DriverScores() {
  const [from, setFrom] = useState(weekAgo())
  const [to, setTo] = useState(today())
  const [scores, setScores] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  async function load() {
    setError('')
    setSaved('')
    try {
      setScores(await api('/drivers/scores', { params: { date_from: from, date_to: to } }))
    } catch (e) {
      setError(e.message)
    }
  }

  async function save() {
    setError('')
    try {
      const r = await api('/drivers/scores/save', { method: 'POST', params: { date_from: from, date_to: to } })
      setSaved(`Сохранён снимок: ${r.saved} водителей за ${r.period_from}…${r.period_to}.`)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="card">
      <h3>Баллы водителей за период</h3>
      <div className="row">
        <label>С<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>По<input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <button onClick={load}>Посчитать</button>
        {scores && <button className="secondary" onClick={save}>Сохранить снимок</button>}
      </div>
      {error && <div className="error">{error}</div>}
      {saved && <div className="success">{saved}</div>}
      {scores && (
        <table style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Водитель</th><th>Баллы</th><th>Выполнено</th><th>Бонус-дни</th>
              <th>Просрочки</th><th>Ошибки без причины</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((s) => (
              <tr key={s.driver_id}>
                <td>{s.driver_name}</td>
                <td><b>{s.points}</b></td>
                <td>{s.breakdown.completed}</td>
                <td>{s.breakdown.bonus_days}</td>
                <td>{s.breakdown.late_exact}</td>
                <td>{s.breakdown.failed_no_reason}</td>
              </tr>
            ))}
            {scores.length === 0 && <tr><td colSpan="6" className="muted">Нет данных за период</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function ReportsPage() {
  const [date, setDate] = useState(today())
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  const loadReport = useCallback(() => {
    setError('')
    api('/reports/daily', { params: { date } }).then(setReport).catch((e) => setError(e.message))
  }, [date])

  useEffect(loadReport, [loadReport])

  async function exportFile(format) {
    setError('')
    try {
      await downloadReport(date, format)
    } catch (e) {
      setError(e.message)
    }
  }

  async function toggleHandover(driver) {
    setError('')
    try {
      if (driver.cash_handed_over) {
        await api('/reports/cash-handover', { method: 'DELETE', params: { driver_id: driver.driver_id, date } })
      } else {
        await api('/reports/cash-handover', { method: 'POST', body: { driver_id: driver.driver_id, date, amount: String(driver.cash) } })
      }
      loadReport()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <h2>Дневной отчёт</h2>
      <div className="card row">
        <label>Дата<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <button className="secondary" onClick={() => exportFile('xlsx')}>Экспорт XLSX</button>
        <button className="secondary" onClick={() => exportFile('csv')}>Экспорт CSV</button>
      </div>
      {error && <div className="error">{error}</div>}
      {report && (
        <>
          <div className="grid2">
            <div className="card">
              <h3>Заказы по статусам (всего {report.orders_total})</h3>
              <table>
                <tbody>
                  {Object.entries(report.orders_by_status).map(([s, n]) => (
                    <tr key={s}>
                      <td><span className={`badge ${s}`}>{STATUS_RU[s] || s}</span></td>
                      <td>{n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Бутыли (по выполненным)</h3>
              <p>
                Поликарбонат: {report.bottles_delivered.pc}, ПЭТ: {report.bottles_delivered.pet},
                помпы: {report.bottles_delivered.pumps}
              </p>
              <h3>Деньги по способам оплаты</h3>
              <table>
                <tbody>
                  {Object.entries(report.money_by_method).map(([m, v]) => (
                    <tr key={m}><td>{PAY_RU[m] || m}</td><td>{v} ₽</td></tr>
                  ))}
                  {Object.keys(report.money_by_method).length === 0 && (
                    <tr><td className="muted">Оплат не было</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="card">
              <h3>Касса по водителям</h3>
              <table>
                <thead>
                  <tr><th>Водитель</th><th>Заказов</th><th>Бутылей</th><th>Наличные</th><th>Карта/перевод</th><th>Касса сдана</th></tr>
                </thead>
                <tbody>
                  {report.drivers.map((d) => (
                    <tr key={d.driver_id}>
                      <td>{d.driver_name}</td>
                      <td>{d.completed_orders}</td>
                      <td>{d.bottles}</td>
                      <td>{d.cash} ₽</td>
                      <td>{d.cashless} ₽</td>
                      <td>
                        {d.cash_handed_over
                          ? <>✅ {d.handover_amount ? `${d.handover_amount} ₽ ` : ''}<button className="secondary" onClick={() => toggleHandover(d)}>Снять</button></>
                          : <button onClick={() => toggleHandover(d)}>Отметить</button>}
                      </td>
                    </tr>
                  ))}
                  {report.drivers.length === 0 && <tr><td colSpan="6" className="muted">Пусто</td></tr>}
                </tbody>
              </table>
              <h3>Отказы</h3>
              <ul>
                {report.refused_orders.map((r) => (
                  <li key={r.order_id}>
                    <Link to={`/orders/${r.order_id}`}>№{r.order_id}</Link> — {r.reason || 'без причины'}
                  </li>
                ))}
                {report.refused_orders.length === 0 && <li className="muted">Нет</li>}
              </ul>
              <h3>Выполнены без оплаты</h3>
              <ul>
                {report.completed_unpaid_order_ids.map((id) => (
                  <li key={id}><Link to={`/orders/${id}`}>Заказ №{id}</Link></li>
                ))}
                {report.completed_unpaid_order_ids.length === 0 && <li className="muted">Нет</li>}
              </ul>
            </div>
          </div>
        </>
      )}
      <Analytics />
      <DriverScores />
    </div>
  )
}
