# Toolkit (工具集) - 剥离数据汇总 版本更新日志

本文件为版本更新日志的数据源，由 version_history.py 解析渲染。
格式约定：每个版本以 ## [x.y.z] - YYYY-MM-DD 开头，
下方分 ### 新增功能 / ### 功能改进 / ### 问题修复 三个分类。

---

## [1.7.1] - 2026-06-14

### 新增功能
- **综合设置保存门禁**：综合设置界面改为底部统一「保存 / 放弃改动 / 关闭」按钮，网络模式、Token、数据库路径、关键词等必要参数不再因误触而立即落盘
- **未保存状态提示**：顶部新增「● 未保存」角标，底部提示当前保存状态，各 Tab 标题自动标记未保存改动
- **关键词编辑体验增强**：正极/负极关键词、材料关键词编辑区改为说明 + 输入框 + 清空按钮的组合式布局

### 功能改进
- **综合设置 UI 全面优化**：统一分组卡片、间距、圆角、按钮层级、输入框 focus/hover 状态，提升配置页面可读性和操作安全感
- **主窗口欢迎页优化**：欢迎页改为更清晰的产品标题、说明与版本提示卡片
- **CI 构建兼容**：GitHub Actions Release workflow 同时支持 `v*` 与 `V*` 标签触发，发行版产物说明不再硬编码旧版本 exe 名称
- **文档同步**：更新局域网使用说明，明确 v1.7.1 起配置项必须点击「保存」才会生效
- **版本号升至 1.7.1**

### 问题修复
- 修复综合设置重构后设备扫描线程方法名写成 `run__` 导致扫描逻辑不执行的问题
- 修复关键词配置区只显示标签、不显示输入框的问题
- 修复 PySide6 多继承初始化链下 `_DirtyTrackerMixin.__init__()` 缺少 host 参数导致 SettingsDialog 构造失败的问题

---

## [1.7.0] - 2026-06-14

### 新增功能
- **综合设置界面**（`ui/settings_dialog.py`）：侧边栏「⚙ 综合设置」按钮打开三 Tab 对话框
  - 🌐 局域网配置：网络模式切换（local/server/client）、监听地址/端口、API Token（明文+复制+自动生成）、客户端 URL、连接测试、设备扫描+配对
  - 📋 剥离数据汇总 参数：数据目录路径、数据库路径、关键词按使用范围分 4 类编辑、恢复默认
  - 💾 导入/导出：JSON 配置文件导出/导入、当前配置预览
- **配置全量持久化**：`config.save()` / `load()` 从只保存 last_data_dir 扩展为保存全部设置（网络、关键词、代理等）
- **数据库命名规范**：所有表名统一为"插件名_数据库名"格式
  - `extraction_history` → `peel_data_extraction_history`
  - 启动时自动检测旧表并 `ALTER TABLE RENAME`，零数据丢失
- **客户端写入限制**：服务端可关闭客户端写入权限（`server_allow_write=False`）
  - 设置界面服务端配置区新增「允许客户端写入」勾选框
  - 客户端 insert/update/delete 被服务端返回 403 + 友好提示
  - `/api/health` 响应包含 `allow_write` 字段，客户端可提前获知
  - 适用场景：多人协作时由主机控制写入，保护数据安全

### 功能改进
- **实时保存**：设置界面所有参数修改即时生效并持久化，无需点击"保存"按钮
- **连接测试**：后台线程测试 DB server 健康状态，不阻塞 UI
- **配置导入兼容**：导入时兼容缺失字段，不会因缺少某个 key 而崩溃
- **监听地址自动检测**：自动填本机局域网 IP，加「自动检测」按钮
- **Token 明文显示**：默认 Normal 模式（非密码遮挡），加「📋 复制」按钮
- **设备自动发现**：`core/discovery.py` 并发扫描局域网 Toolkit 实例，一键配对
- **版本号升至 1.7.0**

### 问题修复
- 修复 `main.py:55` 新增 server 启动逻辑使用 `config` 而非 `_config` 别名导致的 NameError（上一版本遗留）
- 修复 SettingsDialog 打开即崩的严重 bug（_NetworkTab 布局结构损坏 + 缺 QCheckBox 导入）

---

## [1.6.0] - 2026-06-14

### 新增功能
- **局域网多设备访问数据库**：在主电脑上启动 HTTP server（端口 8765），其他电脑通过 client 模式连过来
- **DB 同步服务端** (`core/db_server.py`)：标准库 `http.server` + `sqlite3` 零依赖，支持 Bearer Token 鉴权、表白名单、WHERE 子句防注入
- **DB 同步客户端** (`core/db_client.py`)：标准库 `urllib` 零依赖，REST 风格 API
- **完整 CRUD 接口**：local SQLite 增 `insert()` / 删 `delete()` / 改 `update()` / 查 `count()` + 已有 query_one/query_all
- **network_mode 三模式**：local（单机）/ server（开服）/ client（连他机）
- **使用文档** `NETWORK_USAGE.md`：含防火墙、API curl 示例、v1.7.0 升级计划

