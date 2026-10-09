# 游戏 API 脱敏样本

供二次开发与离线测试使用。**不含**真实 QQ、公会名、viewer_id、token。

| 文件 | 对应接口 | 用途 |
|------|----------|------|
| `envelope_success.sample.json` | 通用信封 | `result_code=1` |
| `envelope_error.sample.json` | 通用错误 | `server_error` |
| `clan_battle_top.sample.json` | `clan_battle/top` | Boss 镜像 + damage_history |
| `reload_detail_info.sample.json` | `clan_battle/reload_detail_info` | fighter_num |
| `boss_phases.sample.json` | Satroki phases | 预览脚本离线 Boss 名/HP |

完整字段说明见 `docs/backup/blueprint/PCR会战API接口留档参考.md`（归档）。
