# 诊断规则示例大全

**版本：** 1.0
**日期：** 2026-03-05
**适用：** AUTO_DIAGNOSE_AND_FIX.md 补充

---

## 📋 内置诊断规则示例

### 1. 端口占用诊断

```yaml
- id: PORT_CONFLICT_001
  name: 端口冲突检测
  category: network
  severity: high
  description: 检测端口是否被占用
  check:
    type: port
    ports: [80, 443, 3000, 5432, 6379, 8080, 8088]
  fix:
    type: change_port
    strategy: auto_increment
    message: "端口 {port} 被占用，已自动切换为 {new_port}"
  examples:
    - scenario: "Gitea 部署时 3000 端口被占用"
      expected: "自动切换为 3001 端口"
      actual_command: "lsof -i :3000"
      actual_fix: "export GITEA_PORT=3001"
```

### 2. 磁盘空间诊断

```yaml
- id: DISK_SPACE_001
  name: 磁盘空间不足
  category: storage
  severity: high
  description: 检测磁盘空间是否充足
  check:
    type: disk
    threshold_percent: 80
    paths: ["/", "/var", "/opt"]
  fix:
    type: cleanup
    targets:
      - docker_prune: "docker system prune -af"
      - apt_clean: "apt-get clean"
      - journal_clean: "journalctl --vacuum-time=7d"
    message: "磁盘空间不足，已清理 {freed_space}GB"
  examples:
    - scenario: "Docker 镜像占用过多空间"
      expected: "执行 docker system prune -af 清理 5GB"
```

### 3. K3S 服务健康诊断

```yaml
- id: SERVICE_HEALTH_001
  name: K3S 服务健康检测
  category: service
  severity: critical
  description: 检测 K3S 服务是否正常运行
  check:
    type: service
    name: k3s
    expected_status: running
  fix:
    type: restart_service
    service: k3s
    steps:
      - "systemctl restart k3s"
      - "sleep 10"
      - "kubectl get nodes"
    message: "K3S 服务异常，已尝试重启"
  examples:
    - scenario: "K3S 服务未运行"
      expected: "systemctl restart k3s 后服务正常"
```

### 4. Pod 健康诊断

```yaml
- id: POD_HEALTH_001
  name: Pod 健康检测
  category: service
  severity: high
  description: 检测 K8s Pod 状态
  check:
    type: kubectl
    command: "get pods --all-namespaces --field-selector=status.phase!=Running,status.phase!=Succeeded"
    expected_empty: true
  fix:
    type: kubectl
    command: "delete pod {pod_name} -n {namespace} --force --grace-period=0"
    message: "发现异常 Pod，已删除并触发重建"
  examples:
    - scenario: "Harbor Core Pod CrashLoopBackOff"
      expected: "删除 Pod 后自动重建，状态恢复正常"
```

### 5. Harbor 连通性诊断

```yaml
- id: HARBOR_CONNECTIVITY_001
  name: Harbor 镜像仓库连通性
  category: network
  severity: high
  description: 检测 Harbor 镜像仓库是否可访问
  check:
    type: http
    url: "http://harbor.sisys.local/api/v2.0/ping"
    method: GET
    expected_status: 200
    timeout: 10
  fix:
    type: restart_service
    service: harbor-core
    steps:
      - "kubectl rollout restart deployment/harbor-core -n harbor"
      - "sleep 30"
      - "curl http://harbor.sisys.local/api/v2.0/ping"
    message: "Harbor 服务异常，已尝试重启"
  examples:
    - scenario: "Harbor API 返回 503"
      expected: "重启 harbor-core 后 API 恢复正常"
```

### 6. TLS 证书有效期诊断

```yaml
- id: CERT_EXPIRY_001
  name: TLS 证书有效期检测
  category: security
  severity: medium
  description: 检测 TLS 证书有效期
  check:
    type: certificate
    domains:
      - "gitea.sisys.local"
      - "harbor.sisys.local"
      - "argocd.sisys.local"
    days_before_expire: 30
  fix:
    type: renew_certificate
    steps:
      - "kubectl delete secret gitea-tls -n gitea"
      - "kubectl delete secret harbor-tls -n harbor"
      - "kubectl delete secret argocd-tls -n argocd"
      - "cert-manager 自动续期"
    message: "证书即将过期，已触发续期流程"
  examples:
    - scenario: "Gitea 证书剩余 15 天过期"
      expected: "删除 Secret 后 cert-manager 自动续期"
```

### 7. 内存使用率诊断

```yaml
- id: MEMORY_USAGE_001
  name: 内存使用率检测
  category: resource
  severity: high
  description: 检测系统内存使用率
  check:
    type: memory
    threshold_percent: 90
  fix:
    type: cleanup
    targets:
      - kill_zombie_pods: "kubectl delete pod --field-selector=status.phase==Failed --all-namespaces"
      - clear_page_cache: "echo 3 > /proc/sys/vm/drop_caches"
      - restart_memory_hogs: "kubectl rollout restart deployment -n harbor"
    message: "内存使用率过高 ({usage}%)，已清理 {freed_memory}MB"
  examples:
    - scenario: "内存使用率 95%"
      expected: "清理后降至 75%"
```

