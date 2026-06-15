import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, STATUS_RU, PAY_RU, today } from '../api.js'

export default function TodayPage() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const date = today()

  useEffect(() => {
    api(`/reports/daily`, { params: { date } }).then(setReport).catch((e) => setError(e.message))
  }, [date])

  if (error) return <div className="error">{error}</div>
  if (!report) return <p>Загрузка…</p>

  const problems = [
    ...report.completed_unpaid_order_ids.map((id) => ({ id, label: 'выполнен без оплаты' })),
    ...report.refused_orders.map((r) => ({ id: r.order_id, label: `отказ: ${r.reason || 'без причины'}` })),
  ]

  return (
    <div>
      <h2>Сводка дня — {date}</h2>
      <div className="stats">
        <div className="card">
          <div className="muted">Всего заказов</div>
          <div className="stat">{report.orders_total}</div>
        </div>
        <div className="card">
          <div className="muted">Бутыли (выполнено)</div>
          <div className="stat">
            {report.bottles_delivered.pc + report.bottles_delivered.pet}
          </div>
          <div className="muted">
            ПК {report.bottles_delivered.pc} / ПЭТ {report.bottles_delivered.pet} / помпы{' '}
            {report.bottles_delivered.pumps}
          </div>
        </div>
        {Object.entries(report.money_by_method).map(([m, v]) => (
          <div className="card" key={m}>
            <div className="muted">{PAY_RU[m] || m}</div>
            <div className="stat">{v} ₽</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Заказы по статусам</h3>
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
      </div>

      <div className="card">
        <h3>Касса по водителям</h3>
        {report.drivers.length === 0 && <p className="muted">Пока пусто.</p>}
        {report.drivers.length > 0 && (
          <table>
            <thead>
              <tr><th>Водитель</th><th>Заказов</th><th>Бутылей</th><th>Наличные</th><th>Карта/перевод</th></tr>
            </thead>
            <tbody>
              {report.drivers.map((d) => (
                <tr key={d.driver_id}>
                  <td>{d.driver_name}</td>
                  <td>{d.completed_orders}</td>
                  <td>{d.bottles}</td>
                  <td>{d.cash} ₽</td>
                  <td>{d.cashless} ₽</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Проблемные заказы</h3>
        {problems.length === 0 && <p className="muted">Нет проблемных заказов.</p>}
        <ul>
          {problems.map((p, i) => (
            <li key={i}>
              <Link to={`/orders/${p.id}`}>Заказ №{p.id}</Link> — {p.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