### 功能改进
- **零外部依赖**：服务端和客户端都用 Python 标准库，PyInstaller 打包体积不变
- **表白名单**：只允许 peel_data_summary / peel_data_extraction_history 两张表被 HTTP 访问，防 SQL 注入
- **CORS 头**：浏览器侧直接调 API 不需额外代理

### 问题修复
- 复用 v1.5.1 的版本号单一来源机制，1.6.0 升版自动同步到 plugin/main_window/spec

---

## [1.5.1] - 2026-06-14

### 新增功能
- **自动更新检查**：点击"版本动态"页面的"检查更新"按钮，自动从 GitHub Releases 拉取最新版本号和下载链接
- **gh-proxy 代理加速**：所有 GitHub 资源下载链接自动拼接 `https://gh-proxy.org/` 前缀，国内用户下载更快
- **版本号单一来源**：`config.AppConfig.app_version` 作为全项目唯一版本号来源。`plugin.py` / `main_window.py` / `toolkit.spec` / `VERSION_LOG.md` 全部从 `config.get_version()` 读取，杜绝版本号漂移
- **bump_version() 工具**：`config.bump_version("major"|"minor"|"patch")` 升版号后自动写回 `config.app_version`

### 功能改进
- **检查更新弹窗**：从简陋的 `QMessageBox` 改为 `QDialog`，含更新内容预览 + 加速下载 + 原始 GitHub 链接三按钮
- **错误提示细分**：网络错误、解析失败、已是最新、发现新版本 4 种情况分别提示，UI 不再吞错
- **PE 嵌入打包诊断**：使用 PyInstaller `CArchiveReader` 直接读 .exe 内的 TOC，验证 plugins/ 是否真打进去

### 问题修复
- **PyInstaller 动态插件打包**：`hiddenimports` 解决不了 `_MEIPASS/plugins/` 目录缺失，必须 `datas += [(plugins, plugins)]`
- **GitHub Actions 跨平台兼容**：`ls -lh` 在 PowerShell 7 不识别，改用 `Get-ChildItem`
- **workflow_dispatch release 缺 tag**：dispatch 触发时自动建 `ci-build-<short-sha>` 临时 tag

---

## [1.5.0] - 2026-06-13

### 新增功能
- **试样名称智能提取**：新增按优先级链提取试样名称的逻辑——优先级 1: 从文件名提取（保留完整的正极/负极前缀和型号中的连字符）；优先级 2: 从已有 sample_name 中提取"正极"/"负极"前缀全量名称；优先级 3: 保留已提取的名称。通用文件名（test、data、temp 等）自动降级为使用文件内容中的名称
- **锂电池材料关键词库**：`config.py` 新增 `lithium_battery_materials` 关键词库（50+ 条），覆盖导电液（导电液、单壁管导电液、CNT导电液）、导电剂（KS-6、SP-Li、SuperP、乙炔黑、VGCF）、石墨类（人造石墨、天然石墨、球形石墨、MCMB）、三元类（NCM、NCA、LFP、LCO）、粘结剂（PVDF、CMC、SBR）、高温胶/膨胀胶、硅基材料（硅碳、SiO、氧化亚硅）、隔膜/电解液、集流体等
- **材料关键词辅助极性判定**：`config.determine_polarity_with_materials()` 先用正负极关键字判定，再用材料关键词辅助——含铝相关→正极，含铜相关→负极，石墨→负极，三元/NCM/NCA/LFP→正极，硅碳/SiO→负极
- **工具函数集**：`config.py` 新增 4 个静态方法——`extract_sample_name_from_filename()`（从文件名提取试样名称）、`extract_sample_name_by_polarity_prefix()`（从极性前缀提取完整名称）、`match_material_keywords()`（匹配材料关键词）、`determine_polarity_with_materials()`（含材料辅助的极性判定）

