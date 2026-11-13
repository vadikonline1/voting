import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function AdminLayout() {
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .me()
      .then((data) => setUsername(data.username))
      .catch(() => navigate("/admin/login", { replace: true, state: { from: location.pathname } }))
      .finally(() => setChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogout() {
    await api.logout();
    navigate("/admin/login");
  }

  if (checking) return <div className="center-page">Se verifică autentificarea...</div>;

  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <h2>Sistem de Vot</h2>
        <nav>
          <NavLink to="/admin" end>
            Alegeri &amp; conținut
          </NavLink>
          <NavLink to="/admin/smtp">Setări SMTP</NavLink>
        </nav>
        <div className="admin-nav-footer">
          <span>{username}</span>
          <button className="btn-link" onClick={handleLogout}>
            Deconectare
          </button>
        </div>
      </aside>
      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  );
}
