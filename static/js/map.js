// 地图视图封装：底图、图层组管理、要素点击、框选、右键拾取坐标。
import { showToast } from "./main.js";

const OSM = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap contributors",
});
const ESRI = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "© Esri" }
);

export class MapView {
  constructor(elId) {
    this.map = L.map(elId, { zoomControl: true, contextmenu: true }).setView([39.9087, 116.3975], 13);
    this.baseLayers = { "OSM 标准": OSM, "Esri 卫星": ESRI };
    OSM.addTo(this.map);
    L.control.layers(this.baseLayers, null, { position: "topright" }).addTo(this.map);

    this.groups = {};                 // name -> L.LayerGroup
    this.highlight = L.layerGroup().addTo(this.map);
    this._boxActive = false;
    this._boxRect = null;
    this._boxStart = null;
    this.onFeatureClick = null;       // (feature) => void
    this.onBoxSelect = null;          // (L.latLngBounds) => void

    this.map.on("contextmenu", (e) => this._onContextMenu(e));
    this._bindBoxSelect();
  }

  addGroup(name) {
    if (!this.groups[name]) this.groups[name] = L.layerGroup().addTo(this.map);
    return this.groups[name];
  }
  clearGroup(name) {
    if (this.groups[name]) this.groups[name].clearLayers();
  }
  removeGroup(name) {
    if (this.groups[name]) { this.map.removeLayer(this.groups[name]); delete this.groups[name]; }
  }

  /** 向指定图层组添加单个 GeoJSON 要素（带点击回调）。 */
  addFeature(groupName, feature, styleFn) {
    const g = this.addGroup(groupName);
    const layer = L.geoJSON(feature, {
      style: styleFn,
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 4, color: "#fff" }),
    });
    layer.eachLayer((l) => {
      l.on("click", (ev) => {
        L.DomEvent.stopPropagation(ev);
        if (this.onFeatureClick) this.onFeatureClick(feature);
      });
    });
    layer.addTo(g);
    return layer;
  }

  /** 高亮某个 GeoJSON 要素（独立图层，可清除）。 */
  highlightFeature(feature) {
    this.clearHighlight();
    const layer = L.geoJSON(feature, {
      style: { color: "#ffffff", weight: 3, fillColor: "#fde047", fillOpacity: 0.35 },
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 6, color: "#fff", fillColor: "#fde047", fillOpacity: 1 }),
    });
    layer.addTo(this.highlight);
  }
  clearHighlight() { this.highlight.clearLayers(); }

  flyTo(latlng, zoom) { this.map.setView(latlng, zoom || Math.max(this.map.getZoom(), 15)); }

  fitToBounds(bounds) {
    if (bounds && bounds.isValid()) this.map.fitBounds(bounds);
  }

  _onContextMenu(e) {
    const ll = e.latlng;
    const txt = `${ll.lat.toFixed(6)}, ${ll.lng.toFixed(6)}`;
    navigator.clipboard?.writeText(txt).then(
      () => showToast(`已复制坐标：${txt}`),
      () => showToast(`坐标：${txt}`)
    );
  }

  // ---- 框选 ----
  setBoxSelect(active) {
    this._boxActive = active;
    document.body.classList.toggle("boxselect", active);
    if (active) { this.map.dragging.disable(); this.clearBox(); }
    else { this.map.dragging.enable(); this.clearBox(); }
  }
  clearBox() {
    if (this._boxRect) { this.map.removeLayer(this._boxRect); this._boxRect = null; }
  }
  _bindBoxSelect() {
    this.map.on("mousedown", (e) => {
      if (!this._boxActive) return;
      this._boxStart = e.latlng;
      this.clearBox();
    });
    this.map.on("mousemove", (e) => {
      if (!this._boxActive || !this._boxStart) return;
      const b = L.latLngBounds(this._boxStart, e.latlng);
      this.clearBox();
      this._boxRect = L.rectangle(b, { color: "#38bdf8", weight: 1, fillOpacity: 0.1 }).addTo(this.map);
    });
    this.map.on("mouseup", (e) => {
      if (!this._boxActive || !this._boxStart) return;
      const b = L.latLngBounds(this._boxStart, e.latlng);
      this._boxStart = null;
      this.clearBox();
      if (this.onBoxSelect) this.onBoxSelect(b);
    });
  }
}
