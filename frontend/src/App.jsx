import { Routes, Route, Navigate } from "react-router-dom";
import AdminLayout from "./components/AdminLayout";
import AdminLogin from "./pages/AdminLogin";
import AdminElections from "./pages/AdminElections";
import AdminElectionDetail from "./pages/AdminElectionDetail";
import AdminSmtp from "./pages/AdminSmtp";
import AdminChangePassword from "./pages/AdminChangePassword";
import VotePage from "./pages/VotePage";

export default function App() {
  return (
    <Routes>
      {/* no public homepage is needed - root goes straight to the admin login */}
      <Route path="/" element={<Navigate to="/admin" replace />} />

      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminElections />} />
        <Route path="elections/:id" element={<AdminElectionDetail />} />
        <Route path="smtp" element={<AdminSmtp />} />
        <Route path="change-password" element={<AdminChangePassword />} />
      </Route>

      {/* public ballot links: /{uuid} - must stay last so it doesn't swallow /admin/* */}
      <Route path="/:uuid" element={<VotePage />} />
    </Routes>
  );
}
