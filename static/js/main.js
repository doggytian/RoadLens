// 入口：登录、加载数据、连接地图/图层/质检交互。
import { api, getStoredUser, setStoredUser } from "./api.js";
import { MapView } from "./map.js";
import {
  FEATURE_TYPES, renderStyleControls, renderInspector, renderCandidateList, styleFor, setAutoColor,
} from "./layers.js";
import { QCManager, QC_CHECKS } from "./qc.js";

let map, qc;
let currentTile = null;
let currentFeatures = [];   // 当前 tile 的原始要素（用于框选/候选）

// ---------------- Toast ----------------
export function showToast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), 2200);
}

// ---------------- 登录 ----------------
function setupLogin() {
  const modal = document.getElementById("login-modal");
  const input = document.getElementById("username-input");
  const err = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");
  const existing = getStoredUser();
  if (existing) { modal.style.display = "none"; initApp(); return; }
  btn.addEventListener("click", () => {
    const u = input.value.trim();
    if (!/^[A-Za-z0-9_]{1,32}$/.test(u)) {
      err.textContent = "用户名需为 1~32 位字母/数字/下划线";
      return;
    }
    setStoredUser(u);
    modal.style.display = "none";
    initApp();
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") btn.click(); });
}

// ---------------- 初始化 ----------------
function initApp() {
  const uid = getStoredUser();
  document.getElementById("user-label").textContent = `用户：${uid}`;

  map = new MapView("map");
  qc = new QCManager(map, () => currentTile, showToast);

  map.onFeatureClick = (feature) => selectFeature(feature);
  map.onBoxSelect = (bounds) => onBoxSelect(bounds);

  renderStyleControls(document.getElementById("layer-styles"), renderCurrentTile);
  qc.renderControls(document.getElementById("qc-list"));

  document.getElementById("auto-color").addEventListener("change", (e) => {
    setAutoColor(e.target.checked); renderCurrentTile();
  });
  document.getElementById("boxselect-btn").addEventListener("click", (e) => {
    const active = !map._boxActive;
    map.setBoxSelect(active);
    e.target.style.borderColor = active ? "var(--accent)" : "";
    showToast(active ? "框选模式：拖拽矩形选择要素" : "已退出框选模式");
  });
  document.getElementById("jump-btn").addEventListener("click", onJump);
  document.getElementById("reload-btn").addEventListener("click", () => loadTile(currentTile, true));
  document.getElementById("tile-select").addEventListener("change", (e) => {
    qc.clearAll(); loadTile(e.target.value, false);
  });

  bootstrap();
}

async function bootstrap() {
  try {
    const state = await api.state();
    const sel = document.getElementById("tile-select");
    let tiles = state.tiles || [];
    if (!tiles.includes(state.sample_tile_id)) {
      // 尝试加载内置示例并刷新列表
      await api.loadSample();
      const s2 = await api.state();
      tiles = s2.tiles || [];
    }
    sel.innerHTML = "";
    tiles.forEach((t) => {
      const o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o);
    });
    if (tiles.length) loadTile(tiles.includes(state.sample_tile_id) ? state.sample_tile_id : tiles[0], false);
  } catch (e) {
    showToast(`初始化失败：${e.message}`);
  }
}

// ---------------- 数据加载与渲染 ----------------
async function loadTile(tileId, fit) {
  if (!tileId) return;
  currentTile = tileId;
  document.getElementById("tile-select").value = tileId;
  qc.clearAll();
  try {
    const data = await api.tile(tileId);
    currentFeatures = data.features || [];
    renderCurrentTile();
    fitToData();
    showToast(`已加载 ${currentFeatures.length} 个要素`);
  } catch (e) {
    showToast(`加载 tile 失败：${e.message}`);
  }
}

function renderCurrentTile() {
  // 清空三类要素图层并重绘
  Object.keys(FEATURE_TYPES).forEach((t) => map.clearGroup(t));
  map.clearHighlight();
  let bounds = null;
  currentFeatures.forEach((f) => {
    const ftype = f.properties?.feature_type;
    if (!ftype || !FEATURE_TYPES[ftype]) return;
    map.addFeature(ftype, f, () => styleFor(ftype));
  });
}

function fitToData() {
  let b = null;
  currentFeatures.forEach((f) => {
    try {
      const layer = L.geoJSON(f);
      const lb = layer.getBounds();
      if (!lb.isValid()) return;
      b = b ? b.extend(lb) : lb;
    } catch (_) { /* ignore */ }
  });
  if (b) map.fitToBounds(b);
}

// ---------------- 要素选择 ----------------
function selectFeature(feature) {
  map.highlightFeature(feature);
  renderInspector(document.getElementById("inspector-body"), feature);
}

function onBoxSelect(bounds) {
  const hits = [];
  currentFeatures.forEach((f) => {
    try {
      const layer = L.geoJSON(f);
      const lb = layer.getBounds();
      if (lb.isValid() && bounds.intersects(lb)) hits.push(f);
    } catch (_) { /* ignore */ }
  });
  if (hits.length === 1) {
    selectFeature(hits[0]);
  } else if (hits.length > 1) {
    map.clearHighlight();
    renderCandidateList(
      document.getElementById("candidate-panel"),
      document.getElementById("candidate-count"),
      document.getElementById("candidate-list"),
      hits,
      (f) => selectFeature(f)
    );
    showToast(`命中 ${hits.length} 个要素，请在左侧候选列表选择`);
  } else {
    showToast("框选区域无要素");
  }
}

// ---------------- 定位跳转 ----------------
function onJump() {
  const lon = parseFloat(document.getElementById("jump-lon").value);
  const lat = parseFloat(document.getElementById("jump-lat").value);
  if (isNaN(lon) || isNaN(lat)) { showToast("请输入有效经纬度"); return; }
  map.flyTo([lat, lon], 16);
}

setupLogin();
