import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { canManagePeople, canUseLab, homePath, isPlatformAdmin, isStaff, roleOf } from './api/types'
import { Layout } from './components/Layout'
import { useAuth } from './hooks/useAuth'
import { AssistPage } from './pages/Assist'
import { AttendancePage } from './pages/Attendance'
import { BoardPage } from './pages/Board'
import { DashboardPage } from './pages/Dashboard'
import { EnrollPage } from './pages/Enroll'
import { EventsPage } from './pages/Events'
import { IdentifyPage } from './pages/Identify'
import { KioskPage } from './pages/Kiosk'
import { LivenessPage } from './pages/Liveness'
import { LoginPage } from './pages/Login'
import { MyAttendancePage } from './pages/MyAttendance'
import { OpsDashboardPage } from './pages/OpsDashboard'
import { OrgsPage } from './pages/Orgs'
import { PeoplePage } from './pages/People'
import { PersonPage } from './pages/Person'
import { ProfilePage } from './pages/Profile'
import { ReportsPage } from './pages/Reports'
import { SchedulePage } from './pages/Schedule'
import { StaffPage } from './pages/Staff'
import { VerifyPage } from './pages/Verify'

function Guard({
  children,
  people,
  lab,
  staff,
  admin,
  platform,
  org,
}: {
  children: ReactNode
  people?: boolean
  lab?: boolean
  staff?: boolean
  admin?: boolean
  platform?: boolean
  org?: boolean
}) {
  const { user, loading, currentOrgId } = useAuth()
  if (loading) return <div className="h-full grid place-items-center text-muted">Loading Sentinel…</div>
  if (!user) return <Navigate to="/login" replace />
  if (people && !canManagePeople(user)) return <Navigate to={homePath(user)} replace />
  if (lab && !canUseLab(user)) return <Navigate to={homePath(user)} replace />
  if (staff && !isStaff(user)) return <Navigate to={homePath(user)} replace />
  if (admin && roleOf(user) !== 'admin') return <Navigate to={homePath(user)} replace />
  if (platform && !isPlatformAdmin(user)) return <Navigate to={homePath(user)} replace />
  if (org && isPlatformAdmin(user) && !currentOrgId) return <Navigate to="/orgs" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <Guard people org>
            <Layout />
          </Guard>
        }
      >
        <Route path="/" element={<OpsDashboardPage />} />
        <Route path="/people" element={<PeoplePage />} />
        <Route path="/people/:id" element={<PersonPage />} />
        <Route path="/enroll" element={<EnrollPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/assist" element={<AssistPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
      </Route>
      <Route
        element={
          <Guard lab org>
            <Layout />
          </Guard>
        }
      >
        <Route path="/lab" element={<DashboardPage />} />
        <Route path="/verify" element={<VerifyPage />} />
        <Route path="/identify" element={<IdentifyPage />} />
        <Route path="/liveness" element={<LivenessPage />} />
      </Route>
      <Route
        element={
          <Guard staff org>
            <Layout />
          </Guard>
        }
      >
        <Route path="/events" element={<EventsPage />} />
        <Route path="/kiosk" element={<KioskPage />} />
        <Route path="/board" element={<BoardPage />} />
      </Route>
      <Route
        element={
          <Guard platform>
            <Layout />
          </Guard>
        }
      >
        <Route path="/orgs" element={<OrgsPage />} />
      </Route>
      <Route
        element={
          <Guard admin org>
            <Layout />
          </Guard>
        }
      >
        <Route path="/staff" element={<StaffPage />} />
      </Route>
      <Route
        element={
          <Guard org>
            <Layout />
          </Guard>
        }
      >
        <Route path="/attendance" element={<AttendancePage />} />
        <Route path="/my-attendance" element={<MyAttendancePage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  )
}
