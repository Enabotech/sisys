# 🎯 Gitea Runner 部署 - 最终实施报告

**日期**: 2026-04-02  
**状态**: ✅ 完成  
**架构**: 双容器 Sidecar (安全优化版)  

---

## 📊 实施总结

### ✅ 已完成任务

| 任务 | 状态 | 说明 |
|------|------|------|
| **单容器技术验证** | ✅ 完成 | 发现 rootless 在 K3s/WSL2 不可行 |
| **双容器方案采纳** | ✅ 完成 | 当前环境最优解 |
| **安全优化配置** | ✅ 完成 | 节点隔离 + NetworkPolicy |
| **CI Workflow 修复** | ✅ 完成 | build-image + integration-tests |
| **部署验证** | ✅ 完成 | Pod 运行正常，Docker/Buildx 可用 |

---

## 🔧 CI Workflow 修复

### 修复 1: build-image Job

**修改前**:
```yaml
options: --privileged  # ❌ 缺少 --user root
```

**修改后**:
```yaml
options: --user root --privileged  # ✅ 修复
```

**新增步骤**:
```yaml
- name: 验证 Docker 环境
  run: |
    docker --version
    docker info
    docker buildx version
```

---

### 修复 2: integration-tests Job

**修改前**:
```yaml
options: --user root --privileged --gpus all
```

**修改后**:
```yaml
options: --user root --gpus all  # ✅ 优化：移除 --privileged
```

**理由**: Job 容器本身不需要 privileged（由 Runner 的 docker-dind 容器提供）

---

## 🏗️ 最终架构

```
┌─────────────────────────────────────────────────────────────┐
│  Namespace: gitea-actions (PSS Baseline)                    │
│  Node Selector: role=ci-runner                              │
│  NetworkPolicy: 限制出站 (Gitea/Harbor/DNS)                 │
├─────────────────────────────────────────────────────────────┤
│  Pod: gitea-runner-dind-0                                   │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Container 1: runner (非特权)                          │  │
│  │  - capabilities: drop ALL                              │  │
│  │  - DOCKER_HOST: tcp://127.0.0.1:2375                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Container 2: docker-dind (特权)                       │  │
│  │  - privileged: true                                    │  │
│  │  - Listen: tcp://127.0.0.1:2375                        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  CI Workflow (.gitea/workflows/ci.yaml)                     │
│  - code-quality: --user root                                │
│  - unit-tests: --user root --gpus all                       │
│  - integration-tests: --user root --gpus all                │
│  - security-scan: --user root                               │
│  - build-image: --user root --privileged ✅                 │
│  - push-image: --user root                                  │
│  - auto-deploy: --user root                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 配置清单

### 部署配置

| 文件 | 路径 | 说明 |
|------|------|------|
| **Runner StatefulSet** | `deployments/gitea-runner/gitea-runner-dind-secured.yaml` | 安全优化版 |
| **CI Workflow** | `.gitea/workflows/ci.yaml` | 已修复 |

### 关键配置

```yaml
# Runner 标签
labels: ubuntu-latest, docker, k8s, linux, dind

# Docker 连接
DOCKER_HOST: tcp://127.0.0.1:2375

# 节点隔离
nodeSelector:
  role: ci-runner
tolerations:
  - key: ci
    operator: Exists
    effect: NoSchedule

# NetworkPolicy
egress:
  - DNS (UDP 53)
  - Gitea (TCP 3000)
  - Harbor (TCP 80/443)
  - Docker Hub (TCP 443)
  # Kubernetes API: ❌ 禁止
```

---

## ✅ 验证结果

### Runner 状态
```
NAME                  READY   STATUS    RESTARTS   AGE
gitea-runner-dind-0   2/2     Running   0          2h
```

### Docker 验证
```
Server Version: 28.5.2
Storage Driver: overlay2
Buildx: v0.29.1
```

### Runner 注册
```
runner: gitea-runner-dind-0, with version: v0.3.0,
with labels: [ubuntu-latest docker k8s linux dind],
declare successfully
```

---

## 🚀 下一步：CI 完整测试

### 触发测试

```bash
# 提交 CI 修复
git add .gitea/workflows/ci.yaml
git commit -m "fix: 修复 CI Workflow Docker 权限配置

- build-image: 添加 --user root 到 container options
- integration-tests: 移除冗余的 --privileged
- 添加 Docker 环境验证步骤

与新的双容器 Runner 架构兼容。"
git push
```

### 验证清单

访问 Gitea Actions:
```
https://gitea.sisys.local/{org}/{repo}/actions
```

- [ ] code-quality 通过
- [ ] unit-tests 通过
- [ ] integration-tests 通过
- [ ] security-scan 通过
- [ ] **build-image 通过** (关键！Buildx 验证)
- [ ] push-image 通过
- [ ] auto-deploy 通过

---

## 📝 经验教训

### 单容器方案教训

1. **rootless ≠ --rootless flag**
   - rootless 是一整套 runtime（rootlesskit + userns + slirp4netns）
   - 不是简单的命令行参数

2. **PSS 安全策略限制**
   - rootlesskit 需要 SYS_ADMIN/SYS_PTRACE
   - rootlesskit 需要 seccomp: Unconfined
   - PSS Baseline 禁止上述配置

3. **WSL2 环境约束**
   - user namespace 支持不完整
   - cgroup v2 + systemd 配置复杂

### 双容器方案优势

1. **已验证可用** - 在 K3s/WSL2 环境稳定运行
2. **安全性可接受** - 通过缓解措施补偿
3. **易维护** - 配置清晰，故障易排查

---

## 🎯 架构决策记录

### 决策：双容器 Sidecar 方案

**背景**: 单容器 all-in-one rootless 在 K3s/WSL2 环境不可行

**决策**: 采用双容器 Sidecar 方案

**理由**:
1. 单容器方案需要 PSS 豁免，违反安全策略
2. 双容器方案已验证可用，功能完整
3. 安全性妥协通过多层缓解措施补偿

**缓解措施**:
- 仅 docker-dind 容器特权
- Docker API 仅监听 localhost
- 无 hostNetwork
- NetworkPolicy 限制出站
- 节点隔离（专用 CI 节点）
- RBAC 最小权限

---

## 📚 参考文档

- [Gitea Act Runner 文档](https://docs.gitea.com/usage/actions/act-runner)
- [Docker Rootless 模式](https://docs.docker.com/engine/security/rootless/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [K3s 安全最佳实践](https://docs.k3s.io/security/best-practices)

---

**报告完成** 🎯
