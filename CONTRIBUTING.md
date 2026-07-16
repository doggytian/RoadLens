# 贡献指南

感谢你对 RoadLens 的关注！本文档说明如何在本地运行、开发与提交贡献。

## 开发环境

要求 Python 3.9+。

```bash
# 安装含测试工具的开发依赖
pip install -r requirements-dev.txt

# （可选）生成/刷新内置示例 tile
python scripts/fetch_sample.py --synthetic

# 启动
./start.sh          # 或 python -m server.app
```

启动后浏览器打开 http://localhost:8124 ，首次进入需输入用户名（字母/数字/下划线，1~32 字符）。

## 运行测试

```bash
python -m pytest -q
```

提交 PR 前请确保：

- `python -m compileall -q server scripts` 无报错；
- `python -m pytest -q` 全部通过；
- 新增功能尽量附带对应测试（放在 `tests/`）。

CI 会在每次 push / PR 时自动执行上述检查（见 `.github/workflows/ci.yml`）。

## 代码风格

- 遵循仓库根目录的 `.editorconfig`（UTF-8、LF、Python 4 空格缩进、JS/CSS/HTML/YAML 2 空格缩进）。
- Python 建议遵循 PEP 8；函数与模块保持简洁的中文/英文 docstring。

## 常见扩展

### 新增质检项

1. 在 `server/qc_service.py` 的 `CHECK_NAMES` 注册名称；
2. 实现 `_check_<name>(self, local, center)`，返回问题列表（每项含 `geometry` / `severity` / `message` 等）；
3. 在 `static/js/qc.js` 的 `QC_CHECKS` 增加一项（含颜色）；
4. 补充对应测试。

### 新增要素类型

1. 在 `server/data_loader.py` 的 `_FEATURE_TYPES` 与 `static/js/layers.js` 的 `FEATURE_TYPES` 中登记样式；
2. `map.addFeature` 已通用支持，无需额外改动渲染主流程。

## 提交规范

- 提交信息建议采用 [Conventional Commits](https://www.conventionalcommits.org/)：
  `feat:` / `fix:` / `docs:` / `test:` / `chore:` / `ci:` 等前缀。
- 一个 PR 聚焦一件事，附上动机与验证方式。

## 合规红线（重要）

RoadLens 是**开源公开**项目，请勿引入：

- 任何专有代码、专有数据、专有算法或内部术语 / logo；
- 任何公司内网域名、内部 API 地址、商业 SDK 或内部计算集群依赖；
- 任何密钥 / 凭证（一律走环境变量，不得硬编码）。

数据来源仅限公开渠道（如 OpenStreetMap / Overpass API）或完全合成的随机几何。

## 许可证

贡献即表示你同意以本项目的 [MIT License](LICENSE) 授权你的代码。
