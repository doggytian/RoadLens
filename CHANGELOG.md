# Changelog

本文件记录 RoadLens 的重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- `.editorconfig`：统一编码与缩进规范。
- 单元测试 `tests/`：覆盖 `geo_utils` 投影往返、`qc_service` 全部 8 类质检、`data_loader` 加载/缓存/校验。
- GitHub Actions CI：多 Python 版本下的编译检查、pytest、接口冒烟。
- README 顶部徽章（CI / License / Python 版本）。
- `CONTRIBUTING.md`：贡献指南与开源合规红线。
- Issue / Pull Request 模板。
- `Dockerfile` 与 `.dockerignore`：基于 gunicorn 的容器化部署。
- `.github/dependabot.yml`：pip / github-actions / docker 依赖自动更新。

## [0.1.0]

### Added
- 车道级 / 道路级地理空间数据的可视化分析与质量检查工作台首个版本。
- 支持要素类型：`RoadCorridor`、`Lane`、`ReferenceLink`。
- 8 类通用质检：走廊宽度、缓冲断裂、中心线覆盖、压盖、菱形拓扑、几何有效性、参考绑定、参考拓扑。
- 基于 Flask + Leaflet 的 Web 界面，按 `X-User-Id` 隔离的用户工作区。
- 内置示例 tile 与 `scripts/fetch_sample.py`（支持离线合成或拉取 OSM）。

[Unreleased]: https://github.com/doggytian/RoadLens/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/doggytian/RoadLens/releases/tag/v0.1.0
