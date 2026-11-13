import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function AdminLayout() {
  const [checking, setChecking] = useState(true);
  const [username, setUsername] = useState("");
  const [mustChange, setMustChange] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setUsername(data.username);
        setMustChange(!!data.must_change_password);
      })
      .catch(() =>
        navigate("/admin/login", { replace: true, state: { from: location.pathname } })
      )
      .finally(() => setChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogout() {
    await api.logout();
    navigate("/admin/login");
  }

  if (checking) return <div className="center-page">Se verifică autentificarea...</div>;

  if (mustChange && location.pathname !== "/admin/change-password") {
    return <Navigate to="/admin/change-password" replace />;
  }

  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <h2>Sistem de Vot</h2>
        <nav>
          {mustChange ? (
            <NavLink to="/admin/change-password">Schimbă parola</NavLink>
          ) : (
            <>
              <NavLink to="/admin" end>
                Alegeri &amp; conținut
              </NavLink>
              <NavLink to="/admin/smtp">Setări SMTP</NavLink>
              <NavLink to="/admin/change-password">Schimbă parola</NavLink>
            </>
          )}
        </nav>
        <div className="admin-nav-footer">
          <span>{username}</span>
          <button className="btn-link" onClick={handleLogout}>
            Deconectare
          </button>
        </div>
      </aside>
      <main className="admin-content">
        <Outlet context={{ mustChangePassword: mustChange, onPasswordChanged: () => setMustChange(false) }} />
      </main>
    </div>
  );
}
