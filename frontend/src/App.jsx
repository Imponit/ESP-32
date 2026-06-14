import { HashRouter, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { getToken, setToken } from './api.js'
import LoginPage from './pages/LoginPage.jsx'
import TodayPage from './pages/TodayPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import OrderPage from './pages/OrderPage.jsx'
import ClientsPage from './pages/ClientsPage.jsx'
import ClientPage from './pages/ClientPage.jsx'
import DriversPage from './pages/DriversPage.jsx'
import PlanningPage from './pages/PlanningPage.jsx'
import ReportsPage from './pages/ReportsPage.jsx'
import EventsPage from './pages/EventsPage.jsx'
import IncomingPage from './pages/IncomingPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'

function Layout({ children }) {
  const navigate = useNavigate()
  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>💧 CRM доставки воды</h1>
        <nav>
          <NavLink to="/today">Сегодня</NavLink>
          <NavLink to="/orders">Заказы</NavLink>
          <NavLink to="/clients">Клиенты</NavLink>
          <NavLink to="/drivers">Водители</NavLink>
          <NavLink to="/planning">Планирование</NavLink>
          <NavLink to="/incoming">Входящие</NavLink>
          <NavLink to="/reports">Отчёты</NavLink>
          <NavLink to="/events">Журнал событий</NavLink>
          <NavLink to="/settings">Настройки</NavLink>
        </nav>
        <button
          className="secondary logout"
          onClick={() => {
            setToken(null)
            navigate('/login')
          }}
        >
          Выйти
        </button>
      </aside>
      <main className="content">{children}</main>
    </div>
  )
}

function Protected({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<Protected><TodayPage /></Protected>} />
        <Route path="/orders" element={<Protected><OrdersPage /></Protected>} />
        <Route path="/orders/:id" element={<Protected><OrderPage /></Protected>} />
        <Route path="/clients" element={<Protected><ClientsPage /></Protected>} />
        <Route path="/clients/:id" element={<Protected><ClientPage /></Protected>} />
        <Route path="/drivers" element={<Protected><DriversPage /></Protected>} />
        <Route path="/planning" element={<Protected><PlanningPage /></Protected>} />
        <Route path="/incoming" element={<Protected><IncomingPage /></Protected>} />
        <Route path="/reports" element={<Protected><ReportsPage /></Protected>} />
        <Route path="/events" element={<Protected><EventsPage /></Protected>} />
        <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      </Routes>
    </HashRouter>
  )
}
