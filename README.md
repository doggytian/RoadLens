# RoadLens

**车道级 / 道路级地理空间数据的「可视化分析 + 质量检查」开源工作台。**

RoadLens 是一个完全自包含、可本地运行的 Web 工具，灵感来自内部 HD 地图工作台，但**不依赖任何专有代码、专有数据、内部网络或商业 SDK**。所有数据来自公开来源（OpenStreetMap）或完全合成的随机几何，所有依赖均为开源库。

- 后端：Flask + shapely + pyproj（Python 3.9+）
- 前端：原生 HTML/CSS/ES6 模块 + Leaflet（无 React/Vue）
- 存储：磁盘上的 GeoJSON + 按用户隔离的运行时目录（无外部数据库）

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. （可选）生成/刷新内置示例 tile
python scripts/fetch_sample.py --synthetic     # 离线合成（默认随仓库已提供）
# 或尝试拉取真实 OSM 路网（需联网）：
python scripts/fetch_sample.py                  # 自动回退到合成

# 3. 启动
./start.sh
# 或： python -m server.app

# 4. 浏览器打开
open http://localhost:8124
```

首次打开会要求输入用户名（字母/数字/下划线，1~32 字符），后端按用户建立独立工作目录，
通过 HTTP Header `X-User-Id` 传递，刷新后保持隔离。

> 端口、网格大小、质检阈值等见 `config.yaml`。

---

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 2D 地图浏览 | Leaflet 加载公开底图（OSM 标准 / Esri 卫星），叠加 RoadCorridor / Lane / ReferenceLink |
| 要素点击交互 | 点击任意要素 → 右侧属性面板展示 ID、类型、车道数、长度、所属 tile 等 |
| 选中模式 | 点选 + 框选（顶栏「框选」按钮，拖拽矩形）；多要素命中时左侧弹出候选列表 |
| 图层样式自定义 | 颜色 / 透明度 / 线宽可配；支持「按类型自动上色」 |
| 经纬度跳转 / 右键拾取 | 顶栏输入经纬度定位；地图右键复制坐标到剪贴板 |
| 质检结果叠加 | 勾选 8 类质检图层，按类型着色，支持懒加载 |
| 用户隔离 | 轻量用户名隔离，独立工作目录 |
| 数据加载 | 启动加载内置示例 tile，或用 `scripts/fetch_sample.py` 拉取 OSM 路网 |
| 后台清理 | 超龄（默认 12h）用户目录由守护线程自动清理 |

---

## 架构说明

```
请求 → Flask(app.py) → 路由(tile.py / data.py) → 服务层
                                          ├─ data_loader.py : Tile 加载 + LRU 缓存
                                          └─ qc_service.py  : 8 类质检（shapely）
                                cleanup.py : 后台清理线程
                                geo_utils.py: WGS84 ↔ 局部米制等距投影
