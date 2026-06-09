# 安全说明

## 敏感信息

本项目不应该提交以下内容：

| 类型 | 示例 |
| --- | --- |
| 登录凭据 | 管理员密码、用户初始密码、临时 SSH key |
| 真实运行数据 | `data/`、`auth.json`、`fake-ui.db`、`fake-ui.db-wal`、`fake-ui.db-shm` |
| 证书和密钥 | `.pem`、TLS 私钥、Reality private key |
| 生产配置 | `.env`、`.env.production`、真实域名和代理账号 |

仓库只保留 `.env.example` 作为配置模板。生产部署时请复制为 `.env` 并填写自己的域名、路径和服务参数。

## 上报安全问题

请不要在公开 Issue 中贴出真实域名、节点订阅、用户密码、代理账号或服务端密钥。建议先用私有渠道联系维护者，确认影响范围后再公开修复记录。

## 默认部署建议

| 项目 | 建议 |
| --- | --- |
| 面板入口 | 必须走 HTTPS，后台接口不要裸露在公网明文 HTTP |
| 管理员密码 | 首次部署后立即修改，并避免复用其他服务密码 |
| 订阅链接 | 定期轮换订阅 token，发现泄露后立即重置 |
| 防火墙 | 只开放必要端口，例如 80、443、Reality/HY2 所需端口 |
| 备份 | 备份文件应离线保存，不要放在 Web 根目录 |

## 面板加固建议

| 项目 | 建议 |
| --- | --- |
| Cookie | 生产环境必须使用 HTTPS，面板会设置 `HttpOnly`、`Secure` 和 `SameSite=Lax` |
| CSRF | 已登录 API 写操作需要 `X-CSRF-Token`，前端会从登录/session 响应中自动携带 |
| 登录防护 | 同一 IP 和用户名的失败登录会被短时间限速，登录成功/失败会写入审计日志 |
| 反代安全头 | Nginx 模板包含 HSTS、`X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy` 和 `Permissions-Policy` |
| 生产暴露 | 面板进程只监听 `127.0.0.1:9100`，不要直接暴露该端口到公网 |
