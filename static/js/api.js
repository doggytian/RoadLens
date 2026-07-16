// 与后端通信的轻量封装：统一携带 X-User-Id 头。
const USER_KEY = "roadlens_user";

export function getStoredUser() { return localStorage.getItem(USER_KEY) || ""; }
export function setStoredUser(u) { localStorage.setItem(USER_KEY, u); }

function headers() {
  return { "X-User-Id": getStoredUser() || "" };
}

async function jget(url) {
  const r = await fetch(url, { headers: headers() });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).error || msg; } catch (_) { /* ignore */ }
    throw new Error(msg || `HTTP ${r.status}`);
  }
  return r.json();
}

export const api = {
  state: () => jget("/api/data/state"),
  loadSample: () => fetch("/api/data/load_sample", { method: "POST", headers: headers() }).then(r => r.json()),
  tile: (id) => jget(`/api/tile/${encodeURIComponent(id)}`),
  qc: (id, check) => jget(`/api/tile/${encodeURIComponent(id)}/qc/${encodeURIComponent(check)}`),
  feature: (id, fid) => jget(`/api/tile/${encodeURIComponent(id)}/feature/${encodeURIComponent(fid)}`),
};
