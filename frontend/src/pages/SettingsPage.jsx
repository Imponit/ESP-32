import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SettingsPage() {
  const [districts, setDistricts] = useState([])
  const [settings, setSettings] = useState([])
  const [newDistrict, setNewDistrict] = useState('')
  const [maxPoints, setMaxPoints] = useState('')
  const [geoThreshold, setGeoThreshold] = useState('')
  const [optimizer, setOptimizer] = useState('greedy')
  const [rules, setRules] = useState(null)
  const [products, setProducts] = useState([])
  const [newProduct, setNewProduct] = useState({ name: '', kind: 'other', unit_price: '0' })
  const [message, setMessage] = useState(null)

  const KIND_RU = { bottle_pc: 'Бутыль ПК', bottle_pet: 'Бутыль ПЭТ', pump: 'Помпа', other: 'Прочее' }

  const DEFAULT_RULES = {
    completed: 1, day_no_failed_bonus: 2, failed_no_reason: -2, late_exact: -1, refused_not_driver_fault: 0,
  }
  const RULE_LABELS = {
    completed: 'За выполненный заказ',
    day_no_failed_bonus: 'Бонус за день без ошибок',
    failed_no_reason: 'Ошибка без причины',
    late_exact: 'Просрочка точного окна',
    refused_not_driver_fault: 'Отказ не по вине водителя',
  }

  const load = useCallback(async () => {
    setDistricts(await api('/districts'))
    setProducts(await api('/products'))
    const s = await api('/settings')
    setSettings(s)
    const mp = s.find((x) => x.key === 'max_route_points')
    setMaxPoints(mp ? String(mp.value) : '9')
    const gt = s.find((x) => x.key === 'geocode_confidence_threshold')
    setGeoThreshold(gt ? String(gt.value) : '0.7')
    const ro = s.find((x) => x.key === 'route_optimizer')
    setOptimizer(ro ? String(ro.value) : 'greedy')
    const sr = s.find((x) => x.key === 'scoring_rules')
    setRules({ ...DEFAULT_RULES, ...(sr ? sr.value : {}) })
  }, [])

  useEffect(() => {
    load().catch((e) => setMessage({ type: 'error', text: e.message }))
  }, [load])

  async function addDistrict(e) {
    e.preventDefault()
    try {
      await api('/districts', { method: 'POST', body: { name: newDistrict } })
      setNewDistrict('')
      load()
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  async function toggleDistrict(d) {
    await api(`/districts/${d.id}`, { method: 'PATCH', body: { is_active: !d.is_active } })
    load()
  }

  async function saveSetting(key, value) {
    setMessage(null)
    try {
      await api(`/settings/${key}`, { method: 'PUT', body: { value } })
      setMessage({ type: 'success', text: 'Сохранено.' })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message + ' (нужна роль admin)' })
    }
  }

  async function addProduct(e) {
    e.preventDefault()
    setMessage(null)
    try {
      await api('/products', {
        method: 'POST',
        body: { ...newProduct, unit_price: String(newProduct.unit_price) },
      })
      setNewProduct({ name: '', kind: 'other', unit_price: '0' })
      load()
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  async function patchProduct(id, patch) {
    try {
      await api(`/products/${id}`, { method: 'PATCH', body: patch })
      load()
    } catch (e) {
      setMessage({ type: 'error', text: e.message })
    }
  }

  return (
    <div>
      <h2>Настройки</h2>
      {message && <div className={message.type}>{message.text}</div>}
      <div className="grid2">
        <div className="card">
          <h3>Районы</h3>
          <table>
            <thead><tr><th>Название</th><th>Активен</th><th></th></tr></thead>
            <tbody>
              {districts.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.is_active ? 'да' : <span className="error">нет</span>}</td>
                  <td>
                    <button className="secondary" onClick={() => toggleDistrict(d)}>
                      {d.is_active ? 'Отключить' : 'Включить'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <form className="row" style={{ marginTop: 10 }} onSubmit={addDistrict}>
            <label>Новый район<input value={newDistrict} onChange={(e) => setNewDistrict(e.target.value)} required /></label>
            <button type="submit">Добавить</button>
          </form>
        </div>
        <div className="card">
          <h3>Параметры</h3>
          <div className="row">
            <label>
              Лимит точек в пакете
              <input type="number" min="1" max="20" value={maxPoints} onChange={(e) => setMaxPoints(e.target.value)} />
            </label>
            <button onClick={() => saveSetting('max_route_points', Number(maxPoints))}>Сохранить</button>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <label>
              Порог точности геокодера (0–1)
              <input type="number" min="0" max="1" step="0.05" value={geoThreshold} onChange={(e) => setGeoThreshold(e.target.value)} />
            </label>
            <button onClick={() => saveSetting('geocode_confidence_threshold', Number(geoThreshold))}>Сохранить</button>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <label>
              Оптимизатор маршрута
              <select value={optimizer} onChange={(e) => setOptimizer(e.target.value)}>
                <option value="simple">Без оптимизации (порядок диспетчера)</option>
                <option value="greedy">Ближайший сосед (greedy)</option>
              </select>
            </label>
            <button onClick={() => saveSetting('route_optimizer', optimizer)}>Сохранить</button>
          </div>
          <p className="muted">
            Применяется при формировании пакета с галкой «Оптимизировать порядок точек».
          </p>
          <p className="muted">
            Ниже порога геокодинг считается неточным, и заказы адреса уходят на проверку (needs_review).
          </p>

          <h3 style={{ marginTop: 16 }}>Баллы водителей (коэффициенты)</h3>
          {rules && Object.keys(DEFAULT_RULES).map((k) => (
            <div className="row" key={k} style={{ marginBottom: 6 }}>
              <label style={{ flex: 1 }}>
                {RULE_LABELS[k]}
                <input
                  type="number"
                  value={rules[k]}
                  onChange={(e) => setRules((r) => ({ ...r, [k]: e.target.value }))}
                />
              </label>
            </div>
          ))}
          {rules && (
            <button onClick={() => saveSetting('scoring_rules', Object.fromEntries(Object.entries(rules).map(([k, v]) => [k, Number(v)])))}>
              Сохранить правила баллов
            </button>
          )}
          <p className="muted" style={{ marginTop: 16 }}>
            Прочие настройки: {settings.filter((s) => !['max_route_points', 'geocode_confidence_threshold', 'scoring_rules', 'route_optimizer'].includes(s.key)).map((s) => `${s.key}=${JSON.stringify(s.value)}`).join(', ') || '—'}
          </p>
        </div>
      </div>

      <div className="card">
        <h3>Каталог товаров и услуг</h3>
        <table>
          <thead><tr><th>Название</th><th>Вид</th><th>Цена, ₽</th><th>Активен</th><th></th></tr></thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{KIND_RU[p.kind] || p.kind}</td>
                <td>
                  <input
                    type="number" step="0.01" min="0" defaultValue={p.unit_price} style={{ width: 90 }}
                    onBlur={(e) => e.target.value !== String(p.unit_price) && patchProduct(p.id, { unit_price: e.target.value })}
                  />
                </td>
                <td>{p.is_active ? 'да' : <span className="error">нет</span>}</td>
                <td>
                  <button className={p.is_active ? 'danger' : ''} onClick={() => patchProduct(p.id, { is_active: !p.is_active })}>
                    {p.is_active ? 'Отключить' : 'Включить'}
                  </button>
                </td>
              </tr>
            ))}
            {products.length === 0 && <tr><td colSpan="5" className="muted">Каталог пуст</td></tr>}
          </tbody>
        </table>
        <form className="row" style={{ marginTop: 10 }} onSubmit={addProduct}>
          <label>Название<input value={newProduct.name} onChange={(e) => setNewProduct((p) => ({ ...p, name: e.target.value }))} required /></label>
          <label>
            Вид
            <select value={newProduct.kind} onChange={(e) => setNewProduct((p) => ({ ...p, kind: e.target.value }))}>
              {Object.entries(KIND_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>Цена, ₽<input type="number" step="0.01" min="0" value={newProduct.unit_price} onChange={(e) => setNewProduct((p) => ({ ...p, unit_price: e.target.value }))} /></label>
          <button type="submit">Добавить товар</button>
        </form>
        <p className="muted">
          Вид «Бутыль ПК/ПЭТ/Помпа» связывает товар с количеством в заказе и ценой; при создании
          заказа позиции и сумма берутся из каталога.
        </p>
      </div>
    </div>
  )
}
