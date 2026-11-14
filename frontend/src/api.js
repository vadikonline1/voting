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
    const detail = data && data.detail;
    let message = `Eroare ${res.status}`;
    if (typeof detail === "string" && detail) {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((item) => (item && item.msg) || String(item)).join("; ");
    }
    throw new Error(message);
  }
  return data;
}

export const api = {
  // public ballot: fixed link /{nr_apc}
  getApcBallot: (nrApc) => request(`/ballot/apc/${encodeURIComponent(nrApc)}`),
  submitApcVote: (nrApc, payload) =>
    request(`/ballot/apc/${encodeURIComponent(nrApc)}/vote`, { method: "POST", body: JSON.stringify(payload) }),

  // public results dashboard
  publicResults: (publicUuid) => request(`/public/results/${publicUuid}`),
  getExtension: (token) => request(`/extend/${encodeURIComponent(token)}`),
  sendLinks: (electionId) => request(`/admin/elections/${electionId}/send-links`, { method: "POST" }),
  voteDetail: (electionId, tokenId) => request(`/admin/elections/${electionId}/votes/${tokenId}`),
  getBallotTemplate: () => request(`/admin/ballot-template`),
  saveBallotTemplate: (payload) => request(`/admin/ballot-template`, { method: "PUT", body: JSON.stringify(payload) }),
  previewBallotTemplate: (payload) =>
    request(`/admin/ballot-template/preview`, { method: "POST", body: JSON.stringify(payload) }),
  extendVote: (token, days) =>
    request(`/extend/${encodeURIComponent(token)}`, { method: "POST", body: JSON.stringify({ days }) }),

  // admin auth
  login: (username, password) =>
    request(`/admin/login`, { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => request(`/admin/logout`, { method: "POST" }),
  me: () => request(`/admin/me`),
  changePassword: (currentPassword, newPassword) =>
    request(`/admin/change-password`, {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  // elections
  listElections: () => request(`/admin/elections`),
  createElection: (payload) =>
    request(`/admin/elections`, { method: "POST", body: JSON.stringify(payload) }),
  updateElection: (id, payload) =>
    request(`/admin/elections/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteElection: (id) => request(`/admin/elections/${id}`, { method: "DELETE" }),

  // voters
  updateToken: (tokenId, payload) =>
    request(`/admin/tokens/${tokenId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteToken: (tokenId) => request(`/admin/tokens/${tokenId}`, { method: "DELETE" }),
  checklist: (electionId) => request(`/admin/elections/${electionId}/checklist`),
  tokensCsvUrl: (electionId) => `${BASE}/admin/elections/${electionId}/tokens.csv`,

  // prolong the vote (new end date; expiry reminders restart)
  extendElection: (id, endIso) =>
    request(`/admin/elections/${id}/extend?end_date=${encodeURIComponent(endIso)}`, { method: "POST" }),

  // email log: what was sent, to whom, with headers
  emailLog: (id) => request(`/admin/elections/${id}/emails`),

  // results
  results: (electionId) => request(`/admin/elections/${electionId}/results`),
  sendResults: (electionId, final = false) =>
    request(`/admin/elections/${electionId}/send-results?final=${final ? "true" : "false"}`, {
      method: "POST",
    }),

  // smtp
  getSmtp: () => request(`/admin/smtp`),
  updateSmtp: (payload) => request(`/admin/smtp`, { method: "PUT", body: JSON.stringify(payload) }),
  testSmtp: (toEmail) =>
    request(`/admin/smtp/test?to_email=${encodeURIComponent(toEmail)}`, { method: "POST" }),
};
