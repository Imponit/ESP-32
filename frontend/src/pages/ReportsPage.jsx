import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, STATUS_RU, PAY_RU, today } from '../api.js'

export default function ReportsPage() {
  const [date, setDate] = useState(today())
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    api('/reports/daily', { params: { date } }).then(setReport).catch((e) => setError(e.message))
  }, [date])

  return (
    <div>
      <h2>Дневной отчёт</h2>
      <div className="card row">
        <label>Дата<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <span className="muted">Экспорт XLSX/CSV — в MVP-2</span>
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
                  {report.drivers.length === 0 && <tr><td colSpan="5" className="muted">Пусто</td></tr>}
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
    </div>
  )
}
