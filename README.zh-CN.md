# NSW PM2.5 空气质量与健康洞察看板

**面向作品集展示的新州空气质量数据工程与分析项目。**

本仓库展示一套可复现的数据流程，将新南威尔士州 PM2.5 监测数据整理为交互式看板，涵盖数据采集、质量控制、地理信息整理、空间估算和可视化分析。

[English](README.md) · **中文**

## 项目简介

看板整合 PM2.5 实测数据、新州郊区与邮编检索、地点级估算、空气质量等级和来源可追溯的健康建议。用户可以按郊区名或邮编搜索，选择健康人群档案，查看近期趋势，并了解地点周边的空气质量情况。

### 项目能力

- 完整的数据流程：采集、清洗、验证、地理信息整理和看板数据输出。
- 处理缺失值、负值观测、重复记录、时间范围和站点完整度。
- 使用反距离加权法（IDW）估算地点浓度，并清楚区分实测值与估算值。
- 使用 Dash 和 Plotly 构建模块化看板，包含地图、趋势、健康建议、地点/人群设置和提醒面板。
- 可使用仓库附带的数据快照离线运行，便于复现。

### 数据快照概况

随项目提供的数据于 2026 年 10 月 6 日采集。日均 PM2.5 数据范围为 2019 年 1 月 1 日至 2026 年 9 月 30 日；小时数据覆盖 2026 年 9 月。离线流程生成了 49 个 PM2.5 监测站、117,118 条有效日度站点-日期记录、32,579 条有效小时记录及 4,542 个新州郊区/地点。详细环境和检查结果见 [tests/VALIDATION.md](tests/VALIDATION.md)。

## 看板

![看板完整截图](docs/images/dashboard-overview.png)

截图使用离线地图模式（`MAP_STYLE=white-bg`）生成，因此只显示监测站点，不显示街道底图。联网运行时地图使用 CARTO Positron 底图。

看板包含：

- **地点与人群档案：** 按新州郊区名或邮编搜索，并选择一般人群或敏感人群档案。
- **周边空气质量：** 查看监测站数据，并查看明确标注的地点估算值。
- **近期趋势：** 在快照数据覆盖范围内查看当天、7 天和 30 天趋势。
- **健康建议：** 根据空气质量等级与所选人群查看对应建议。
- **个人提醒设置：** 查看或调整提醒阈值，并查看本地提醒历史。

地点估算是用于探索分析的近似值，不代表每个郊区都有监测设备，也不能取代监测站读数或专业健康建议。

## 数据流程

~~~mermaid
flowchart TD
    A["NSW 空气质量 API<br/>PM2.5 观测值 + 站点信息"] --> B["原始 CSV 快照<br/>data/raw"]
    B --> C["清洗与验证<br/>去重、处理缺失值、<br/>截断并标记负值、统一等级名称"]
    C --> D["规范处理后的数据表<br/>存放于 data/processed"]
    E["ABS ASGS Edition 3<br/>郊区/地点 + 邮编区"] --> F["新州郊区索引<br/>邮编 + 中心点"]
    G["Air Quality NSW<br/>健康建议"] --> H["人群建议<br/>与默认提醒阈值"]
    D --> I["共享数据加载器"]
    F --> I
    H --> I
    I --> J["Dash + Plotly 看板<br/>地图 · 趋势 · 建议 · 提醒"]
    J --> K["pytest 验证<br/>面板组合 + 搜索检查"]
~~~

### 流程步骤

1. **采集观测数据** — scripts/fetch_pm25_data.py 从 NSW API 下载站点信息、日均数据及 2026 年 9 月的小时数据。每次实时采集会写入 data/raw/refetch_* 日期目录，不覆盖仓库附带的原始快照。
2. **清洗与汇总** — scripts/clean_pm25_data.py 删除缺失测量值和重复键；将负 PM2.5 读数截断到 0 并保留标记；统一等级名称；将小时记录转换为时间戳；输出处理后数据及质量汇总。
3. **建立地点索引** — scripts/build_suburbs.py 根据随项目附带的 ABS 地理数据整理新州郊区、邮编和中心点，用于检索与地图展示。
4. **生成健康建议表** — scripts/build_health_advice.py 为 6 类人群和 5 个空气质量等级生成建议，并为每类人群生成默认提醒阈值。
5. **渲染和验证** — tests/test_dashboard_smoke.py 在多种地点、人群、阈值和趋势范围下渲染看板面板，并检查郊区搜索排序。

### 空间估算方法

地点距离监测站不超过 2 公里时，看板使用最近站点的实测值。否则会从 50 公里范围内最多 5 个站点使用反距离加权法进行估算，距离幂次为 2。看板会分别标记估算值与站点实测值。估算值不是官方站点读数。

## 运行项目

### 环境要求