### 8. Gitea 仓库连接诊断

```yaml
- id: GITEA_REPO_001
  name: Gitea 仓库连接检测
  category: git
  severity: high
  description: 检测 Gitea 仓库连接
  check:
    type: git
    url: "http://gitea.sisys.local/admin/sisys-config.git"
    expected_accessible: true
  fix:
    type: check_service
    service: gitea
    steps:
      - "kubectl get pods -n gitea"
      - "kubectl logs -n gitea -l app.kubernetes.io/name=gitea"
    message: "Gitea 仓库连接失败，请检查 Gitea 服务"
  examples:
    - scenario: "Git clone 返回 403"
      expected: "检查 Gitea 权限配置"
```

### 9. ArgoCD 同步状态诊断

```yaml
- id: ARGOCD_SYNC_001
  name: ArgoCD 同步状态检测
  category: gitops
  severity: critical
  description: 检测 ArgoCD 应用同步状态
  check:
    type: argocd
    command: "app list"
    expected_synced: true
  fix:
    type: argocd
    command: "app sync {app_name}"
    message: "ArgoCD 应用未同步，已触发同步"
  examples:
    - scenario: "sisys-app 显示 OutOfSync"
      expected: "执行 argocd app sync sisys-app 后同步成功"
```

### 10. Docker 守护进程诊断

```yaml
- id: DOCKER_DAEMON_001
  name: Docker 守护进程健康检测
  category: container
  severity: critical
  description: 检测 Docker 守护进程是否正常运行
  check:
    type: docker
    command: "info"
    expected_success: true
  fix:
    type: restart_service
    service: docker
    steps:
      - "systemctl restart docker"
      - "docker info"
    message: "Docker 守护进程异常，已尝试重启"
  examples:
    - scenario: "docker info 返回错误"
      expected: "重启 Docker 服务后恢复正常"
```

---

## 📋 自定义诊断规则模板

### 应用健康检查模板

```yaml
- id: CUSTOM_APP_{APP_NAME}
  name: {APP_NAME} 健康检测
  category: application
  severity: critical
  description: 检测 {APP_NAME} 应用是否正常运行
  check:
    type: http
    url: "http://{app_url}/health"
    method: GET
    expected_status: 200
    timeout: 10
    headers:
      Authorization: "Bearer {token}"
  fix:
    type: kubectl
    command: "rollout restart deployment/{app_name} -n {namespace}"
    message: "{APP_NAME} 应用异常，已触发重启"
```

### 数据库连接检查模板

```yaml
- id: CUSTOM_DB_{DB_NAME}
  name: {DB_NAME} 数据库连接检测
  category: database
  severity: critical
  description: 检测 {DB_NAME} 数据库连接
  check:
    type: tcp
    host: "{db_host}"
    port: {db_port}
    timeout: 5
  fix:
    type: restart_service
    service: "{db_service}"
    message: "{DB_NAME} 数据库连接失败，已尝试重启"
```

### Redis 缓存检查模板

```yaml
- id: CUSTOM_REDIS_{INSTANCE}
  name: Redis {INSTANCE} 健康检测
  category: cache
  severity: medium
  description: 检测 Redis 缓存服务
  check:
    type: redis_ping
    host: "{redis_host}"
    port: {redis_port}
    password: "{redis_password}"
  fix:
    type: restart_service
    service: redis
    message: "Redis 服务异常，已尝试重启"
```

---

## 📊 诊断报告示例

```
┌─────────────────────────────────────────────────────────────┐
│              SISYS 系统诊断报告                             │
│  时间：2026-03-05 14:30:00                                  │
├─────────────────────────────────────────────────────────────┤
│ [✅] PORT_CONFLICT_001: 端口冲突检测 - 通过                 │
│ [✅] DISK_SPACE_001: 磁盘空间检测 - 通过 (65% 使用)          │
│ [⚠️] POD_HEALTH_001: Pod 健康检测 - 2 个异常 Pod             │
│      → 已自动删除异常 Pod                                   │
│ [✅] SERVICE_HEALTH_001: K3S 服务健康 - 通过                │
│ [✅] HARBOR_CONNECTIVITY_001: Harbor 连通性 - 通过          │
│ [✅] CERT_EXPIRY_001: TLS 证书有效期 - 通过 (剩余 280 天)     │
│ [✅] MEMORY_USAGE_001: 内存使用率 - 通过 (72% 使用)          │
│ [✅] GITEA_REPO_001: Gitea 仓库连接 - 通过                  │
│ [✅] ARGOCD_SYNC_001: ArgoCD 同步状态 - 通过                │
│ [✅] DOCKER_DAEMON_001: Docker 守护进程 - 通过              │
├─────────────────────────────────────────────────────────────┤
│ 诊断完成：10 通过，0 警告，0 失败                           │
│ 系统状态：健康 ✅                                           │
└─────────────────────────────────────────────────────────────┘
```

---

**文档状态：** ✅ 完整
**规则数量：** 10 个内置规则 + 3 个模板
