# 运维手册

## 本地测试

| 检查 | 命令 |
| --- | --- |
| 编译全部 Python 文件 | `bash scripts/test-local.sh` 或 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-local.ps1` |
| 单元测试 | `python -m pytest -q` |
| PowerShell 一键测试 | `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-local.ps1` |

## Windows 部署到 Compose 机器

从 Windows/PowerShell 部署时不要直接写 `git archive | ssh ... tar`，也不要把远端 `$(date ...)`、`$var`、复杂管道写在 PowerShell 的 SSH 字符串里；PowerShell 会先解析这些内容，here-string 也容易带 BOM/CRLF。

使用项目内置脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-compose-windows.ps1 -HostAlias fake-ui-sg -RemoteDir /opt/fake-airport
```

脚本会：

| 步骤 | 说明 |
| --- | --- |
| 本地测试 | 默认先运行 `scripts/test-local.ps1` |
| 打包 | 使用 `git archive -o` 生成本地 tar 文件，不走 PowerShell 二进制管道 |
| 上传 | 通过 `scp` 上传 tar 和远端部署脚本 |
| 远端脚本 | 使用 UTF-8 无 BOM、LF 换行写入，再由远端 `bash` 执行 |
| 备份 | 在远端 `/root/fake-airport-backups/` 生成部署前备份 |
| 同步 | 保留 `.env`、`data/`、`generated/`，只覆盖代码文件 |
| 验证 | 远端运行 pytest，并重建 `panel` 服务，等待健康检查 |

可选参数：

| 参数 | 用途 |
| --- | --- |
| `-SkipTests` | 跳过本地测试，仅建议已刚跑过测试时使用 |
| `-SkipBuild` | 只同步代码和远端测试，不重建 panel 容器 |
| Bash 一键测试 | `bash scripts/test-local.sh` |

## Docker Compose 部署流程

全新 VPS 推荐直接运行：

```bash
sudo bash scripts/install-fresh-vps.sh
```

运行前请先把脚本提示的域名 A 记录解析到 VPS 公网 IP，并关闭 CDN/代理模式。

1. 复制配置模板：

```bash
cp .env.example .env
```

2. 修改 `.env` 中的域名、邮箱、端口、证书和服务参数。

3. 启动：

```bash
docker compose up -d --build
```

4. 查看状态：

```bash
docker compose ps
docker compose logs --tail=100 panel
```

## 生产上线检查

| 阶段 | 检查项 |
| --- | --- |
| 上线前 | 备份面板目录、Xray 配置、Hysteria2 配置；确认备份包含 `fake-ui.db`、`fake-ui.db-wal`、`fake-ui.db-shm` |
| 上线前 | 远端 `bash scripts/test-local.sh` |
| 上线前 | 远端 `python3 -m pytest -q` |
| 上线前 | 临时端口启动面板，测试 `/login`、`/api/session`、`/api/users`、`/api/nodes` |
| 上线 | 重启 `xray-proxy-panel` |
| 上线后 | 检查面板 HTTPS、Xray active、Hysteria2 running |

## 加密货币支付运维

| 项目 | 要求 |
| --- | --- |
| 钱包权限 | 面板只需要收款地址和公开查询端点，不需要也不能导入钱包私钥、助记词或可签名凭据 |
| 支持范围 | USDT/USDC 支持 Ethereum mainnet 与 BSC；ETH 使用 Ethereum mainnet；BNB 使用 BSC；BTC 使用公开区块链 API |
| 汇率 | 订单按 USD 计价，稳定币固定 1 USD；BTC/ETH/BNB 可在管理员设置里填写 USD 覆盖价格 |
| 链上校验 | 用户提交 txid 后，系统按配置的 RPC/API、收款地址、token 合约、金额和确认数校验到账 |
| 生产配置 | 生产 RPC URL、API Key、真实收款地址写入面板运行数据，不要提交到 Git |
| 测试流程 | 新增或修改收款方式后，先在测试机用小额订单验证二维码、txid 提交、确认数和自动开通 |
| 上线边界 | 香港生产机上线前必须先备份 `data/`，并在新加坡测试机完成回归和回滚演练 |

## 生产环境变量

开源仓库默认使用 `example.com` 占位值。生产环境必须覆盖：

| 变量 | 说明 |
| --- | --- |
| `PANEL_DOMAIN` | 面板域名 |
| `HY2_DOMAIN` | Hysteria2 域名 |
| `PUBLIC_BASE_URL` | 面板公开访问地址 |
| `DEFAULT_VLESS_ADDRESS` | 默认 VLESS 地址 |
| `DEFAULT_VLESS_NAME` | 默认 VLESS 节点名 |
| `DEFAULT_HY2_NAME` | 默认 Hysteria2 节点名 |
| `HY2_MASQUERADE_URL` | Hysteria2 伪装站点 |

systemd 部署时建议使用 override 文件注入环境变量，避免把生产域名写死到代码。

## 回滚策略

| 对象 | 回滚方式 |
| --- | --- |
| 面板代码 | 从上线前 tar 备份恢复项目目录 |
| Xray 配置 | 使用 `XRAY_BACKUP_DIR` 中最近的配置恢复 |
| Hysteria2 配置 | 使用 `HY2_BACKUP_DIR` 中最近的配置恢复 |
| Docker Compose 状态 | 使用 `scripts/import-compose-data.sh` 导入导出的状态包 |