- Python 3.10 或更高版本。
- 只有实时下载 NSW API 数据和加载在线地图底图时需要联网；附带快照可用于离线运行完整流程。

### Windows PowerShell

在仓库根目录执行：

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements_pipeline.txt
python scripts/run_pipeline.py --use-included
~~~

离线命令会处理仓库附带的数据快照，将规范数据表写入 `data/processed/`，并运行 pytest 验证。

如需重新下载最新快照，执行：

~~~powershell
python scripts/run_pipeline.py
~~~

实时下载通常需要 10–15 分钟，并依赖 NSW API 服务可用；下载文件会写入 `data/raw/` 下的新日期目录。

若只想运行看板，安装相关依赖后执行：

~~~powershell
python -m pip install -r dashboard/requirements.txt
python dashboard/app.py
~~~

然后在浏览器打开 http://127.0.0.1:8050。按 Ctrl+C 停止服务。

在本地运行 lint 和格式检查：

~~~bash
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
~~~

### macOS / Linux

在仓库根目录执行：

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_pipeline.txt
python scripts/run_pipeline.py --use-included
~~~

启动看板：

~~~bash
python dashboard/app.py
~~~

## 使用 Render 部署

仓库附带 Render Blueprint 配置 `render.yaml` 和精简的看板运行依赖文件 `requirements_render.txt`。配置会安装看板运行环境，通过 Gunicorn 启动 Dash WSGI 服务，并检查 `/` 健康状态接口。

部署时，在 Render 中基于此公开 GitHub 仓库创建 Blueprint，检查 `render.yaml` 中的服务设置后应用配置。线上看板使用仓库中的历史数据快照；地图底图仍需联网加载。Render 免费方案在闲置时会休眠，首次访问可能需要约 30–60 秒加载。

## 项目结构

~~~text
.
├── data/
│   ├── raw/                  # 附带的 NSW 与 ABS 原始数据快照
│   └── processed/            # 看板直接读取的规范处理数据表
├── scripts/                  # 采集、清洗、地理数据、建议和流程编排脚本
├── tests/                    # pytest 测试与本次验证记录
├── dashboard/
│   ├── app.py                # Dash 应用
│   ├── components/           # 地点/人群、地图、趋势、建议和提醒面板
│   └── assets/               # 样式、无障碍补丁和图标
├── .github/workflows/ci.yml  # 自动 lint 与测试
├── docs/images/              # 项目截图
├── render.yaml               # Render Web 服务 Blueprint
├── requirements_render.txt   # 看板与 Gunicorn 运行依赖
├── LICENSE                   # 项目源码 MIT 许可证
├── README.zh-CN.md           # 中文说明
├── requirements_pipeline.txt
└── requirements-dev.txt
~~~

## 数据来源与署名

- **PM2.5 观测值与站点信息：** NSW Government 运营的 [NSW Air Quality Data API](https://data.airquality.nsw.gov.au/docs/index.html)。随项目附带的数据于 2026 年 10 月 6 日导出；API 简介和用户指南见 [Air Quality NSW](https://www.airquality.nsw.gov.au/air-quality-data-services/air-quality-api)。
- **郊区与邮编地理数据：** [ABS ASGS Edition 3 郊区与地点](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/non-abs-structures/suburbs-and-localities) 及 [ABS 数字边界文件](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files)。项目使用转换后的郊区中心点和 2021 邮编区信息进行检索和展示；ABS 郊区近似范围用于统计用途，并非法律边界。
- **健康建议：** [Air Quality NSW 健康建议与活动指南](https://www.airquality.nsw.gov.au/health-advice) 及 [山火烟雾健康建议](https://www.airquality.nsw.gov.au/health-advice/bushfire-health-advice)。建议仅供信息参考，不能替代医疗服务。
- **数据许可：** 数据仍遵循各自提供方标示的条款。来源标明为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 的材料保留署名。本项目不代表 NSW Government 或 ABS 的官方认可。

## 验证结果

本次运行环境、命令、数据量和检查结果记录在 [tests/VALIDATION.md](tests/VALIDATION.md)。离线流程使用固定快照；实时 API 下载的数据可能因历史数据修订而不同。

## 负责任使用与限制

- 本看板用于探索性分析，不是 NSW Government 官方服务。
- 郊区数据可能是插值估算，而不是本地测量；查看结果时请留意站点与距离标记。
- 随项目提供的是历史快照，不是实时空气质量数据流。
- 健康建议来自所链接的 NSW 来源，仅作一般信息；个人健康问题请咨询合格的医疗专业人员。
- 地图底图需要联网；设置 `MAP_STYLE=white-bg` 可完全离线显示地图。离线时本地数据和图表仍可使用。

## 许可证

项目代码采用 [MIT 许可证](LICENSE)。随项目提供的数据集和第三方素材仍遵循各自提供方的条款，详见[数据来源与署名](#数据来源与署名)。