```

- **投影**：几何计算统一投影到以 tile 中心为原点的方位等距平面（`geo_utils.py`），
  保证米制下的距离、面积、缓冲在公里级尺度误差极小。
- **缓存**：`data_loader.DataLoader` 内置 LRU（默认 16 个 tile）。
- **用户隔离**：`workspace/<user_id>/tiles/*.geojson`，由 `X-User-Id` 头驱动；
  `config.yaml` 中 `cleanup_max_age_hours` 控制清理阈值。

### 目录结构

```
RoadLens/
├── README.md
├── LICENSE                # MIT
├── requirements.txt
├── config.yaml
├── start.sh
├── scripts/fetch_sample.py
├── server/
│   ├── app.py             # Flask 入口
│   ├── config.py          # 配置解析
│   ├── data_loader.py
│   ├── qc_service.py      # 8 类质检（shapely）
│   ├── geo_utils.py       # 投影工具
│   ├── cleanup.py
│   └── routes/{tile,data}.py
├── static/
│   ├── index.html
│   ├── css/style.css
│   └── js/{api,map,layers,qc,main}.js
├── sample_data/tile_sample_city.geojson
└── workspace/             # 运行时（gitignore）
```

---

## 数据模型

OSM 路网被抽象为一套「车道级」语义模型（区别于普通地图查看器的关键）：

- **RoadCorridor**（对应 LaneGroup）：一组**平行** OSM way 组成的道路走廊，用多边形表示覆盖区域。
- **Lane**（对应 Lane）：走廊内单条 OSM way（LineString）。
- **ReferenceLink**（对应 Link）：走廊参考中心线（LineString），可为代表 way 或脊柱线。
- **Tile**：按经纬度网格（`config.yaml` 的 `grid_size_deg`）分区；每 tile 一组 GeoJSON 文件。

每个要素为 GeoJSON `Feature`，`properties.feature_type` 取上述三种之一，并携带
`id`、`tile_id`，以及可选 `lane_count` / `length_m` / `corridor_id` 等字段。

`sample_data/tile_sample_city.geojson` 是一份**合成**示例：一张小型连通路网，
刻意包含各类质检问题（宽度异常、压盖、菱形拓扑、缺失参考线、孤立段、退化几何等），
便于直接体验全部 8 类质检。

---

## 质检项说明

全部基于开源 `shapely` 在 Python 侧实现，输出 GeoJSON（`check_type` / `severity` / `message`），
前端按 `check_type` 着色。

| check_type | 名称 | 说明 |
| --- | --- | --- |
| `corridor_width` | 走廊宽度异常 | 走廊垂直宽度偏离 `车道数 × 标准车道宽(默认3.5m)` 的合理范围 |
| `buffer_break` | 缓冲断裂 | 对走廊多边形做负向缓冲（`buffer(-0.5)`）后破碎/消失 |
| `centerline_coverage` | 中心线覆盖 | ReferenceLink 未被对应走廊多边形完全覆盖（覆盖率 < 阈值） |
| `overlap` | 压盖检测 | 同层两个走廊多边形面积重叠（近似垂直相交的路口已排除） |
| `diamond_topology` | 菱形拓扑 | 近似识别：两条走廊的参考中心线共享同一对起讫结点（分流→合流） |
| `geometry_validity` | 几何有效性 | 空几何 / 无效几何 / 零面积 |
| `reference_binding` | 参考绑定 | 走廊未挂接任何 ReferenceLink |
| `reference_topology` | 参考拓扑 | ReferenceLink 链条断裂 / 悬空端点 / 孤立段 |

> 说明：`overlap` / `diamond_topology` 为 MVP 阶段的**近似**实现，用作占位与扩展起点，
> 生产级可替换为更严谨的拓扑规则。

---

## REST API

所有接口需带 `X-User-Id` 头。

- `GET  /api/data/state` — 当前用户可用 tile 列表、示例就绪状态、质检项清单
- `POST /api/data/load_sample` — 将内置示例复制到用户工作目录
- `GET  /api/tile/<tile_id>` — 某 tile 全部要素（FeatureCollection）
- `GET  /api/tile/<tile_id>/feature/<feature_id>` — 单个要素详情
- `GET  /api/tile/<tile_id>/qc` — 运行全部 8 类质检
- `GET  /api/tile/<tile_id>/qc/<check_name>` — 运行单个质检

---

## 扩展指引

- **新增质检项**：在 `qc_service.CHECK_NAMES` 注册名称，并实现 `_check_<name>(self, local, center)`
  返回问题列表；前端 `qc.js` 的 `QC_CHECKS` 增加一项（含颜色）即可。
- **新增要素类型**：在 `data_loader._FEATURE_TYPES` 与 `static/js/layers.js` 的 `FEATURE_TYPES`
  中登记样式；`map.addFeature` 已通用支持。
- **对接真实流水线**：本项目刻意不包含内部 DAG / 流水线能力。如需接入，请在
  `server/data_loader.py` 增加新的 Tile 来源适配器（返回相同 GeoJSON 结构），
  并在 `routes/data.py` 暴露加载接口——**请勿引入任何专有内部服务地址或 SDK**。
- **多 tile / 合并**：`config.yaml` 的 `grid_size_deg` 已支持网格划分；合并接口可作为
  `data_loader` 的新方法扩展。

---

## 合规说明

本项目为开源公开版，遵循 MIT 许可证。**不**包含任何专有代码、专有数据、内部网络访问、
商业 SDK 或内部术语/logo。示例数据均来自 OSM（经 Overpass）或完全合成的随机几何。

---

## 后续可扩展方向

- 多 tile 对比与差异高亮
- 质检趋势 / 历史问题统计面板
- 瓦片合并与裁剪接口
- 更多质检规则（车道连续性、拓扑悬挂、方向一致性等）
- 质检查询参数化（按严重级过滤、按区域裁剪）
- 导出质检报告（CSV / HTML）
- 用户级配置持久化（样式、常用 tile）
