# -*- coding: utf-8 -*-
"""
局域网多设备访问指引 v1.6.0
"""
本文件路径: E:\工作目录\toolkit重构版\NETWORK_USAGE.md

Z，数据库联网 + 多设备 CRUD 已经按你选的方案落地了：

## 选型：方案 B (SQLite + HTTP API)
- 数据库仍是 SQLite 单文件（项目根 data/app.db），零迁移成本
- "联网"通过在你**主电脑**上启动一个轻量 HTTP API（端口 8765）
- 其他电脑用 client 模式连过来，HTTP/JSON 包装 CRUD
- 纯标准库实现（不依赖 Flask/FastAPI）

## 三种 network_mode

### 1. local（默认，单机用）
- config.db.network_mode = "local"
- 你的工具还是直接动本地 SQLite
- 跟之前 v1.5.0 一样

### 2. server（主电脑开服务）
- config.db.network_mode = "server"
- 主电脑启动后，HTTP server 自动监听 0.0.0.0:8765
- 同局域网其他电脑可以访问这台机器的数据库
- 可选 api_token 做 Bearer Token 鉴权

### 3. client（其他电脑连过来）
- config.db.network_mode = "client"
- config.db.server_url = "http://主电脑IP:8765"
- 这台电脑的所有 CRUD 都走 HTTP 调主电脑的 SQLite
- 如果想两端都能写，可以用 v1.7.0 的乐观锁（不在本版本）

## 客户端写入限制（v1.7.0 新增）
- **服务端设置**：`config.db.server_allow_write = False`（在综合设置 → 局域网配置 → 取消勾选「允许客户端写入」）
- **效果**：客户端只能查询数据，insert/update/delete 会被服务端返回 403 拒绝
- **健康检查**：`/api/health` 响应会包含 `"allow_write": true/false`，客户端可提前知道是否允许写入
- **客户端错误处理**：收到 403 write_denied 时，客户端会抛出 `PermissionError`，提示「服务端已禁用远程写入」
- **适用场景**：多人协作时由主机控制写入，避免数据冲突；或保护主机数据不被客户端误改

## 配置文件位置
- 项目根目录 `data/app_config.json`（自动持久化）
- 首次需要 GUI 端 "设置" 面板填写（v1.6.0 新增）
- 现在可以直接改 `config.py` 的默认值

## 防火墙
主电脑开 server 后，要允许 8765 端口入站：
- 控制面板 → Windows Defender 防火墙 → 高级设置
- 入站规则 → 新建 → 端口 → TCP 8765 → 允许
- 或 PowerShell 一行（管理员）：
  New-NetFirewallRule -DisplayName "Toolkit DB" -Direction Inbound -LocalPort 8765 -Protocol TCP -Action Allow

## API 用法
```bash
# 健康检查
curl http://主电脑IP:8765/api/health

# 查询所有
curl -X POST http://主电脑IP:8765/api/peel_data/query -H "Content-Type: application/json" -d '{"where": "1=1", "params": []}'

# 插入
curl -X POST http://主电脑IP:8765/api/peel_data/insert -H "Content-Type: application/json" -d '{"data": {"sample_name": "test", "polarity": "正极"}}'

# 更新
curl -X POST http://主电脑IP:8765/api/peel_data/update -H "Content-Type: application/json" -d '{"data": {"sample_name": "new"}, "where": "id=?", "params": [1]}'

# 删除
curl -X POST http://主电脑IP:8765/api/peel_data/delete -H "Content-Type: application/json" -d '{"where": "id=?", "params": [1]}'
```

## 限制（v1.6.0 范围）
- 只支持白名单表（peel_data_summary, peel_data_extraction_history）
- WHERE 子句只允许字母数字下划线比较运算符（防注入）
- 没有事务并发控制，多设备同时写同一行可能丢数据
- 局域网用足够了，公网用需要加 HTTPS + 强鉴权（v1.7.0）

## 下次升级 v1.7.0 计划
- 乐观锁（last-write-wins 或 manual-conflict-resolution）
- 实时同步（server-sent events 推送变更）
- 手机端只读视图
