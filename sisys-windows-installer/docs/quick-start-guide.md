# SISYS 快速入门指南

欢迎使用 SISYS 企业战略规划管理系统！

---

## 🎉 恭喜！SISYS 已成功安装

您现在可以通过以下方式访问 SISYS：

### 🌐 访问地址

| 页面 | 地址 |
|------|------|
| **欢迎页面** | http://localhost:8080/welcome |
| **登录页面** | http://localhost:8080/login |
| **健康检查** | http://localhost:8080/health |

### 🔐 初始登录凭据

- **地址**: http://localhost:8080/login
- **账号**: `admin`
- **密码**: `sisys123`

> ⚠️ **重要**: 首次登录后请立即修改密码！

---

## 📚 快速入门

### 1. 第一次使用（3 分钟）

1. 打开浏览器访问：http://localhost:8080/login
2. 使用初始凭据登录
3. 修改密码
4. 开始使用！

### 2. 主要功能

- 📄 **文档管理**: 上传、解析、检索各类文档
- 🔍 **智能检索**: 混合检索（Dense + BM25 + Graph）
- 🧰 **战略工具箱**: 23 种战略分析工具
- 🤖 **Agent 协作**: 多 Agent 协作完成任务
- 📊 **战略规划**: BLM 战略规划流程

### 3. 常见问题

**Q: 如何启动/停止服务？**

```powershell
# 启动服务
cd "C:\Program Files\SISYS"
docker compose up -d

# 停止服务
docker compose down
```

**Q: 如何查看日志？**

```powershell
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f sisys-app
```

**Q: 如何备份数据？**

数据存储在 `%USERPROFILE%\SISYS\data` 目录，可以直接复制备份。

---

## 🔧 系统状态

### 服务检查

```powershell
# 检查所有服务状态
docker compose ps

# 健康检查
curl http://localhost:8080/health
```

### 端口信息

| 服务 | 端口 | 说明 |
|------|------|------|
| SISYS App | 8080 | 主应用 |
| Redis | 6379 | 缓存 |
| PostgreSQL | 5432 | 数据库 |
| Qdrant | 6333 | 向量数据库 |
| MinIO | 9000/9001 | 对象存储 |

---

## 📞 技术支持

### 联系方式

| 渠道 | 信息 |
|------|------|
| **邮箱** | support@sisys.local |
| **电话** | 400-XXX-XXXX |
| **在线帮助** | http://localhost:8080/help |
| **文档** | http://localhost:8080/docs |

### 故障排查

如果遇到问题，请：

1. 查看安装日志：`%TEMP%\SISYS-Setup.log`
2. 查看应用日志：`%USERPROFILE%\SISYS\logs\sisys.log`
3. 运行一键诊断（如安装程序提供）
4. 联系技术支持（提供错误报告）

---

## 📖 更多资源

- **用户手册**: http://localhost:8080/docs/user-guide
- **API 文档**: http://localhost:8080/docs/api
- **开发者指南**: http://localhost:8080/docs/developer
- **常见问题**: http://localhost:8080/faq

---

**版本**: 0.14.0
**安装日期**: $(Get-Date -Format "yyyy-MM-dd")
**操作系统**: Windows 10/11

祝您使用愉快！🎊
