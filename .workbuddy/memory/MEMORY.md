# toolkit 重构版 — 项目记忆（跨会话）

> **本文件由 Z 2026-06-14 项目长期记忆卡生成**。
> 真相源 = Z 口述 + 代码事实。每次修改代码前先 `cat` 本文件确认约束未变。

---

## 0. 项目元信息

| 项 | 值 |
|---|---|
| 真实根目录 | `E:\工作目录\toolkit重构版\` |
| ⚠️ 易错别名 | `E:\工作目录\toolkit\`（旧版/不存在，**绝不可写入**） |
| 启动方式 | `.venv\Scripts\pythonw.exe main.py`（即 `启动.pyw`） |
| 打包 | PyInstaller → `dist\Toolkit_v<版本>.exe`（71 MB 量级） |
| 仓库 | https://github.com/qinghuan31/toolkit |
| 当前版本 | v1.6.0（`config.app_version` 单一来源） |

---

## 1. 技术栈

| 层 | 技术 |
|---|---|
| GUI | PySide6 (Qt 6.5+) |
| 数据库 | SQLite (WAL 模式) |
| DB 访问 | `core/database.py` → `DatabaseManager` |
| PDF 解析 | pdfplumber |
| Excel 解析 | openpyxl (.xlsx) / xlrd (.xls) / csv (内置) |
| 架构 | 插件式 `BasePlugin → PeelDataPlugin → PeelDataWidget` |
| 自动更新 | `core/updater.py`（标准库 urllib，无 requests 依赖） |

---

## 2. DB API 铁律（血的教训）

**`DatabaseManager` 只有两个查询方法**：
- `query_one(sql, params=...)` → 单行字典 / None
- `query_all(sql, params=...)` → 行列表

❌ **不存在** `query()` / `execute()` / `fetch_*` 等其他方法。写新代码或改老代码前先 `grep` 确认。

---

## 3. 关键文件路径

```
config.py                                  # 全局配置（关键字 / 材料库 / 极性判定）
main.py                                    # 入口（注入路径、初始化 DB）
ui/main_window.py                          # 主窗口（侧边栏 + QStackedWidget）
core/
  ├─ database.py                           # DatabaseManager
  ├─ plugin_manager.py                     # 插件发现与加载
  ├─ base_plugin.py                        # BasePlugin 抽象基类
  ├─ updater.py                            # GitHub Releases 自动更新
  └─ logger.py / unified_logger.py
plugins/peel_data/
  ├─ plugin.py                             # PeelDataPlugin 入口（create_widget 调 ensure_table/ensure_history_table）
  ├─ extractor.py                          # 提取引擎（_dedup_records / SkippedRecord / ExtractionResult）
  ├─ excel_parser.py                       # _upgrade_sample_name / _determine_polarity
  ├─ pdf_parser.py                         # 同上
  ├─ models.py                             # PeelDataRecord dataclass / _normalize_date|time / to_dict
  └─ ui/main_widget.py                     # _populate_table / _on_extract_finished
toolkit.spec                               # PyInstaller 配置
backup.py                                  # 双保险备份脚本
VERSION_LOG.md                             # 完整更新日志
```

---

## 4. `config.py` 公开 API（必用入口）

| API | 用途 |
|---|---|
| `config.positive_keywords` | 正极关键字列表 |
| `config.negative_keywords` | 负极关键字列表 |
| `config.lithium_battery_materials` | 锂电池材料关键词库（50+ 条） |
| `config.extract_sample_name_from_filename(filename)` | 从文件名提取试样名称 |
| `config.extract_sample_name_by_polarity_prefix(text)` | 从"正极"/"负极"前缀提取完整名称 |
| `config.match_material_keywords(text)` | 匹配锂电池材料关键词 |
| `config.determine_polarity_with_materials(sample_name, filename)` | **极性判定统一入口**（先正负极关键字，再材料关键词辅助） |
| `get_version()` / `bump_version()` | 版本号单一来源 |

⚠️ **所有极性判定必须走 `determine_polarity_with_materials()`**，不要自己写关键字匹配。

---

## 5. 数据模型

### `PeelDataRecord` (dataclass)
- 曲线字段：`curve_1` ~ `curve_9`
- 标准差：`std_dev`
- `to_dict()` → dict

### `SkippedRecord` (dataclass)
- `record: PeelDataRecord`
- `reason: str`
- `matched_existing_id: int = None`

### `ExtractionResult`
- `app_skipped: int`
- `skipped_records: List[SkippedRecord]`
- `summary` 字段含 "应用层去重 N 条"

---

## 6. 关键约定

| 主题 | 规则 |
|---|---|
| **极性判定** | 统一使用 `config.determine_polarity_with_materials()` |
| **Qt 线程安全** | ❌ 严禁在 worker 线程中直接操作 UI 控件<br>✅ 必须通过 Signal/QueuedConnection |
| **时间规范化** | `test_date` → `YYYY-MM-DD`<br>`test_time` → `HH:MM:SS` |
| **来源路径** | `source_file` 存**完整绝对路径**<br>右键菜单 `explorer /select,<path>` 跳转 |
| **去重策略** | 仅**批次内去重** — `_dedup_records()` 按 `(test_date, test_time, polarity)` 去重<br>❌ 跨批次去重已移除 |
| **表格渲染** | 保留行：白底 + "✓ 已保留"<br>跳过行：暖黄底色 `#fff3cd` + "⚠ 去重跳过" |

---

## 7. UI 偏好

- **不要弹窗** — 数据直接在主窗口表格中显示
- **跳过数据要可见** — 用视觉区分（暖黄底色），不要直接扔掉
- **试样名称提取优先级** — 文件名 > 文本内容
- **跨批次去重 = 不要**

---

## 8. 修改前铁律（双保险）

1. `git add -A && git commit -m "backup: <改动>"`
2. `python E:\工作目录\toolkit重构版\backup.py --note "<改动>"`
3. ⚠️ **备份完成前禁止编辑**

详见 `~/.workbuddy/MEMORY.md` 备份铁律章节。

---

## 9. 已知踩坑（避免重蹈）

| 踩坑 | 教训 |
|---|---|
| PyInstaller + 动态插件发现 | `hiddenimports` 不够，必须 `datas += [(plugins, plugins)]` |
| GitHub Actions | 默认 shell 是 PowerShell 7；`workflow_dispatch` 无 tag 需建临时 `ci-build-<sha>` |
| `bump_version()` 后忘了重置 | spec 文件名会错，PyInstaller 编译时已求值 |
| `query()` 方法 | 不存在，用 `query_one` / `query_all` |
| 错误项目根目录 | 改到 `E:\工作目录\toolkit\`（旧版）= 全部修改无效 |

---

## 10. 安卓适配

**已分离到独立项目**：`E:\工作目录\toolkit移动端\`
- API 后端（FastAPI）和 Flutter 安卓端不再放在本项目中
- 通过 `toolkit_config.py` 桥接，API 服务 import 本项目的 config / core / plugins
- 详见 `E:\工作目录\toolkit移动端\.workbuddy\memory\MEMORY.md`

---

## 11. 待办

- [ ] toolkit 1.6.0：继续推进其他功能（具体啥等 Z 拍）
- [ ] 未来 toolkit 加新插件时记得同步 `toolkit.spec` 的 `datas`

---

_本文件由 AI 2026-06-14 02:04 根据 Z 口述契约卡生成_
_2026-06-14 02:21 更新：§10-§12 移至 `E:\工作目录\toolkit移动端\.workbuddy\memory\MEMORY.md`_
