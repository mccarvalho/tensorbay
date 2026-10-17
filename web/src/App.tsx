import { Suspense, lazy, type ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import RequireAuth from './components/RequireAuth';
import { Spinner } from './components/ui';
import Login from './pages/Login';
import Callback from './pages/Callback';
import Customers from './pages/Customers';
import CustomerDetail from './pages/CustomerDetail';
import Sales from './pages/Sales';
import Catalog from './pages/Catalog';
import Contracts from './pages/Contracts';
import ContractDetail from './pages/ContractDetail';
import OpportunityDetail from './pages/OpportunityDetail';
import Inventory from './pages/Inventory';
import Capacity from './pages/Capacity';
import Reservations from './pages/Reservations';
import Documents from './pages/Documents';
import Admin from './pages/Admin';

// Dashboard pulls in recharts — code-split it so other routes stay lean.
const Dashboard = lazy(() => import('./pages/Dashboard'));

export default function App(): ReactElement {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/callback" element={<Callback />} />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Suspense fallback={<Spinner label="Loading dashboard…" />}><Dashboard /></Suspense>} />
        <Route path="customers" element={<Customers />} />
        <Route path="customers/:id" element={<CustomerDetail />} />
        <Route path="sales" element={<Sales />} />
        <Route path="opportunities/:id" element={<OpportunityDetail />} />
        <Route path="catalog" element={<Catalog />} />
        <Route path="contracts" element={<Contracts />} />
        <Route path="contracts/:id" element={<ContractDetail />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="capacity" element={<Capacity />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="documents" element={<Documents />} />
        <Route path="admin" element={<Admin />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
