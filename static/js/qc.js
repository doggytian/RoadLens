// 质检图层管理：构建控制项、按需拉取并叠加问题要素。
import { api } from "./api.js";

export const QC_CHECKS = [
  { key: "corridor_width", label: "走廊宽度异常", color: "#f59e0b" },
  { key: "buffer_break", label: "缓冲断裂", color: "#ef4444" },
  { key: "centerline_coverage", label: "中心线覆盖", color: "#3b82f6" },
  { key: "overlap", label: "压盖检测", color: "#ec4899" },
  { key: "diamond_topology", label: "菱形拓扑", color: "#8b5cf6" },
  { key: "geometry_validity", label: "几何有效性", color: "#ef4444" },
  { key: "reference_binding", label: "参考绑定", color: "#14b8a6" },
  { key: "reference_topology", label: "参考拓扑", color: "#f97316" },
];

export class QCManager {
  constructor(map, getTileId, toast) {
    this.map = map;
    this.getTileId = getTileId;
    this.toast = toast;
    this.counts = {};      // key -> count
    this.active = {};      // key -> boolean
  }

  renderControls(container) {
    container.innerHTML = "";
    QC_CHECKS.forEach((check) => {
      const row = document.createElement("label");
      row.className = "qc-row";
      row.innerHTML = `
        <input type="checkbox" data-k="${check.key}" />
        <span class="dot" style="background:${check.color}"></span>
        <span>${check.label}</span>
        <span class="cnt" id="qc-cnt-${check.key}">0</span>`;
      const cb = row.querySelector("input");
      cb.addEventListener("change", async () => {
        try { await this.toggle(check, cb.checked); }
        catch (e) { this.toast(`质检加载失败：${e.message}`); cb.checked = false; }
      });
      container.appendChild(row);
    });
  }

  async toggle(check, on) {
    const name = `qc_${check.key}`;
    if (!on) {
      this.map.removeGroup(name);
      this.active[check.key] = false;
      this._setCount(check.key, 0);
      return;
    }
    const tileId = this.getTileId();
    if (!tileId) return;
    const data = await api.qc(tileId, check.key);
    this.map.clearGroup(name);
    data.features.forEach((f) => {
      this.map.addFeature(name, f, () => ({
        color: check.color, weight: 2, fillColor: check.color, fillOpacity: 0.4,
      }));
    });
    this.active[check.key] = true;
    this._setCount(check.key, data.count);
    if (data.count > 0) this.toast(`${check.label}：${data.count} 个问题`);
    else this.toast(`${check.label}：未发现问题`);
  }

  _setCount(key, n) {
    this.counts[key] = n;
    const el = document.getElementById(`qc-cnt-${key}`);
    if (el) el.textContent = n;
  }

  /** 切换 tile 时清空所有已加载质检图层。 */
  clearAll() {
    QC_CHECKS.forEach((c) => this.map.removeGroup(`qc_${c.key}`));
    this.active = {};
    this.counts = {};
    QC_CHECKS.forEach((c) => this._setCount(c.key, 0));
  }
}
