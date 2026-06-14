// Обёртка над fetch: JWT из localStorage, ошибки API -> исключения с detail.

const BASE = '/api'

export function getToken() {
  return localStorage.getItem('token')
}

export function setToken(token) {
  if (token) localStorage.setItem('token', token)
  else localStorage.removeItem('token')
}

export async function api(path, { method = 'GET', body, params } = {}) {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    }
  }
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (resp.status === 401) {
    setToken(null)
    window.location.hash = '#/login'
    throw new Error('Требуется вход')
  }
  const data = resp.status === 204 ? null : await resp.json().catch(() => null)
  if (!resp.ok) {
    throw new Error(data?.detail ? String(data.detail) : `Ошибка ${resp.status}`)
  }
  return data
}

export const STATUS_RU = {
  draft: 'Черновик',
  new: 'Новый',
  needs_review: 'Требует проверки',
  planned: 'Запланирован',
  assigned: 'Назначен',
  sent_to_driver: 'Отправлен водителю',
  accepted_by_driver: 'Принят водителем',
  in_progress: 'В работе',
  completed: 'Выполнен',
  failed: 'Ошибка',
  refused: 'Отказ',
  postponed: 'Перенос',
  cancelled: 'Отменён',
}

export const PART_RU = {
  any: 'Любое время',
  first_half: 'Первая половина',
  second_half: 'Вторая половина',
  exact: 'Точное окно',
}

export const PAY_RU = { cash: 'Наличные', cashless: 'Карта/перевод', unknown: 'Не известно', other: 'Другое' }

// Загрузка файла (multipart) — отдельно от JSON-обёртки api().
export async function uploadOrders(file, dryRun) {
  const url = new URL('/api/import/orders', window.location.origin)
  if (dryRun) url.searchParams.set('dry_run', 'true')
  const form = new FormData()
  form.append('file', file)
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const resp = await fetch(url, { method: 'POST', headers, body: form })
  const data = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(data?.detail ? String(data.detail) : `Ошибка ${resp.status}`)
  return data
}

export const GEOCODE_RU = {
  none: 'нет координат',
  manual: 'вручную',
  ok: 'геокодинг',
  pending: 'геокодер недоступен',
  failed: 'адрес не найден',
}

export function today() {
  return new Date().toISOString().slice(0, 10)
}
