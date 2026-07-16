// 图层样式与属性/候选面板渲染。
export const FEATURE_TYPES = {
  RoadCorridor: { label: "道路走廊", color: "#3b82f6", fill: true, fillOpacity: 0.2, weight: 1 },
  Lane: { label: "车道", color: "#22c55e", fill: false, fillOpacity: 0, weight: 3 },
  ReferenceLink: { label: "参考中心线", color: "#f97316", fill: false, fillOpacity: 0, weight: 2, dashArray: "4 3" },
};

let AUTO_COLOR = true;
export function setAutoColor(v) { AUTO_COLOR = v; }

/** 返回 Leaflet 样式对象（供 map.addFeature 使用）。 */
export function styleFor(ftype) {
  const c = FEATURE_TYPES[ftype] || FEATURE_TYPES.Lane;
  if (!AUTO_COLOR) {
    return { color: "#cbd5e1", weight: 2, opacity: 0.9, fillColor: "#cbd5e1", fillOpacity: 0.1 };
  }
  return {
    color: c.color,
    weight: c.weight,
    opacity: 0.95,
    fillColor: c.color,
    fillOpacity: c.fill ? c.fillOpacity : 0,
    dashArray: c.dashArray,
  };
}

/** 渲染图层样式控制面板。onChange 在样式变化后被调用。 */
export function renderStyleControls(container, onChange) {
  container.innerHTML = "";
  for (const [key, c] of Object.entries(FEATURE_TYPES)) {
    const row = document.createElement("div");
    row.className = "style-row";
    row.innerHTML = `
      <span class="swatch" style="background:${c.color}"></span>
      <span style="width:78px">${c.label}</span>
      <input type="color" value="${c.color}" data-k="color" title="颜色" />
      <input type="range" min="1" max="8" value="${c.weight}" data-k="weight" title="线宽" />
      <span class="val">${c.weight}</span>`;
    const [colorInput, weightInput] = row.querySelectorAll("input");
    const valEl = row.querySelector(".val");
    colorInput.addEventListener("input", () => {
      c.color = colorInput.value;
      row.querySelector(".swatch").style.background = c.color;
      onChange();
    });
    weightInput.addEventListener("input", () => {
      c.weight = +weightInput.value; valEl.textContent = c.weight; onChange();
    });
    container.appendChild(row);
  }
}

/** 渲染属性面板。 */
export function renderInspector(el, feature) {
  if (!feature) { el.innerHTML = "点击地图要素查看属性"; el.className = "muted"; return; }
  const p = feature.properties || {};
  const order = ["id", "feature_type", "tile_id", "lane_count", "length_m", "name", "highway"];
  const keys = [...order.filter((k) => k in p), ...Object.keys(p).filter((k) => !order.includes(k))];
  let html = "";
  for (const k of keys) {
    let v = p[k];
    if (v === null || v === undefined) v = "";
    if (typeof v === "object") v = JSON.stringify(v);
    const long = String(v).length > 40;
    html += `<div class="kv"><span class="k">${k}</span><span class="v${long ? " long" : ""}"${long ? ` title="${v}"` : ""}>${v}</span></div>`;
  }
  el.innerHTML = html;
  el.className = "";
}

/** 渲染候选要素列表。onPick(feature) 在点击列表项时调用。 */
export function renderCandidateList(panel, countEl, listEl, features, onPick) {
  if (!features || features.length === 0) { panel.style.display = "none"; return; }
  panel.style.display = "block";
  countEl.textContent = features.length;
  listEl.innerHTML = "";
  features.forEach((f, i) => {
    const li = document.createElement("li");
    const p = f.properties || {};
    const label = p.id || `#${i}`;
    const tag = p.feature_type || "";
    li.innerHTML = `<span>${label}</span> <span class="tag">${tag}</span>`;
    li.addEventListener("click", () => onPick(f));
    listEl.appendChild(li);
  });
}
