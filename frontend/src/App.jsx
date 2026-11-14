import { Routes, Route } from "react-router-dom";
import AdminLayout from "./components/AdminLayout";
import AdminLogin from "./pages/AdminLogin";
import AdminElections from "./pages/AdminElections";
import AdminElectionDetail from "./pages/AdminElectionDetail";
import AdminSmtp from "./pages/AdminSmtp";
import AdminBallotTemplate from "./pages/AdminBallotTemplate";
import AdminChangePassword from "./pages/AdminChangePassword";
import ElectionDashboard from "./pages/ElectionDashboard";
import Home from "./pages/Home";
import VotePage from "./pages/VotePage";
import ExtendPage from "./pages/ExtendPage";

export default function App() {
  return (
    <Routes>
      {/* clean blank home page - no automatic redirect to the admin panel */}
      <Route path="/" element={<Home />} />

      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminElections />} />
        <Route path="elections/:id" element={<AdminElectionDetail />} />
        <Route path="smtp" element={<AdminSmtp />} />
        <Route path="buletin" element={<AdminBallotTemplate />} />
        <Route path="change-password" element={<AdminChangePassword />} />
      </Route>

      {/* public results dashboard: /{public_uuid}/dashboard */}
      <Route path="/:uuid/dashboard" element={<ElectionDashboard />} />

      {/* secret link sent to the APC by email: /extend/{extend_uuid} - the APC chooses how long to prolong */}
      <Route path="/extend/:token" element={<ExtendPage />} />

      {/* fixed public voting link per APC: /{nr_apc} - must stay last so it doesn't swallow /admin/* */}
      <Route path="/:nrApc" element={<VotePage />} />
    </Routes>
  );
}
