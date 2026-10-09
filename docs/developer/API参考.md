# API 参考

## 约定

| 项 | 值 |
|----|-----|
| 默认前缀 | `/kanna_dependency`（`setting_clanbattle.api.base_path`） |
| 默认端口 | `8138`（`api.port`） |
| 成员鉴权 | Cookie Session（登录后） |
| 运维 OpenAPI | Header `X-Admin-Key` = `api.admin_key`（配置须非空、非示例占位；**无**代码层面的长度限制） |

游戏 API 脱敏样本见 [`devtools/fixtures/api/clan_battle_top.sample.json`](../../devtools/fixtures/api/clan_battle_top.sample.json) 等同目录下的 `envelope_*.json`。

---

## 成员 API（`webui/api.py`）

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/login` | QQ 号 + 密码登录 |
| POST | `/logout` | 登出 |
| POST | `/change_password` | 修改密码 |

### 首页与公会

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/home` | 可见公会列表（`ClanBattleMember` + 补全规则） |

### 会战面板（按 `group_id`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{group_id}/panel` | 面板 JSON（Boss、队列摘要） |
| GET | `/{group_id}/panel/stream` | SSE 推送更新 |
| GET | `/{group_id}/status-image` | 会战状态 PNG（ETag 缓存） |
| GET | `/{group_id}/dashboard` | 看板数据（兼容旧版） |
| GET | `/{group_id}/notice` | 预约/申请/挂树 |
| GET | `/{group_id}/report` | 战报数据 |
| GET | `/{group_id}/rank_lines` | 排名行 |
| GET | `/{group_id}/boss_dao` | Boss 伤害 DAO |
| GET | `/{group_id}/battle-days` | 会战日列表 |
| GET | `/{group_id}/stats/daily` | 按日统计 |
| GET | `/{group_id}/reports/guild/daily.png` | 公会日出刀统计图 |

### 成员绑定

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/me/binding` | 当前用户绑定列表 |
| PUT | `/me/binding` | 更新绑定 |
| PUT | `/me/bindings/sort` | 调整 `sort_order` |
| DELETE | `/me/bindings/{viewer_id}` | 解绑 |
| GET | `/me/season-records` | 当期个人出刀 |
| GET | `/{group_id}/clan-accounts` | 公会账号列表（拉游戏 API） |
| POST | `/{group_id}/bind_account` | 绑定 UID |
| POST | `/{group_id}/unbind_account` | 解绑 UID |

### 队列写操作（需权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/set_notice` | 新增预约/申请等 |
| POST | `/delete_notice` | 删除通知 |
| POST | `/delete_notice_special` | 特殊删除 |
| DELETE | `/{group_id}/notice/{notice_id}` | 按 ID 删除 |
| POST | `/correct_dao` | 修正 DAO |

### 监控（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{group_id}/monitor/accounts` | 监控槽位账号 |
| POST | `/{group_id}/monitor` | 开/关监控 |

### SSE / 轮询（兼容）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{group_id}/renew_dashboard` | 看板更新信号 |
| GET | `/{group_id}/renew_report` | 战报更新信号 |
| GET | `/{group_id}/renew_notice` | 队列更新信号 |

> `POST /{group_id}/boss/refresh` 已废弃，Boss 数据由监控 1 秒轮询自动更新。

---

## 管理运维 API（`webui/web_admin_routes.py`）

Cookie 登录 + KCR 管理员角色。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/me/role` | 当前用户 KCR 角色 |
| GET | `/monitor` | 监控状态 |
| GET | `/binding-groups` | 可绑定的群 |
| GET | `/bindings` | 成员 UID 绑定列表 |
| POST | `/bindings/batch` | 批量代绑 |
| PUT | `/bindings` | 更新绑定 |
| DELETE | `/bindings/{binding_id}` | 删除绑定 |
| GET | `/logs` | 运维日志 |
| GET | `/admins` | 委派管理员列表 |
| POST | `/admins` | 任命（超管） |
| DELETE | `/admins/{qq_id}` | 撤销（超管） |

（路径均相对于 `base_path`，与成员 API 同 app。）

---

## Admin OpenAPI（`webui/admin_api.py`）

Header：`X-Admin-Key`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/admin/config` | 读写配置 |
| GET/POST/DELETE | `/admin/accounts` | 监控账号 CRUD |
| GET/POST/DELETE | `/admin/bindings` | 绑定管理 |
| POST | `/admin/users/import` | 批量导入用户 |
| GET | `/admin/monitor` | 监控概览 |
| GET | `/admin/knife_budget` | 刀型预算查询 |
| POST | `/admin/knife_budget/{viewer_id}/reset` | 重置预算 |
| GET | `/guild/{group_id}/status` | 群状态 |
| GET | `/guild/{group_id}/queues` | 队列快照 |

---

## 游戏 API（客户端层）

会战监控主要调用（经 `client/`）：

| 接口 | 用途 |
|------|------|
| `clan_battle/top` | 五王 HP/周目、`damage_history` |
| `clan_battle/reload_detail_info` | 单王 `fighter_num`、挑战者 |
| `clan_battle/battle_log_list` | 战报列表 |
| `clan/info` | 公会成员列表（Web 绑号） |

响应结构与留档见 backup 内 API 参考文档 §4。

---

## 相关文档

- [Web 设计](../design/网页端.md)
- [部署 · 反代与 SSE](../deploy/安装指南.md)
