import { type ReactElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import RequireAuth from './components/RequireAuth';
import Login from './pages/Login';
import Callback from './pages/Callback';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Sales from './pages/Sales';
import Contracts from './pages/Contracts';
import Inventory from './pages/Inventory';
import Capacity from './pages/Capacity';
import Reservations from './pages/Reservations';
import Documents from './pages/Documents';
import Admin from './pages/Admin';

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
        <Route index element={<Dashboard />} />
        <Route path="customers" element={<Customers />} />
        <Route path="sales" element={<Sales />} />
        <Route path="contracts" element={<Contracts />} />
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
