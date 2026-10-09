# Validation record

This record describes the offline run performed on 7 October 2026 against the data snapshot included in this repository.

## Environment

- Python 3.12.14
- Dash 4.4.1
- Plotly 7.1.0
- pandas 3.0.6
- NumPy 2.5.3
- requests 2.34.2
- pytest 8.4.2
- Ruff 0.16.10

## Command

~~~powershell
python scripts/run_pipeline.py --use-included
~~~

The command was run from the repository root. It skipped the live NSW API fetch and used the raw CSV files included under data/raw.

## Pipeline results

| Check | Result |
|---|---:|
| PM2.5 monitoring stations | 49 |
| Raw daily site-date rows | 138,670 |
| Valid daily site-date rows | 117,118 |
| Missing daily values removed | 21,552 |
| Negative daily values clipped to zero and flagged | 281 |
| Valid hourly rows | 32,579 |
| Daily date range | 2019-01-01 to 2026-09-30 |
| NSW suburbs/localities written | 4,542 |
| Suburb records without a postcode | 33 |
| Duplicate suburb names | 0 |
| Health-advice rows built | 30 |
| Default thresholds built | 6 |

### Valid daily category counts

| Category | Rows |
|---|---:|
| Good | 113,154 |
| Fair | 2,316 |
| Poor | 872 |
| Very poor | 321 |
| Extremely poor | 455 |

## Dashboard and code-quality checks

The pipeline completed all five stages using the included snapshot. Its pytest suite passed:

- 62 pytest cases passed: 60 location/profile/threshold combinations plus suburb-search ranking and panel-availability checks.
- Trend charts rendered for today, 7-day, and 30-day ranges for each combination.
- Suburb-name and postcode search-ranking checks passed.
- All dashboard panels loaded.
- No warnings were raised; pytest treats warnings as errors.
- `ruff check .` and `ruff format --check .` passed.

The screenshot embedded in the root README was captured with the offline map mode (`MAP_STYLE=white-bg`), so it shows station markers without a street basemap.

## Comparison with the included processed data

The pipeline's before/after summary matched for station count, valid daily rows, date range, valid hourly rows, suburb count, and daily category counts.

## Scope

This confirms the offline pipeline and dashboard checks against the bundled 6 October 2026 snapshot. A live API download was not performed as part of this run; API availability and subsequently revised observations may change fresh-download results.

---

# 验证记录

本记录对应 2026 年 10 月 7 日使用仓库内数据快照执行的离线流程。

## 环境

- Python 3.12.14
- Dash 4.4.1
- Plotly 7.1.0
- pandas 3.0.6
- NumPy 2.5.3
- requests 2.34.2

## 执行命令

~~~powershell
python scripts/run_pipeline.py --use-included
~~~

命令从仓库根目录运行，跳过实时 NSW API 下载，使用 data/raw 中附带的原始 CSV 数据。

## 流程结果

| 检查项 | 结果 |
|---|---:|
| PM2.5 监测站 | 49 |
| 原始日度站点-日期记录 | 138,670 |
| 有效日度站点-日期记录 | 117,118 |
| 删除的日度缺失值 | 21,552 |
| 截断至 0 并标记的负值 | 281 |
| 有效小时记录 | 32,579 |
| 日度数据范围 | 2019-01-01 至 2026-09-30 |
| 生成的新州郊区/地点 | 4,542 |
| 无邮编记录 | 33 |
| 重复郊区名称 | 0 |
| 生成的健康建议记录 | 30 |
| 生成的默认阈值 | 6 |

### 有效日度记录的等级数量

| 等级 | 记录数 |
|---|---:|
| Good | 113,154 |
| Fair | 2,316 |
| Poor | 872 |
| Very poor | 321 |
| Extremely poor | 455 |

## 看板与代码质量检查

使用仓库附带的数据快照完成五个流程阶段，pytest 测试结果如下：

- 62 项 pytest 通过：60 种地点/人群/阈值组合，以及郊区搜索排序和面板可用性检查。
- 每种组合均渲染当天、7 天和 30 天趋势图。
- 郊区名和邮编搜索排序检查通过。
- 所有看板面板均可加载。
- pytest 将警告视为错误；本次没有警告。
- `ruff check .` 和 `ruff format --check .` 均通过。

根目录 README 中的截图使用离线地图模式（`MAP_STYLE=white-bg`）生成，因此显示监测站点但不显示街道底图。

## 与仓库附带的处理数据对比

流程执行前后的站点数、有效日度记录数、日期范围、有效小时记录数、郊区数和各等级记录数均一致。

## 验证范围

本次验证覆盖仓库内 2026 年 10 月 6 日快照的离线数据流程和看板检查。此次没有执行实时 API 下载；API 可用性及历史记录修订可能导致未来下载结果变化。

