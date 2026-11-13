const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const message = (data && data.detail) || `Eroare ${res.status}`;
    throw new Error(message);
  }
  return data;
}

export const api = {
  // public ballot
  getBallot: (uuid) => request(`/ballot/${uuid}`),
  submitVote: (uuid, payload) =>
    request(`/ballot/${uuid}/vote`, { method: "POST", body: JSON.stringify(payload) }),
  receiptUrl: (uuid) => `${BASE}/ballot/${uuid}/receipt.pdf`,

  // admin auth
  login: (username, password) =>
    request(`/admin/login`, { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request(`/admin/logout`, { method: "POST" }),
  me: () => request(`/admin/me`),

  // elections
  listElections: () => request(`/admin/elections`),
  createElection: (payload) =>
    request(`/admin/elections`, { method: "POST", body: JSON.stringify(payload) }),
  updateElection: (id, payload) =>
    request(`/admin/elections/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteElection: (id) => request(`/admin/elections/${id}`, { method: "DELETE" }),

  // voters
  generateTokens: (payload) =>
    request(`/admin/tokens/generate`, { method: "POST", body: JSON.stringify(payload) }),
  updateToken: (tokenId, payload) =>
    request(`/admin/tokens/${tokenId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteToken: (tokenId) => request(`/admin/tokens/${tokenId}`, { method: "DELETE" }),
  checklist: (electionId) => request(`/admin/elections/${electionId}/checklist`),
  tokensCsvUrl: (electionId) => `${BASE}/admin/elections/${electionId}/tokens.csv`,

  // results
  results: (electionId) => request(`/admin/elections/${electionId}/results`),

  // smtp
  getSmtp: () => request(`/admin/smtp`),
  updateSmtp: (payload) => request(`/admin/smtp`, { method: "PUT", body: JSON.stringify(payload) }),
  testSmtp: (toEmail) =>
    request(`/admin/smtp/test?to_email=${encodeURIComponent(toEmail)}`, { method: "POST" }),
};