### 功能改进
- ExcelParser 和 PDFParser 统一使用 `_upgrade_sample_name()` 方法升级试样名称，确保两个解析器的提取逻辑完全同步
- ExcelParser 和 PDFParser 的 `_determine_polarity()` 统一调用 `config.determine_polarity_with_materials()`，极性判定结果包含材料关键词信息
- 文件名提取时保留型号中的连字符（如 `INR21700-40PE` 不再被拆分为 `INR21700 40PE`）
- 去重策略优化：移除跨批次数据库查询去重，仅保留单次提取的批次内去重（按 test_date+test_time+polarity），由数据库 UNIQUE 约束处理写入时去重
- 数据预览表格改造：去掉 PreviewDialog 弹窗，数据直接填入主窗口表格；去重跳过的记录用暖黄底色 (#fff3cd) 显示，新增"状态"列区分"✓ 已保留"和"⚠ 去重跳过"

---

## [1.4.0] - 2026-06-12

### 新增功能
- 数据目录路径动态化：移除硬编码路径，首次使用时数据目录留空，用户通过"浏览"按钮自行选择后自动持久化到 `data/app_config.json`，后续启动自动回填上次目录
- 历史记录操作时间：每次提取操作自动记录精确时间戳（格式 `yyyy-MM-dd HH:mm:ss`），在历史记录表格中独立展示，支持持久化存储和排序

### 功能改进
- 极性判定统一化：PDFParser 改用 `config.py` 中的 `positive_keywords` / `negative_keywords` 关键字列表判定极性（含试样名称+文件名双重匹配），与 ExcelParser 保持一致
- 旧版 Python 2.x dict 键名修复：ExcelParser 日志摘要中 `S1`~`S4` 改为 `curve_1`~`curve_4`，与 `PeelDataRecord` dataclass 字段名对齐
- 来源文件完整路径：`source_file` 字段从仅存文件名改为存储完整绝对路径，导出 Excel/CSV 时自动使用完整路径；数据预览表格"来源文件"列支持右键菜单「打开文件所在位置」，调用 Windows 资源管理器定位并高亮文件

### 问题修复
- **修复提取过程中程序闪退（严重）**：`WidgetLogHandler.emit()` 在 worker 线程直接操作 `QTextEdit.append()` 违反 Qt 线程安全规则，在 Windows 上导致 `0xC0000005` 访问冲突崩溃；改为 `Signal(str, str)` + `QueuedConnection` 跨线程安全传递日志
- 修复 `.xls` 文件无法提取剥离强度数据：`_parse_xls_sheet()` 中 `pass` 占位符替换为完整实现，支持 Format A（横向 S 列）和 Format B（纵向曲线行）两种布局的 xlrd 适配版解析
- 修复 `test_datetime` 属性对 `datetime.date` 对象调用 `.strip()` 导致 `AttributeError` 崩溃：增加 `isinstance` 类型检测，统一转为 `isoformat()` 字符串
- 修复 `to_dict()` 透传 `datetime.date` / `datetime.time` 对象导致 SQLite `executemany` 绑定失败：在序列化阶段统一转换为 `isoformat()` 字符串
- 修复 `insert_many_ignore` 和 `insert_ignore` 不处理 `datetime.time` 类型导致数据库写入失败：参数绑定前增加 `_adapt()` 防御层，自动转换 `datetime.date` / `datetime.time` → `isoformat()` 字符串
- **修复时间精度不一致导致重复数据误判**：不同数据源的 `test_time` 格式不统一（`"14:30"` vs `"14:30:00"`），导致 `UNIQUE(test_date,test_time,sample_name)` 约束无法识别同一试验；新增 `_normalize_date()` / `_normalize_time()` 规范化函数，强制统一 `test_date` → `YYYY-MM-DD`、`test_time` → `HH:MM:SS` 格式
- **修复同一测试从 PDF/Excel 提取时因 sample_name 不一致产生重复数据**：同一物理测试在不同文件格式中 `sample_name` 不同（PDF 简名 vs Excel 完整文件名），导致 UNIQUE 约束失效；新增 `_dedup_records()` 方法，在入库前按 `(test_date, test_time, polarity)` 批次内+跨批次去重，手动新增记录同样增加去重检查

---
## [1.3.0] - 2026-06-12

### 新增功能
- 数据库查看器：新增行内编辑按钮，支持直接修改记录并保存
- 数据库查看器：新增全选复选框列，支持批量选择记录
- 数据库查看器：新增极性筛选下拉框，按正极/负极/全部快速过滤
- 数据库查看器：新增全局搜索框（300ms 防抖），支持按关键词实时过滤
- 数据库查看器：新增导出 Excel 功能，将当前视图数据导出为带格式的 Excel 文件
- 应用图标：设置 DTL Logo 为多分辨率应用图标（ICO 含 7 种尺寸 + 高清 PNG），适配桌面/任务栏/标题栏
- 动态曲线列：数据库查看器根据数据自动显示 curve_1~curve_9 列，无数据列自动隐藏

### 功能改进
- 历史记录对话框：升级为多选模式，支持批量删除；新增"新增记录"入口；替换蓝色配色为现代灰/绿/红主题
- 数据库查看器对话框：同步历史记录对话框的交互与视觉优化（多选、新增、配色）
- 启动脚本：启动.pyw 改为无控制台窗口方式启动（CREATE_NO_WINDOW），消除黑色闪屏
- 数据库查看器：操作列按钮布局优化，编辑/删除按钮水平排列，列宽固定 120px

### 问题修复
- 修复程序启动崩溃：移除 QTableWidgetItem.setWordWrap() 无效调用（该方法不存在，导致 AttributeError）
- 修复启动.pyw 黑色控制台窗口：改用 subprocess.Popen 并设置 CREATE_NO_WINDOW 标志

---

## [1.2.0] - 2026-06-11

### 新增功能
- 数据库记录浏览：新增"查看数据库"按钮，支持搜索、删除、刷新数据库中的记录
- 历史记录持久化：提取历史自动写入数据库，重启后仍可查询之前的提取记录
- 曲线单位显示：从源文件中提取剥离强度单位（如 kN/m），在表格列标题和导出 Excel 中显示
- 版本动态页面：从标题栏按钮升级为侧边栏主体功能模块，新增"变更总览"标签页
- 检查更新：版本动态页面新增"检查更新"按钮，支持在线检测新版本

### 功能改进
- 侧边栏布局优化：版本动态移至侧边栏底部作为独立导航项，后续插件沿用此布局模式
- 历史记录按钮状态管理：仅在数据库中存在历史记录或首次提取完成后启用
- 删除功能完善：数据库浏览器的"删除选中"功能已完整实现，支持批量删除
- 防御性错误处理：提取完成后的表格渲染和消息框显示均增加 try/except 防护

### 问题修复
- 修复 _is_db_available() NameError：该函数定义在 extractor.py 中但未在 main_widget.py 中导入，导致保存修改和查看数据库时闪退
- 修复未勾选"保存到数据库"时闪退：增加防御性 try/except，区分"未勾选"和"数据库不可用"两种场景的消息提示
- 修复数据库浏览器批量删除不生效：_on_delete_selected() 中 pass 占位符替换为实际删除逻辑

---

## [1.1.0] - 2026-06-11

### 新增功能
- 版本更新日志页面：时间线形式展示版本历史，支持分类查看（新增/改进/修复）
- 版本对比视图：任选两个版本并排对比差异
- 版本搜索与筛选：支持关键词搜索和版本号快速定位
- 提取历史记录模块：记录每个文件的提取成功/失败状态及原因说明
- 打开文件所在位置：历史记录中可一键打开文件所在文件夹并选中文件
- 数据表格编辑功能：双击单元格可直接编辑，修改后可保存到数据库

### 功能改进
- 日期时间合并显示：将"试验时间"和"试验日期"合并为"试验日期时间"单列，格式统一为 `YYYY-MM-DD HH:MM:SS`
- 数据库无 MySQL 时优雅降级：自动切换为 SQLite（零安装），数据仍可预览和导出
- 日志系统优化：日志保存路径改为项目根目录 `logs/`，按日期轮转，保留 5 天备份
- 按钮文案统一："提取历史"改为"历史记录"，"打开文件所在路径"改为"打开文件所在位置"

### 问题修复
- 修复试样名称提取失败：增加标签文字回退机制，当提取到"试样编号"等标签时自动回退到文件名
- 修复极性识别失败：综合试样名称和文件名判定极性，支持更多关键字匹配
- 修复数据库 KeyError: 'curve_4'：`to_dict()` 改为返回完整字段字典，确保批量插入时列一致
- 修复 PDF 解析兼容性：增强文本提取逻辑，同时提取文本和表格内容
- 修复 Excel 字段映射错误：修正表头布局解析中试样名称取值逻辑，取关键字右侧值而非关键字本身

---

## [1.0.0] - 2026-06-10

### 新增功能
- 首次发布剥离数据汇总插件
- 支持 PDF 文件解析：提取 S1~S9 剥离强度、A_Sd 标准差、试验时间/日期
- 支持 Excel 文件解析：提取曲线1~9 剥离强度、标准差、试验时间/日期
- 自动识别正负极：根据试样名称和文件名中的关键字自动判定
- 数据预览表格：展示提取结果，支持按实际曲线数量动态生成列
- 数据导出：支持将汇总数据导出为 Excel 文件，导出路径和文件名可自定义
- 数据库存储：支持将数据写入 MySQL 数据库，基于"试验时间+试验日期+试样名称"建立唯一性约束，重复数据自动跳过
- 日志系统：分级日志（DEBUG/INFO/WARNING/ERROR），支持界面实时调整日志级别
- 模块化架构：核心框架与插件分离，新增工具无需修改核心代码
- 主界面导航：侧边栏工具导航，支持插件动态发现和加载
