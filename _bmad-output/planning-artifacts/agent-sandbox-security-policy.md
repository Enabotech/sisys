# 附录 K：Agent 沙箱安全策略设计文档

**版本：** 1.0.0
**状态：** 新增（解决架构评审 H6 问题："Agent 沙箱安全边界模糊"）
**创建日期：** 2026-02-25
**关联章节：** 第 15.3 节（安全性设计）、第 17.2 节（工具箱架构设计）

---

## 目录

1. [沙箱安全架构概述](#1-沙箱安全架构概述)
2. [沙箱隔离层设计](#2-沙箱隔离层设计)
3. [代码执行安全流程](#3-代码执行安全流程)
4. [沙箱逃逸检测与防护](#4-沙箱逃逸检测与防护)
5. [恶意代码防护](#5-恶意代码防护)
6. [沙箱监控与审计](#6-沙箱监控与审计)
7. [实现代码示例](#7-实现代码示例)
8. [验收标准](#8-验收标准)

---

## 1. 沙箱安全架构概述

### 1.1 沙箱威胁模型

基于 STRIDE 威胁建模框架，识别 Agent 沙箱面临的六大威胁类别：

| 威胁类别 | 具体威胁场景 | 影响等级 | 缓解措施 |
|---------|-------------|---------|---------|
| **Spoofing（伪装）** | 恶意 Agent 伪装成合法工具执行代码 | 🔴 高 | MCP 协议认证 + 工具签名验证 |
| **Tampering（篡改）** | 攻击者篡改沙箱内执行的代码 | 🔴 高 | 代码完整性校验 + WORM 存储 |
| **Repudiation（抵赖）** | Agent 否认执行的恶意操作 | 🟠 中 | 完整审计日志 + 不可篡改记录 |
| **Information Disclosure（信息泄露）** | 沙箱内代码访问敏感数据 | 🔴 高 | 数据隔离 + 最小权限原则 |
| **Denial of Service（拒绝服务）** | 恶意代码消耗过多资源 | 🟠 中 | 资源配额限制 + 超时控制 |
| **Elevation of Privilege（权限提升）** | 沙箱逃逸获取宿主机权限 | 🔴 高 | gVisor 隔离 + Seccomp 过滤 |

### 1.2 安全边界定义

```
┌─────────────────────────────────────────────────────────────────┐
│                        宿主机 (Host)                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    安全边界层                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Seccomp     │  │ Capability  │  │ 网络        │       │  │
│  │  │ 过滤器      │  │ Drop        │  │ 白名单      │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │ gVisor      │     │ gVisor      │     │ gVisor      │       │
│  │ 容器 A      │     │ 容器 B      │     │ 容器 C      │       │
│  │ (数值计算)  │     │ (统计分析)  │     │ (图表渲染)  │       │
│  │ CPU:2/Mem:2G│     │ CPU:4/Mem:4G│     │ CPU:2/Mem:4G│       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│         │                    │                    │             │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    文件系统边界                            │  │
│  │  - 只读挂载：/usr, /etc, /bin                              │  │
│  │  - 临时写入：/tmp/sandbox_{uuid} (TTL=24h)                 │  │
│  │  - 禁止访问：/host, /proc, /sys                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 沙箱类型选择（Docker vs gVisor）

#### 技术方案对比

| 评估维度 | Docker (runc) | gVisor (runsc) | Firecracker | 本系统选择 |
|---------|--------------|----------------|-------------|-----------|
| **隔离级别** | 进程级（命名空间+Cgroups） | 用户空间内核（Sentry） | 硬件级微 VM | gVisor |
| **系统调用覆盖** | 100% | 70-80%（白名单） | 100% | ✅ 满足需求 |
| **性能开销** | 基准（0%） | 20-50% | 较高 | ✅ 可接受 |
| **启动时间** | <100ms | 200-500ms | ~150ms | ✅ 可接受 |
| **内存占用** | 低 | 中等（~200MB 基础） | 高（~500MB） | ✅ 可接受 |
| **安全性** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 满足企业级 |
| **运维复杂度** | 低 | 中等 | 高 | ✅ 可管理 |
| **成本** | 低 | 中等 | 高 | ✅ 成本最优 |

#### 决策矩阵

```
                    安全性
                      ▲
                      │
         Firecracker  │     ★ gVisor（生产环境）
              ★       │        - 企业级隔离
                      │        - 成本可控
                      │        - 运维可行
    ──────────────────┼──────────────────────▶ 成本效益
                      │
         Docker       │
              ★       │     ★ Docker（开发环境）
                      │        - 快速迭代
                      │        - 调试友好
                      │
```

#### 最终决策

| 环境 | 沙箱类型 | 理由 |
|------|---------|------|
| **生产环境** | gVisor (runsc) | 企业级安全隔离，成本可控，满足合规要求 |
| **开发环境** | Docker (runc) | 快速迭代，调试友好，降低开发门槛 |
| **高威胁场景** | Firecracker | 执行不可信第三方代码时的终极隔离方案 |

---

## 2. 沙箱隔离层设计

### 2.1 文件系统隔离

#### 挂载策略

```yaml
# gVisor 容器挂载配置
mounts:
  # 只读系统目录
  - type: bind
    source: /usr
    target: /usr
    options: ["ro", "nosuid", "noexec"]
  
  - type: bind
    source: /etc
    target: /etc
    options: ["ro", "nosuid"]
  
  - type: bind
    source: /bin
    target: /bin
    options: ["ro", "nosuid", "noexec"]
  
  # 临时写入目录（沙箱隔离）
  - type: tmpfs
    target: /tmp/sandbox_{uuid}
    options: ["rw", "nosuid", "noexec", "size=512M"]
  
  # 只读数据挂载
  - type: bind
    source: /data/readonly/{tenant_id}
    target: /data
    options: ["ro"]
  
  # 禁止访问的目录
  - type: bind
    source: /dev/null
    target: /host
    options: ["ro"]  # 空挂载，阻止访问
  
  - type: bind
    source: /dev/null
    target: /proc
    options: ["ro"]
  
  - type: bind
    source: /dev/null
    target: /sys
    options: ["ro"]
```

#### 文件访问控制矩阵

| 目录路径 | 读权限 | 写权限 | 执行权限 | 说明 |
|---------|-------|-------|---------|------|
| `/usr/*` | ✅ | ❌ | ❌ | 只读系统工具 |
| `/etc/*` | ✅ | ❌ | ❌ | 只读配置 |
| `/bin/*` | ✅ | ❌ | ❌ | 只读二进制 |
| `/tmp/sandbox_{uuid}/*` | ✅ | ✅ | ❌ | 临时工作目录 |
| `/data/*` | ✅ | ❌ | ❌ | 只读数据 |
| `/host/*` | ❌ | ❌ | ❌ | 禁止访问 |
| `/proc/*` | ❌ | ❌ | ❌ | 禁止访问 |
| `/sys/*` | ❌ | ❌ | ❌ | 禁止访问 |
| `/dev/*` | ⚠️ | ❌ | ❌ | 仅基本设备（/dev/null, /dev/zero） |

### 2.2 网络访问控制

#### 网络隔离架构

```
┌─────────────────────────────────────────────────────────────┐
│                    沙箱容器                                  │
│  ┌─────────────┐                                            │
│  │  Agent 代码  │                                            │
│  └──────┬──────┘                                            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              eBPF 网络过滤器 (Cilium)                    ││
│  │  ┌─────────────────────────────────────────────────┐   ││
│  │  │  白名单规则：                                    │   ││
│  │  │  - 允许：api.trusted-finance.com:443            │   ││
│  │  │  - 允许：qdrant.internal:6333                   │   ││
│  │  │  - 允许：redis.internal:6379                    │   ││
│  │  │  - 拒绝：所有其他出站连接                        │   ││
│  │  │  - 拒绝：所有入站连接                            │   ││
│  │  └─────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────┘│
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              网络代理网关                                ││
│  │  - HTTP/HTTPS 代理（认证 + 审计）                        ││
│  │  - DNS 过滤（仅解析白名单域名）                          ││
│  │  - 连接速率限制（100 连接/分钟）                          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

#### 网络白名单配置

```python
NETWORK_WHITELIST = {
    # 允许的域名（支持通配符）
    "allowed_domains": [
        "api.trusted-finance.com",
        "*.qdrant.internal",
        "*.redis.internal",
        "*.minio.internal"
    ],
    
    # 允许的端口
    "allowed_ports": [443, 6333, 6379, 9000],
    
    # 禁止的 IP 范围
    "blocked_cidrs": [
        "10.0.0.0/8",      # 内部网络（除白名单）
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",  # 链路本地
        "127.0.0.0/8"      # 本地回环
    ],
    
    # 协议限制
    "allowed_protocols": ["HTTPS", "DNS"],
    "blocked_protocols": ["HTTP", "FTP", "SMTP", "SSH", "Telnet"]
}
```

### 2.3 资源限制（CPU/内存）

#### 资源配额配置

```yaml
# Kubernetes gVisor Pod 资源配置
apiVersion: v1
kind: Pod
metadata:
  name: sandbox-executor
spec:
  runtimeClassName: gvisor
  containers:
  - name: executor
    image: sisys/sandbox-executor:latest
    resources:
      requests:
        cpu: "2"           # 请求 2 核 CPU
        memory: "2Gi"      # 请求 2GB 内存
      limits:
        cpu: "4"           # 限制 4 核 CPU
        memory: "4Gi"      # 限制 4GB 内存
        ephemeral-storage: "1Gi"  # 临时存储限制
    # OOM 配置
    securityContext:
      oomScoreAdj: 500     # OOM 时优先杀死
  # Pod 级别资源限制
  overhead:
    memory: "200Mi"        # gVisor Sentry 开销
```

#### 资源配额等级

| 任务类型 | CPU 请求 | CPU 限制 | 内存请求 | 内存限制 | 超时 |
|---------|---------|---------|---------|---------|------|
| **简单计算** | 1 核 | 2 核 | 1GB | 2GB | 60s |
| **数值分析** | 2 核 | 4 核 | 2GB | 4GB | 300s |
| **统计分析** | 4 核 | 8 核 | 4GB | 8GB | 600s |
| **图表渲染** | 2 核 | 4 核 | 4GB | 8GB | 300s |
| **模型推理** | 4 核 | 8 核 | 8GB | 16GB | 900s |

### 2.4 系统调用过滤

#### Seccomp 白名单配置

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_AARCH64"],
  "syscalls": [
    {
      "names": [
        "accept", "accept4", "access", "arch_prctl", "bind",
        "brk", "capget", "capset", "chdir", "chmod", "chown",
        "clock_getres", "clock_gettime", "clock_nanosleep",
        "clone", "clone3", "close", "connect", "dup", "dup2",
        "dup3", "epoll_create", "epoll_create1", "epoll_ctl",
        "epoll_pwait", "epoll_wait", "execve", "exit", "exit_group",
        "faccessat", "fchmod", "fchmodat", "fchown", "fchownat",
        "fcntl", "fdatasync", "fgetxattr", "flistxattr", "flock",
        "fork", "fremovexattr", "fsetxattr", "fstat", "fstatfs",
        "fsync", "ftruncate", "futex", "getcwd", "getdents",
        "getdents64", "getegid", "geteuid", "getgid", "getgroups",
        "getpeername", "getpgrp", "getpid", "getppid", "getpriority",
        "getrandom", "getresgid", "getresuid", "getrlimit",
        "getrusage", "getsid", "getsockname", "getsockopt",
        "gettid", "gettimeofday", "getuid", "inotify_add_watch",
        "inotify_init", "inotify_init1", "inotify_rm_watch",
        "ioctl", "kill", "lgetxattr", "link", "linkat", "listen",
        "llistxattr", "lremovexattr", "lseek", "lsetxattr", "lstat",
        "madvise", "memfd_create", "mincore", "mkdir", "mkdirat",
        "mlock", "mlock2", "mlockall", "mmap", "mprotect",
        "mremap", "msync", "munlock", "munlockall", "munmap",
        "nanosleep", "open", "openat", "pipe", "pipe2", "poll",
        "ppoll", "prctl", "pread64", "prlimit64", "pselect6",
        "pwrite64", "read", "readahead", "readlink", "readlinkat",
        "readv", "recvfrom", "recvmmsg", "recvmsg", "remap_file_pages",
        "rename", "renameat", "renameat2", "rmdir", "rt_sigaction",
        "rt_sigpending", "rt_sigprocmask", "rt_sigqueueinfo",
        "rt_sigreturn", "rt_sigsuspend", "rt_sigtimedwait",
        "sched_getaffinity", "sched_getattr", "sched_getparam",
        "sched_get_priority_max", "sched_get_priority_min",
        "sched_getscheduler", "sched_setaffinity", "sched_setattr",
        "sched_setparam", "sched_setscheduler", "sched_yield",
        "seccomp", "select", "semctl", "semget", "semop", "semtimedop",
        "sendfile", "sendmmsg", "sendmsg", "sendto", "set_robust_list",
        "set_tid_address", "setfsgid", "setfsuid", "setgid",
        "setgroups", "setpgid", "setpriority", "setregid", "setresgid",
        "setresuid", "setreuid", "setsid", "setsockopt", "setuid",
        "shmat", "shmctl", "shmdt", "shmget", "shutdown", "sigaltstack",
        "socket", "socketcall", "socketpair", "splice", "stat",
        "statfs", "symlink", "symlinkat", "sync", "sync_file_range",
        "sysinfo", "tee", "tgkill", "time", "timer_create",
        "timer_delete", "timerfd_create", "timerfd_gettime",
        "timerfd_settime", "timer_getoverrun", "timer_gettime",
        "timer_settime", "times", "tkill", "truncate", "umask",
        "uname", "unlink", "unlinkat", "utimensat", "vfork",
        "vmsplice", "wait4", "waitid", "write", "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

#### 禁止的系统调用

| 系统调用 | 风险等级 | 禁止原因 |
|---------|---------|---------|
| `ptrace` | 🔴 高 | 进程跟踪，可用于调试逃逸 |
| `mount`/`umount` | 🔴 高 | 挂载文件系统，可能突破隔离 |
| `reboot` | 🔴 高 | 重启系统 |
| `swapon`/`swapoff` | 🔴 高 | 操作交换空间 |
| `init_module`/`delete_module` | 🔴 高 | 加载/删除内核模块 |
| `kexec_load` | 🔴 高 | 加载新内核 |
| `personality` | 🟠 中 | 修改进程执行环境 |
| `setns` | 🟠 中 | 加入命名空间，可能突破隔离 |

---

## 3. 代码执行安全流程

### 3.1 代码静态分析

#### 分析流程

```
┌─────────────────┐
│  Agent 生成代码  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    静态分析引擎                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ AST 解析    │  │ 控制流分析  │  │ 数据流分析  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              规则引擎检测                                ││
│  │  - 危险函数调用检测（eval, exec, subprocess）           ││
│  │  - 文件访问模式检测（open, os.system）                  ││
│  │  - 网络访问模式检测（socket, requests, urllib）         ││
│  │  - 系统调用模式检测（ctypes, ctypes.util）              ││
│  │  - 动态导入检测（__import__, importlib）                ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    风险评估报告                              │
│  - 风险评分：0-100                                          │
│  - 风险等级：低/中/高/严重                                   │
│  - 详细问题列表 + 修复建议                                   │
└─────────────────────────────────────────────────────────────┘
```

#### 静态分析规则示例

```python
# 静态分析规则定义
STATIC_ANALYSIS_RULES = {
    "dangerous_functions": {
        "severity": "HIGH",
        "patterns": [
            "eval", "exec", "compile",  # 代码执行
            "os.system", "os.popen", "subprocess.*",  # 系统调用
            "__import__", "importlib.import_module",  # 动态导入
            "ctypes.CDLL", "ctypes.cdll",  # C 库调用
            "socket.socket", "requests.get", "urllib.*",  # 网络访问
            "open.*('/etc/.*')", "open.*('/proc/.*')",  # 敏感文件
        ]
    },
    "file_operations": {
        "severity": "MEDIUM",
        "patterns": [
            "os.remove", "os.unlink", "shutil.rmtree",  # 删除操作
            "os.rename", "shutil.move",  # 移动操作
            "os.chmod", "os.chown",  # 权限修改
        ]
    },
    "network_operations": {
        "severity": "HIGH",
        "patterns": [
            "socket.*", "http.client.*", "urllib.request.*",
            "requests.*", "aiohttp.*", "httpx.*",
        ]
    }
}
```

### 3.2 代码执行前验证

#### 验证检查清单

```python
class PreExecutionValidator:
    """代码执行前验证器"""
    
    async def validate(self, code: str, context: ExecutionContext) -> ValidationResult:
        checks = [
            self._check_code_signature(code),           # 代码签名验证
            self._check_static_analysis(code),          # 静态分析
            self._check_resource_quota(context),        # 资源配额
            self._check_network_policy(context),        # 网络策略
            self._check_file_access(context),           # 文件访问
            self._check_rate_limit(context.tenant_id),  # 速率限制
        ]
        
        results = await asyncio.gather(*checks)
        
        if all(r.passed for r in results):
            return ValidationResult(passed=True)
        else:
            failed_checks = [r for r in results if not r.passed]
            return ValidationResult(
                passed=False,
                failures=[f.reason for f in failed_checks]
            )
```

#### 验证检查项

| 检查项 | 检查内容 | 失败处理 |
|-------|---------|---------|
| **代码签名验证** | 验证生成代码的 Agent 身份和完整性 | 拒绝执行 |
| **静态分析** | 检测危险函数和模式 | 评分<80 拒绝执行 |
| **资源配额** | 检查租户剩余资源配额 | 返回配额错误 |
| **网络策略** | 验证网络访问在白名单内 | 拒绝执行 |
| **文件访问** | 验证文件路径在允许范围内 | 拒绝执行 |
| **速率限制** | 检查执行频率是否超限 | 返回 429 错误 |

### 3.3 执行中监控

#### 监控指标

```python
# 执行中监控指标
EXECUTION_METRICS = {
    # 资源使用
    "cpu_usage_percent": Gauge("sandbox_cpu_usage", "CPU 使用率"),
    "memory_usage_bytes": Gauge("sandbox_memory_usage", "内存使用量"),
    "disk_io_bytes": Counter("sandbox_disk_io", "磁盘 IO"),
    "network_io_bytes": Counter("sandbox_network_io", "网络 IO"),
    
    # 执行状态
    "execution_duration_seconds": Histogram("sandbox_execution_duration", "执行时长"),
    "syscalls_count": Counter("sandbox_syscalls", "系统调用次数"),
    "file_operations_count": Counter("sandbox_file_ops", "文件操作次数"),
    
    # 安全事件
    "blocked_syscalls": Counter("sandbox_blocked_syscalls", "被阻止的系统调用"),
    "blocked_network_attempts": Counter("sandbox_blocked_network", "被阻止的网络访问"),
    "policy_violations": Counter("sandbox_policy_violations", "策略违规"),
}
```

#### 实时监控流程

```
┌─────────────────────────────────────────────────────────────┐
│                    沙箱执行容器                              │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ eBPF 探针   │  │ cgroups v2  │  │ 审计日志    │         │
│  │ (系统调用)  │  │ (资源使用)  │  │ (文件操作)  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              指标收集器 (OpenTelemetry)                  ││
│  │  - 采集频率：1 秒                                        ││
│  │  - 上报频率：10 秒                                       ││
│  │  - 目标：Prometheus + Jaeger                            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 3.4 执行后审计

#### 审计日志结构

```python
class ExecutionAuditLog(BaseModel):
    """执行审计日志"""
    
    # 基本信息
    log_id: UUID
    timestamp: datetime
    tenant_id: UUID
    agent_id: UUID
    agent_role: str
    
    # 代码信息
    code_hash: str  # SHA-256
    code_size_bytes: int
    language: str  # "python", "sql"
    
    # 执行信息
    sandbox_id: str
    execution_duration_ms: int
    exit_code: int
    status: Literal["success", "failed", "timeout", "killed"]
    
    # 资源使用
    cpu_time_ms: int
    memory_peak_bytes: int
    disk_io_bytes: int
    network_io_bytes: int
    
    # 安全信息
    syscalls_executed: List[str]
    files_accessed: List[str]
    network_connections: List[NetworkConnection]
    policy_violations: List[PolicyViolation]
    
    # 输出信息
    stdout_hash: str
    stderr_hash: str
    output_size_bytes: int
    
    # 审计追踪
    worm_storage_ref: str  # WORM 存储引用（7 年归档）
```

---

## 4. 沙箱逃逸检测与防护

### 4.1 逃逸攻击向量分析

#### 常见逃逸技术

| 攻击向量 | 技术描述 | 检测难度 | 防护措施 |
|---------|---------|---------|---------|
| **容器逃逸** | 利用内核漏洞突破容器隔离 | 🟠 中 | gVisor 用户空间内核 |
| **挂载攻击** | 通过挂载宿主机目录逃逸 | 🟢 低 | 严格挂载策略 + 只读挂载 |
| **特权提升** | 利用 capabilities 提升权限 | 🟢 低 | Capability Drop |
| **命名空间突破** | 利用 setns 加入宿主机命名空间 | 🟢 低 | Seccomp 过滤 setns |
| **设备访问** | 通过/dev 设备访问宿主机 | 🟢 低 | 限制设备访问 |
| **内核模块** | 加载恶意内核模块 | 🟢 低 | 禁止 init_module |
| **ptrace 调试** | 调试其他进程获取信息 | 🟢 低 | Seccomp 过滤 ptrace |
| **procfs 泄露** | 通过/proc 获取宿主机信息 | 🟢 低 | 禁止访问/proc |

#### 攻击路径图

```
┌─────────────────────────────────────────────────────────────┐
│                    沙箱逃逸攻击路径                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  攻击入口                                                    │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────┐                                           │
│  │ 恶意代码注入 │                                           │
│  └──────┬──────┘                                           │
│         │                                                   │
│    ┌────┴────┐                                             │
│    ▼         ▼                                             │
│  ┌─────────┐ ┌─────────┐                                   │
│  │容器逃逸 │ │文件逃逸 │                                   │
│  └────┬────┘ └────┬────┘                                   │
│       │           │                                        │
│       ▼           ▼                                        │
│  ┌─────────┐ ┌─────────┐                                   │
│  │内核漏洞 │ │挂载利用 │                                   │
│  │利用     │ │         │                                   │
│  └────┬────┘ └────┬────┘                                   │
│       │           │                                        │
│       └─────┬─────┘                                        │
│             ▼                                              │
│  ┌─────────────────────┐                                   │
│  │   宿主机权限获取    │                                   │
│  └─────────────────────┘                                   │
│                                                             │
│  防护层：                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ gVisor │ Seccomp │ Capability Drop │ 挂载限制 │      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 检测机制

#### 异常行为检测

```python
class EscapeDetectionEngine:
    """沙箱逃逸检测引擎"""
    
    # 逃逸行为特征
    ESCAPE_INDICATORS = {
        "kernel_exploit": {
            "patterns": [
                "dirty_pipe", "dirty_cow", "overlayfs",  # 已知漏洞
                "ptrace.*attach", "process_vm_readv",  # 进程注入
            ],
            "severity": "CRITICAL"
        },
        "mount_abuse": {
            "patterns": [
                "mount.*--bind", "mount.*-o bind",  # 绑定挂载
                "/proc.*root", "/sys.*root",  # 访问宿主机根目录
            ],
            "severity": "CRITICAL"
        },
        "namespace_escape": {
            "patterns": [
                "setns.*pid", "setns.*net", "setns.*mnt",  # 命名空间切换
                "unshare.*CLONE_NEW",  # 创建新命名空间
            ],
            "severity": "HIGH"
        },
        "device_access": {
            "patterns": [
                "/dev/sda", "/dev/mem", "/dev/kmem",  # 敏感设备
                "/dev/fuse", "/dev/kvm",  # 虚拟化设备
            ],
            "severity": "HIGH"
        }
    }
    
    async def detect(self, execution_context: ExecutionContext) -> DetectionResult:
        # 实时监控系统调用
        syscalls = await self.monitor_syscalls(execution_context.sandbox_id)
        
        # 检测异常模式
        for indicator_type, config in self.ESCAPE_INDICATORS.items():
            for pattern in config["patterns"]:
                if self._match_pattern(syscalls, pattern):
                    return DetectionResult(
                        detected=True,
                        indicator_type=indicator_type,
                        severity=config["severity"],
                        evidence=syscalls
                    )
        
        return DetectionResult(detected=False)
```

#### 检测规则示例

```yaml
# 逃逸检测规则配置
detection_rules:
  - name: "ptrace_injection"
    description: "检测 ptrace 进程注入"
    condition: "syscall.ptrace AND process.parent != init"
    severity: CRITICAL
    action: "KILL_AND_ALERT"
    
  - name: "sensitive_mount"
    description: "检测敏感目录挂载"
    condition: "syscall.mount AND (target == '/' OR target == '/etc' OR target == '/proc')"
    severity: CRITICAL
    action: "KILL_AND_ALERT"
    
  - name: "network_scan"
    description: "检测网络扫描行为"
    condition: "network.connections > 100 AND network.time_window < 60s"
    severity: HIGH
    action: "BLOCK_AND_ALERT"
    
  - name: "crypto_miner"
    description: "检测加密货币挖矿"
    condition: "cpu.usage > 90% AND duration > 300s AND network.pool_detected"
    severity: HIGH
    action: "KILL_AND_ALERT"
```

### 4.3 防护策略

#### 纵深防御架构

```
┌─────────────────────────────────────────────────────────────┐
│                    纵深防御架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第 1 层：代码验证                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 静态分析 + 签名验证 + 风险评估                        │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  第 2 层：容器隔离                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ gVisor 用户空间内核 + Seccomp 过滤 + Capability Drop  │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  第 3 层：运行时监控                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ eBPF 系统调用监控 + 资源限制 + 异常检测               │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  第 4 层：响应与恢复                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 自动终止 + 告警通知 + 取证保存 + 策略更新             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 响应策略

| 检测事件 | 响应动作 | 通知对象 | 后续处理 |
|---------|---------|---------|---------|
| **严重逃逸尝试** | 立即终止容器 | 安全团队 + SOC | 取证分析 + 策略更新 |
| **高风险行为** | 终止执行 + 保存现场 | 安全团队 | 人工审查 |
| **中风险行为** | 记录告警 + 继续监控 | 运维团队 | 趋势分析 |
| **低风险行为** | 记录日志 | - | 定期审计 |

---

## 5. 恶意代码防护

### 5.1 静态分析规则

#### 危险函数检测

```python
DANGEROUS_FUNCTION_PATTERNS = {
    # 代码执行类
    "code_execution": {
        "functions": ["eval", "exec", "compile", "input"],
        "severity": "CRITICAL",
        "action": "BLOCK"
    },
    
    # 系统调用类
    "system_calls": {
        "functions": [
            "os.system", "os.popen", "os.spawn*", "os.exec*",
            "subprocess.call", "subprocess.run", "subprocess.Popen",
            "commands.getoutput", "commands.getstatusoutput"
        ],
        "severity": "CRITICAL",
        "action": "BLOCK"
    },
    
    # 动态导入类
    "dynamic_import": {
        "functions": ["__import__", "importlib.import_module", "importlib.__import__"],
        "severity": "HIGH",
        "action": "REVIEW"
    },
    
    # C 扩展类
    "c_extensions": {
        "functions": [
            "ctypes.CDLL", "ctypes.cdll", "ctypes.windll",
            "ctypes.pythonapi", "cffi.FFI"
        ],
        "severity": "CRITICAL",
        "action": "BLOCK"
    },
    
    # 网络访问类
    "network_access": {
        "functions": [
            "socket.socket", "socket.create_connection",
            "requests.get", "requests.post", "requests.request",
            "urllib.request.urlopen", "urllib.request.Request",
            "http.client.HTTPConnection", "aiohttp.ClientSession",
            "httpx.Client", "httpx.AsyncClient"
        ],
        "severity": "HIGH",
        "action": "REVIEW"
    },
    
    # 文件操作类
    "file_operations": {
        "functions": [
            "open", "io.open", "codecs.open",
            "os.remove", "os.unlink", "os.rmdir", "os.removedirs",
            "shutil.rmtree", "shutil.remove",
            "os.rename", "shutil.move"
        ],
        "severity": "MEDIUM",
        "action": "MONITOR"
    }
}
```

#### AST 分析器实现

```python
import ast

class MaliciousCodeDetector(ast.NodeVisitor):
    """恶意代码 AST 检测器"""
    
    def __init__(self):
        self.issues = []
        self.dangerous_calls = []
    
    def visit_Call(self, node):
        # 检测危险函数调用
        func_name = self._get_full_name(node.func)
        
        for category, config in DANGEROUS_FUNCTION_PATTERNS.items():
            if any(pattern in func_name for pattern in config["functions"]):
                self.issues.append({
                    "type": "dangerous_function",
                    "category": category,
                    "function": func_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "severity": config["severity"],
                    "action": config["action"]
                })
                self.dangerous_calls.append(func_name)
        
        self.generic_visit(node)
    
    def visit_Import(self, node):
        # 检测危险导入
        for alias in node.names:
            if alias.name in ["ctypes", "cffi", "socket", "subprocess"]:
                self.issues.append({
                    "type": "dangerous_import",
                    "module": alias.name,
                    "line": node.lineno,
                    "severity": "HIGH"
                })
        self.generic_visit(node)
    
    def _get_full_name(self, node):
        """获取完整函数名（处理属性访问）"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_full_name(node.value)
            return f"{value}.{node.attr}"
        return ""
    
    def analyze(self, code: str) -> AnalysisResult:
        try:
            tree = ast.parse(code)
            self.visit(tree)
            
            risk_score = self._calculate_risk_score()
            return AnalysisResult(
                passed=risk_score < 50,
                risk_score=risk_score,
                issues=self.issues,
                dangerous_calls=self.dangerous_calls
            )
        except SyntaxError as e:
            return AnalysisResult(
                passed=False,
                error=f"Syntax error: {e}"
            )
    
    def _calculate_risk_score(self) -> int:
        """计算风险评分（0-100）"""
        score = 0
        severity_weights = {
            "CRITICAL": 30,
            "HIGH": 20,
            "MEDIUM": 10,
            "LOW": 5
        }
        
        for issue in self.issues:
            score += severity_weights.get(issue.get("severity", "LOW"), 5)
        
        return min(score, 100)
```

### 5.2 动态行为检测

#### 运行时行为分析

```python
class RuntimeBehaviorAnalyzer:
    """运行时行为分析器"""
    
    def __init__(self):
        self.syscall_trace = []
        self.file_access_log = []
        self.network_connections = []
    
    async def analyze(self, sandbox_id: str) -> BehaviorReport:
        # 收集系统调用轨迹
        self.syscall_trace = await self.collect_syscalls(sandbox_id)
        
        # 分析异常行为
        anomalies = []
        
        # 检测 fork bomb
        if self._detect_fork_bomb():
            anomalies.append({
                "type": "fork_bomb",
                "severity": "CRITICAL",
                "evidence": "Excessive process creation detected"
            })
        
        # 检测网络扫描
        if self._detect_network_scan():
            anomalies.append({
                "type": "network_scan",
                "severity": "HIGH",
                "evidence": "Rapid connection attempts to multiple hosts"
            })
        
        # 检测加密挖矿
        if self._detect_crypto_mining():
            anomalies.append({
                "type": "crypto_mining",
                "severity": "HIGH",
                "evidence": "High CPU usage with mining pool connection"
            })
        
        return BehaviorReport(
            anomalies=anomalies,
            risk_level=self._calculate_risk_level(anomalies)
        )
```

### 5.3 黑名单/白名单机制

#### 模块白名单

```python
# 允许的 Python 标准库模块
ALLOWED_STANDARD_MODULES = {
    # 基础模块
    "builtins", "sys", "os.path", "pathlib",
    
    # 数学计算
    "math", "cmath", "decimal", "fractions",
    "statistics", "random", "numpy", "scipy",
    
    # 数据处理
    "json", "csv", "xml", "html",
    "collections", "itertools", "functools",
    "operator", "re", "string",
    
    # 日期时间
    "datetime", "time", "calendar",
    
    # 类型提示
    "typing", "dataclasses",
    
    # 日志
    "logging",
    
    # 数据科学
    "pandas", "matplotlib", "seaborn", "plotly"
}

# 明确禁止的模块
DENIED_MODULES = {
    "ctypes", "cffi", "socket", "subprocess",
    "multiprocessing", "threading",  # 限制并发
    "pickle", "marshal",  # 反序列化风险
    "shelve", "dbm",  # 数据库风险
}
```

#### 导入钩子实现

```python
import sys
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec

class SecureImportFinder(MetaPathFinder):
    """安全导入查找器"""
    
    def __init__(self, allowed_modules: set, denied_modules: set):
        self.allowed_modules = allowed_modules
        self.denied_modules = denied_modules
        self.original_finders = sys.meta_path.copy()
    
    def find_spec(self, fullname, path, target=None):
        # 检查是否在黑名单中
        if fullname in self.denied_modules:
            raise ImportError(f"Module '{fullname}' is not allowed")
        
        # 检查是否在白名单中（标准库）
        base_module = fullname.split('.')[0]
        if base_module in self.allowed_modules:
            for finder in self.original_finders:
                spec = finder.find_spec(fullname, path, target)
                if spec:
                    return spec
        
        # 检查是否是已安装的第三方安全模块
        if self._is_safe_third_party(fullname):
            for finder in self.original_finders:
                spec = finder.find_spec(fullname, path, target)
                if spec:
                    return spec
        
        # 默认拒绝
        raise ImportError(f"Module '{fullname}' is not in the allowed list")
    
    def _is_safe_third_party(self, module_name: str) -> bool:
        """检查是否是安全的第三方模块"""
        safe_packages = {
            "numpy", "pandas", "scipy", "matplotlib",
            "scikit-learn", "seaborn", "plotly",
            "pydantic", "requests"  # requests 需要网络白名单配合
        }
        base_module = module_name.split('.')[0]
        return base_module in safe_packages

# 安装导入钩子
def install_secure_import():
    secure_finder = SecureImportFinder(
        allowed_modules=ALLOWED_STANDARD_MODULES,
        denied_modules=DENIED_MODULES
    )
    sys.meta_path.insert(0, secure_finder)
```

---

## 6. 沙箱监控与审计

### 6.1 执行监控指标

#### Prometheus 指标定义

```yaml
# 沙箱监控指标
groups:
  - name: sandbox_metrics
    interval: 10s
    rules:
      # 资源使用指标
      - record: sandbox:cpu_usage:percent
        expr: rate(sandbox_cpu_time_seconds_total[5m]) * 100
      
      - record: sandbox:memory_usage:bytes
        expr: sandbox_memory_usage_bytes
      
      - record: sandbox:execution_duration:seconds
        expr: histogram_quantile(0.95, rate(sandbox_execution_duration_seconds_bucket[5m]))
      
      # 安全指标
      - record: sandbox:policy_violations:rate
        expr: rate(sandbox_policy_violations_total[5m])
      
      - record: sandbox:escape_attempts:rate
        expr: rate(sandbox_escape_detection_total[5m])
      
      # 业务指标
      - record: sandbox:executions:rate
        expr: rate(sandbox_executions_total[5m])
      
      - record: sandbox:success_rate:ratio
        expr: rate(sandbox_executions_success_total[5m]) / rate(sandbox_executions_total[5m])
```

#### 监控仪表板

```
┌─────────────────────────────────────────────────────────────┐
│              沙箱监控仪表板 (Grafana)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ 执行成功率      │  │ 平均执行时长    │  │ 活跃沙箱数  │ │
│  │    99.2%       │  │    2.3s        │  │    45      │ │
│  │    ▲ +0.5%     │  │    ▼ -0.2s     │  │    ▲ +12   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CPU/内存使用趋势（24 小时）               │   │
│  │  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   │
│  │  CPU ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   │
│  │  Mem ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ 策略违规统计    │  │ 逃逸尝试检测    │                  │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │                  │
│  │ │█████ 网络   │ │  │ │░░░░░░░░░░░░│ │                  │
│  │ │███ 文件    │ │  │ │  0 次/24h  │ │                  │
│  │ │█ 系统调用  │ │  │ │  ✅ 正常   │ │                  │
│  │ └─────────────┘ │  │ └─────────────┘ │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 审计日志设计

#### 审计日志 Schema

```sql
-- 沙箱执行审计日志表
CREATE TABLE sandbox_audit_logs (
    log_id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    agent_role VARCHAR(50) NOT NULL,
    
    -- 代码信息
    code_hash VARCHAR(64) NOT NULL,
    code_size_bytes INTEGER NOT NULL,
    language VARCHAR(20) NOT NULL,
    
    -- 执行信息
    sandbox_id VARCHAR(100) NOT NULL,
    execution_duration_ms INTEGER NOT NULL,
    exit_code INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    
    -- 资源使用
    cpu_time_ms INTEGER NOT NULL,
    memory_peak_bytes BIGINT NOT NULL,
    disk_io_bytes BIGINT NOT NULL,
    
    -- 安全信息
    syscalls_executed JSONB NOT NULL DEFAULT '[]',
    files_accessed JSONB NOT NULL DEFAULT '[]',
    policy_violations JSONB NOT NULL DEFAULT '[]',
    
    -- 审计追踪
    worm_storage_ref VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_sandbox_audit_tenant ON sandbox_audit_logs(tenant_id);
CREATE INDEX idx_sandbox_audit_timestamp ON sandbox_audit_logs(timestamp DESC);
CREATE INDEX idx_sandbox_audit_agent ON sandbox_audit_logs(agent_id);
CREATE INDEX idx_sandbox_audit_status ON sandbox_audit_logs(status);

-- 分区表（按月分区）
CREATE TABLE sandbox_audit_logs_2026_02 PARTITION OF sandbox_audit_logs
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

### 6.3 异常检测与告警

#### 告警规则配置

```yaml
# Prometheus AlertManager 告警规则
groups:
  - name: sandbox_alerts
    rules:
      # 严重告警
      - alert: SandboxEscapeDetected
        expr: rate(sandbox_escape_detection_total[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "沙箱逃逸尝试被检测到"
          description: "检测到 {{ $value }} 次沙箱逃逸尝试"
      
      - alert: HighPolicyViolationRate
        expr: rate(sandbox_policy_violations_total[10m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "策略违规率过高"
          description: "策略违规率：{{ $value }}/s"
      
      # 资源告警
      - alert: SandboxMemoryHigh
        expr: sandbox_memory_usage_bytes / sandbox_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "沙箱内存使用率过高"
          description: "内存使用率：{{ $value | humanizePercentage }}"
      
      - alert: SandboxExecutionTimeout
        expr: histogram_quantile(0.99, rate(sandbox_execution_duration_seconds_bucket[30m])) > 300
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "沙箱执行超时率过高"
          description: "P99 执行时长：{{ $value }}s"
      
      # 业务告警
      - alert: SandboxSuccessRateLow
        expr: rate(sandbox_executions_success_total[30m]) / rate(sandbox_executions_total[30m]) < 0.95
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "沙箱执行成功率过低"
          description: "成功率：{{ $value | humanizePercentage }}"
```

#### 告警通知流程

```
┌─────────────────────────────────────────────────────────────┐
│                    告警通知流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  告警触发                                                     │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────────┐                                       │
│  │ AlertManager    │                                       │
│  └────────┬────────┘                                       │
│           │                                                 │
│    ┌──────┴──────┐                                         │
│    ▼             ▼                                         │
│  ┌─────────┐ ┌─────────┐                                   │
│  │严重告警 │ │警告告警 │                                   │
│  └────┬────┘ └────┬────┘                                   │
│       │           │                                        │
│       ▼           ▼                                        │
│  ┌─────────┐ ┌─────────┐                                   │
│  │ PagerDuty│ │ Slack  │                                   │
│  │ 电话/SMS │ │ 频道   │                                   │
│  └─────────┘ └─────────┘                                   │
│                                                             │
│  通知内容：                                                  │
│  - 告警名称和级别                                            │
│  - 受影响沙箱 ID                                             │
│  - 租户信息                                                  │
│  - 时间戳和持续时间                                          │
│  - 建议处理动作                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 实现代码示例

### 7.1 Docker 沙箱实现

```python
"""
Docker 沙箱实现 - 适用于开发环境
"""

import docker
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
import hashlib

@dataclass
class SandboxConfig:
    """沙箱配置"""
    cpu_limit: float = 2.0
    memory_limit: str = "2g"
    network_disabled: bool = True
    read_only: bool = True
    tmpfs_size: str = "512m"
    timeout: int = 300

class DockerSandbox:
    """Docker 沙箱执行器"""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.client = docker.from_env()
        self.container: Optional[docker.models.containers.Container] = None
    
    async def create(self, image: str = "python:3.11-slim") -> str:
        """创建沙箱容器"""
        container = self.client.containers.run(
            image=image,
            detach=True,
            remove=True,
            cpu_quota=int(self.config.cpu_limit * 100000),
            cpu_period=100000,
            mem_limit=self.config.memory_limit,
            network_disabled=self.config.network_disabled,
            read_only=self.config.read_only,
            tmpfs={
                '/tmp': f'rw,nosuid,noexec,size={self.config.tmpfs_size}'
            },
            security_opt=[
                'no-new-privileges:true',
            ],
            cap_drop=['ALL'],
            cap_add=['CHOWN', 'SETUID', 'SETGID'],
            volumes={
                '/dev/null': {'bind': '/host', 'mode': 'ro'}
            },
            working_dir='/tmp/sandbox'
        )
        
        self.container = container
        return container.id
    
    async def execute(self, code: str) -> ExecutionResult:
        """执行代码"""
        if not self.container:
            raise RuntimeError("Sandbox not created")
        
        # 将代码写入容器
        code_bytes = code.encode('utf-8')
        self.container.put_archive('/tmp/sandbox', self._create_tar(code_bytes))
        
        # 执行代码
        result = self.container.exec_run(
            cmd=['python3', '/tmp/sandbox/code.py'],
            demux=True,
            timeout=self.config.timeout
        )
        
        return ExecutionResult(
            exit_code=result.exit_code,
            stdout=result.output[0].decode('utf-8') if result.output[0] else '',
            stderr=result.output[1].decode('utf-8') if result.output[1] else ''
        )
    
    async def cleanup(self):
        """清理沙箱"""
        if self.container:
            self.container.stop(timeout=5)
            self.container = None
    
    def _create_tar(self, code_bytes: bytes) -> bytes:
        """创建包含代码的 tar 包"""
        import tarfile
        import io
        
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
            code_info = tarfile.TarInfo(name='code.py')
            code_info.size = len(code_bytes)
            tar.addfile(code_info, io.BytesIO(code_bytes))
        
        return tar_buffer.getvalue()

@dataclass
class ExecutionResult:
    """执行结果"""
    exit_code: int
    stdout: str
    stderr: str
```

### 7.2 gVisor 沙箱实现

```python
"""
gVisor 沙箱实现 - 适用于生产环境
"""

import kubernetes
from kubernetes import client
from typing import Optional, Dict, Any
import uuid
import asyncio

class GVisorSandbox:
    """gVisor 沙箱执行器（Kubernetes）"""
    
    def __init__(self, namespace: str = "sandbox"):
        self.namespace = namespace
        self.v1 = client.CoreV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.pod_name: Optional[str] = None
    
    async def create_pod(self, image: str, resources: Dict[str, Any]) -> str:
        """创建 gVisor Pod"""
        self.pod_name = f"sandbox-{uuid.uuid4().hex[:8]}"
        
        pod_manifest = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': self.pod_name,
                'namespace': self.namespace,
                'labels': {'app': 'sandbox'}
            },
            'spec': {
                'runtimeClassName': 'gvisor',  # 使用 gVisor 运行时
                'restartPolicy': 'Never',
                'containers': [{
                    'name': 'executor',
                    'image': image,
                    'resources': {
                        'requests': {
                            'cpu': str(resources.get('cpu_request', 2)),
                            'memory': resources.get('memory_request', '2Gi')
                        },
                        'limits': {
                            'cpu': str(resources.get('cpu_limit', 4)),
                            'memory': resources.get('memory_limit', '4Gi'),
                            'ephemeral-storage': '1Gi'
                        }
                    },
                    'securityContext': {
                        'allowPrivilegeEscalation': False,
                        'readOnlyRootFilesystem': True,
                        'capabilities': {
                            'drop': ['ALL']
                        }
                    },
                    'volumeMounts': [{
                        'name': 'tmp-volume',
                        'mountPath': '/tmp/sandbox'
                    }],
                    'command': ['python3', '-c', 'import time; time.sleep(3600)']
                }],
                'volumes': [{
                    'name': 'tmp-volume',
                    'emptyDir': {
                        'sizeLimit': '512Mi'
                    }
                }],
                'affinity': {
                    'nodeAffinity': {
                        'requiredDuringSchedulingIgnoredDuringExecution': {
                            'nodeSelectorTerms': [{
                                'matchExpressions': [{
                                    'key': 'sandbox-enabled',
                                    'operator': 'In',
                                    'values': ['true']
                                }]
                            }]
                        }
                    }
                }
            }
        }
        
        # 创建 Pod
        self.v1.create_namespaced_pod(
            namespace=self.namespace,
            body=pod_manifest
        )
        
        # 等待 Pod 就绪
        await self._wait_for_pod_ready()
        
        return self.pod_name
    
    async def execute(self, code: str) -> ExecutionResult:
        """在 gVisor 沙箱中执行代码"""
        if not self.pod_name:
            raise RuntimeError("Sandbox pod not created")
        
        # 创建 ConfigMap 存储代码
        config_map_name = f"code-{uuid.uuid4().hex[:8]}"
        config_map = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(name=config_map_name, namespace=self.namespace),
            data={'code.py': code}
        )
        self.v1.create_namespaced_config_map(namespace=self.namespace, body=config_map)
        
        # 创建 Job 执行代码
        job_name = f"exec-{uuid.uuid4().hex[:8]}"
        job_manifest = {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {'name': job_name, 'namespace': self.namespace},
            'spec': {
                'ttlSecondsAfterFinished': 60,
                'template': {
                    'spec': {
                        'runtimeClassName': 'gvisor',
                        'restartPolicy': 'Never',
                        'containers': [{
                            'name': 'executor',
                            'image': 'python:3.11-slim',
                            'command': ['python3', '/code/code.py'],
                            'volumeMounts': [{
                                'name': 'code-volume',
                                'mountPath': '/code',
                                'readOnly': True
                            }],
                            'resources': {
                                'limits': {'cpu': '4', 'memory': '4Gi'}
                            },
                            'securityContext': {
                                'allowPrivilegeEscalation': False,
                                'capabilities': {'drop': ['ALL']}
                            }
                        }],
                        'volumes': [{
                            'name': 'code-volume',
                            'configMap': {'name': config_map_name}
                        }]
                    }
                }
            }
        }
        
        # 创建 Job
        self.batch_v1.create_namespaced_job(namespace=self.namespace, body=job_manifest)
        
        # 等待 Job 完成并获取结果
        return await self._wait_for_job_completion(job_name)
    
    async def _wait_for_pod_ready(self, timeout: int = 60):
        """等待 Pod 就绪"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            pod = self.v1.read_namespaced_pod(name=self.pod_name, namespace=self.namespace)
            if pod.status.phase == 'Running':
                return
            await asyncio.sleep(1)
        raise TimeoutError("Pod not ready within timeout")
    
    async def _wait_for_job_completion(self, job_name: str, timeout: int = 300) -> ExecutionResult:
        """等待 Job 完成"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            job = self.batch_v1.read_namespaced_job(name=job_name, namespace=self.namespace)
            if job.status.succeeded:
                # 获取 Pod 日志
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=f"job-name={job_name}"
                )
                if pods.items:
                    logs = self.v1.read_namespaced_pod_log(
                        name=pods.items[0].metadata.name,
                        namespace=self.namespace
                    )
                    return ExecutionResult(exit_code=0, stdout=logs, stderr='')
            elif job.status.failed:
                return ExecutionResult(exit_code=1, stdout='', stderr='Job failed')
            await asyncio.sleep(2)
        
        raise TimeoutError("Job not completed within timeout")
    
    async def cleanup(self):
        """清理资源"""
        if self.pod_name:
            try:
                self.v1.delete_namespaced_pod(
                    name=self.pod_name,
                    namespace=self.namespace,
                    grace_period_seconds=5
                )
            except Exception:
                pass
```

### 7.3 代码验证器

```python
"""
代码验证器 - 静态分析 + 动态验证
"""

import ast
import hashlib
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Issue:
    """分析发现的问题"""
    type: str
    severity: Severity
    message: str
    line: int
    column: int

@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    risk_score: int  # 0-100
    issues: List[Issue]
    code_hash: str

class CodeValidator:
    """代码验证器"""
    
    DANGEROUS_FUNCTIONS = {
        'eval': Severity.CRITICAL,
        'exec': Severity.CRITICAL,
        'compile': Severity.CRITICAL,
        'os.system': Severity.CRITICAL,
        'os.popen': Severity.CRITICAL,
        'subprocess.Popen': Severity.CRITICAL,
        'subprocess.call': Severity.CRITICAL,
        'ctypes.CDLL': Severity.CRITICAL,
        '__import__': Severity.HIGH,
        'importlib.import_module': Severity.HIGH,
    }
    
    DANGEROUS_MODULES = {
        'ctypes': Severity.CRITICAL,
        'cffi': Severity.CRITICAL,
        'socket': Severity.HIGH,
        'subprocess': Severity.CRITICAL,
        'multiprocessing': Severity.MEDIUM,
    }
    
    def __init__(self):
        self.issues: List[Issue] = []
    
    def validate(self, code: str) -> ValidationResult:
        """验证代码"""
        self.issues = []
        
        # 计算代码哈希
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # AST 分析
        try:
            tree = ast.parse(code)
            self._analyze_ast(tree)
        except SyntaxError as e:
            self.issues.append(Issue(
                type="syntax_error",
                severity=Severity.CRITICAL,
                message=f"Syntax error: {e}",
                line=e.lineno or 0,
                column=e.offset or 0
            ))
            return ValidationResult(
                passed=False,
                risk_score=100,
                issues=self.issues,
                code_hash=code_hash
            )
        
        # 计算风险评分
        risk_score = self._calculate_risk_score()
        
        return ValidationResult(
            passed=risk_score < 50,
            risk_score=risk_score,
            issues=self.issues,
            code_hash=code_hash
        )
    
    def _analyze_ast(self, tree: ast.AST):
        """AST 分析"""
        for node in ast.walk(tree):
            # 检测危险函数调用
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node)
                if func_name in self.DANGEROUS_FUNCTIONS:
                    self.issues.append(Issue(
                        type="dangerous_function",
                        severity=self.DANGEROUS_FUNCTIONS[func_name],
                        message=f"Dangerous function call: {func_name}",
                        line=node.lineno,
                        column=node.col_offset
                    ))
            
            # 检测危险导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.DANGEROUS_MODULES:
                        self.issues.append(Issue(
                            type="dangerous_import",
                            severity=self.DANGEROUS_MODULES[alias.name],
                            message=f"Dangerous module import: {alias.name}",
                            line=node.lineno,
                            column=node.col_offset
                        ))
            
            if isinstance(node, ast.ImportFrom):
                if node.module in self.DANGEROUS_MODULES:
                    self.issues.append(Issue(
                        type="dangerous_import",
                        severity=self.DANGEROUS_MODULES[node.module],
                        message=f"Dangerous module import: {node.module}",
                        line=node.lineno,
                        column=node.col_offset
                    ))
    
    def _get_func_name(self, node: ast.Call) -> str:
        """获取函数完整名称"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            value = self._get_func_name_base(node.func.value)
            return f"{value}.{node.func.attr}"
        return ""
    
    def _get_func_name_base(self, node: ast.AST) -> str:
        """获取函数名称基础部分"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_func_name_base(node.value)}.{node.attr}"
        return ""
    
    def _calculate_risk_score(self) -> int:
        """计算风险评分"""
        severity_scores = {
            Severity.CRITICAL: 30,
            Severity.HIGH: 20,
            Severity.MEDIUM: 10,
            Severity.LOW: 5
        }
        
        score = sum(severity_scores.get(issue.severity, 5) for issue in self.issues)
        return min(score, 100)
```

### 7.4 监控集成

```python
"""
监控集成 - OpenTelemetry + Prometheus
"""

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
import time
from typing import Optional

class SandboxMonitor:
    """沙箱监控器"""
    
    def __init__(self, tenant_id: str, sandbox_id: str):
        self.tenant_id = tenant_id
        self.sandbox_id = sandbox_id
        self.start_time: Optional[float] = None
        
        # 初始化 OpenTelemetry
        resource = Resource.create({
            "service.name": "sandbox-executor",
            "tenant.id": tenant_id,
            "sandbox.id": sandbox_id
        })
        
        reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        
        self.meter = metrics.get_meter("sandbox")
        
        # 创建指标
        self._create_metrics()
    
    def _create_metrics(self):
        """创建监控指标"""
        # CPU 使用率
        self.cpu_usage = self.meter.create_gauge(
            name="sandbox_cpu_usage",
            description="CPU usage percentage",
            unit="%"
        )
        
        # 内存使用
        self.memory_usage = self.meter.create_gauge(
            name="sandbox_memory_usage",
            description="Memory usage in bytes",
            unit="By"
        )
        
        # 执行时长
        self.execution_duration = self.meter.create_histogram(
            name="sandbox_execution_duration",
            description="Execution duration in seconds",
            unit="s"
        )
        
        # 系统调用计数
        self.syscall_count = self.meter.create_counter(
            name="sandbox_syscalls",
            description="Number of system calls",
            unit="1"
        )
        
        # 策略违规
        self.policy_violations = self.meter.create_counter(
            name="sandbox_policy_violations",
            description="Number of policy violations",
            unit="1"
        )
    
    def start_execution(self):
        """开始执行"""
        self.start_time = time.time()
    
    def end_execution(self, exit_code: int):
        """结束执行"""
        if self.start_time:
            duration = time.time() - self.start_time
            self.execution_duration.record(duration)
    
    def record_cpu_usage(self, percentage: float):
        """记录 CPU 使用率"""
        self.cpu_usage.set(percentage)
    
    def record_memory_usage(self, bytes: int):
        """记录内存使用"""
        self.memory_usage.set(bytes)
    
    def record_syscall(self, syscall_name: str):
        """记录系统调用"""
        self.syscall_count.add(1, {"syscall": syscall_name})
    
    def record_policy_violation(self, violation_type: str):
        """记录策略违规"""
        self.policy_violations.add(1, {"type": violation_type})
```

---

## 8. 验收标准

### 8.1 沙箱隔离测试

#### 隔离测试用例

| 测试 ID | 测试名称 | 测试步骤 | 预期结果 | 优先级 |
|--------|---------|---------|---------|-------|
| **ISO-001** | 文件系统隔离 | 尝试访问 `/host`、`/proc`、`/sys` | 访问被拒绝 | P0 |
| **ISO-002** | 网络隔离 | 尝试连接外部网络（非白名单） | 连接被阻止 | P0 |
| **ISO-003** | 进程隔离 | 尝试查看/杀死其他进程 | 操作被拒绝 | P0 |
| **ISO-004** | 资源限制 | 执行超出 CPU/内存限制的代码 | 被 cgroups 限制 | P0 |
| **ISO-005** | 只读文件系统 | 尝试修改 `/etc`、`/usr` 等目录 | 写入失败 | P0 |
| **ISO-006** | 临时目录隔离 | 验证 `/tmp/sandbox_{uuid}` 隔离 | 各沙箱独立 | P1 |
| **ISO-007** | 设备访问限制 | 尝试访问 `/dev/sda` 等设备 | 访问被拒绝 | P0 |

#### 隔离测试脚本

```python
"""
沙箱隔离测试脚本
"""

import pytest
import docker
import time

class TestSandboxIsolation:
    """沙箱隔离测试"""
    
    @pytest.fixture
    def sandbox_container(self):
        """创建测试沙箱容器"""
        client = docker.from_env()
        container = client.containers.run(
            image="python:3.11-slim",
            command="sleep 300",
            detach=True,
            remove=True,
            network_disabled=True,
            read_only=True,
            tmpfs={'/tmp': 'rw,nosuid,noexec,size=512m'},
            cap_drop=['ALL'],
            security_opt=['no-new-privileges:true']
        )
        yield container
        container.stop(timeout=5)
    
    def test_filesystem_isolation(self, sandbox_container):
        """测试文件系统隔离"""
        # 尝试访问禁止的目录
        exit_code, output = sandbox_container.exec_run("ls /host")
        assert exit_code != 0, "Should not access /host"
        
        exit_code, output = sandbox_container.exec_run("ls /proc")
        assert exit_code != 0, "Should not access /proc"
    
    def test_network_isolation(self, sandbox_container):
        """测试网络隔离"""
        # 尝试网络连接
        exit_code, output = sandbox_container.exec_run(
            "python3 -c 'import socket; s=socket.socket(); s.connect((\"8.8.8.8\", 53))'"
        )
        assert exit_code != 0, "Should not connect to external network"
    
    def test_readonly_filesystem(self, sandbox_container):
        """测试只读文件系统"""
        # 尝试写入只读目录
        exit_code, output = sandbox_container.exec_run("touch /etc/test")
        assert exit_code != 0, "Should not write to /etc"
    
    def test_resource_limits(self, sandbox_container):
        """测试资源限制"""
        # 尝试消耗大量内存
        exit_code, output = sandbox_container.exec_run(
            "python3 -c 'x = \"a\" * (10 * 1024 * 1024 * 1024)'"
        )
        # 应该被 OOM killer 杀死或失败
        assert exit_code != 0, "Should be limited by memory"
```

### 8.2 逃逸测试

#### 逃逸测试用例

| 测试 ID | 测试名称 | 攻击向量 | 预期结果 | 优先级 |
|--------|---------|---------|---------|-------|
| **ESC-001** | ptrace 注入 | 尝试 ptrace 附加到其他进程 | 被 Seccomp 阻止 | P0 |
| **ESC-002** | 挂载逃逸 | 尝试挂载宿主机目录 | 被 Capability 阻止 | P0 |
| **ESC-003** | 命名空间逃逸 | 尝试 setns 加入宿主机命名空间 | 被 Seccomp 阻止 | P0 |
| **ESC-004** | 内核模块加载 | 尝试 init_module | 被 Seccomp 阻止 | P0 |
| **ESC-005** | 设备访问 | 尝试访问 /dev/mem | 被设备限制阻止 | P0 |
| **ESC-006** | procfs 信息泄露 | 尝试读取 /proc/1/root | 被挂载限制阻止 | P0 |
| **ESC-007** | 容器逃逸漏洞 | 模拟 Dirty Pipe 攻击 | gVisor 阻止 | P0 |

#### 逃逸测试脚本

```python
"""
沙箱逃逸测试脚本
"""

import pytest
import subprocess

class TestSandboxEscape:
    """沙箱逃逸测试"""
    
    @pytest.fixture
    def gvisor_sandbox(self):
        """创建 gVisor 测试沙箱"""
        # 启动 gVisor 容器
        cmd = [
            "docker", "run", "-d", "--rm",
            "--runtime=runsc",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--read-only",
            "--tmpfs=/tmp:rw,nosuid,noexec,size=512m",
            "python:3.11-slim",
            "sleep", "300"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        container_id = result.stdout.strip()
        yield container_id
        subprocess.run(["docker", "stop", container_id])
    
    def test_ptrace_injection(self, gvisor_sandbox):
        """测试 ptrace 注入防护"""
        exit_code = subprocess.run([
            "docker", "exec", gvisor_sandbox,
            "python3", "-c",
            "import ctypes; ctypes.CDLL('libc.so.6').ptrace(0, 1, 0, 0)"
        ]).returncode
        assert exit_code != 0, "ptrace should be blocked"
    
    def test_mount_escape(self, gvisor_sandbox):
        """测试挂载逃逸防护"""
        exit_code = subprocess.run([
            "docker", "exec", gvisor_sandbox,
            "mount", "--bind", "/", "/tmp/host"
        ]).returncode
        assert exit_code != 0, "mount should be blocked"
    
    def test_setns_escape(self, gvisor_sandbox):
        """测试 setns 逃逸防护"""
        exit_code = subprocess.run([
            "docker", "exec", gvisor_sandbox,
            "python3", "-c",
            "import os; os.setns(0, 0)"
        ]).returncode
        assert exit_code != 0, "setns should be blocked"
```

### 8.3 性能指标

#### 性能验收标准

| 指标 | MVP 目标 | V1 目标 | V2 目标 | 测量方式 |
|------|---------|--------|--------|---------|
| **沙箱启动时间 (P95)** | <2s | <1s | <500ms | Prometheus |
| **代码执行延迟 (P95)** | <5s | <3s | <2s | 链路追踪 |
| **静态分析延迟 (P95)** | <500ms | <300ms | <100ms | 应用指标 |
| **资源开销 (内存)** | <300MB/沙箱 | <250MB/沙箱 | <200MB/沙箱 | Node Exporter |
| **并发沙箱数** | ≥50 | ≥100 | ≥200 | 负载测试 |
| **逃逸检测率** | ≥99% | ≥99.5% | ≥99.9% | 红队测试 |
| **误报率** | <5% | <3% | <1% | 回归测试 |

#### 性能基准测试

```python
"""
沙箱性能基准测试
"""

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor

class TestSandboxPerformance:
    """沙箱性能测试"""
    
    def test_startup_latency(self, sandbox_factory):
        """测试启动延迟"""
        latencies = []
        for _ in range(20):
            start = time.time()
            sandbox = sandbox_factory.create()
            latencies.append(time.time() - start)
            sandbox.cleanup()
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 2.0, f"P95 startup latency {p95}s exceeds 2s"
    
    def test_execution_latency(self, sandbox_factory):
        """测试执行延迟"""
        sandbox = sandbox_factory.create()
        code = "print(sum(range(1000000)))"
        
        latencies = []
        for _ in range(50):
            start = time.time()
            sandbox.execute(code)
            latencies.append(time.time() - start)
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 5.0, f"P95 execution latency {p95}s exceeds 5s"
        
        sandbox.cleanup()
    
    def test_concurrent_executions(self, sandbox_factory):
        """测试并发执行"""
        def execute_task():
            sandbox = sandbox_factory.create()
            sandbox.execute("print('hello')")
            sandbox.cleanup()
        
        start = time.time()
        with ThreadPoolExecutor(max_workers=50) as executor:
            list(executor.map(lambda _: execute_task(), range(50)))
        duration = time.time() - start
        
        assert duration < 30.0, f"50 concurrent executions took {duration}s"
    
    def test_memory_overhead(self, sandbox_factory):
        """测试内存开销"""
        import psutil
        
        before = psutil.virtual_memory().used
        sandboxes = [sandbox_factory.create() for _ in range(10)]
        after = psutil.virtual_memory().used
        
        overhead_per_sandbox = (after - before) / 10
        assert overhead_per_sandbox < 300 * 1024 * 1024, \
            f"Memory overhead {overhead_per_sandbox/1024/1024}MB exceeds 300MB"
        
        for s in sandboxes:
            s.cleanup()
```

---

## 附录 A：安全配置清单

### A.1 gVisor 生产配置

```yaml
# gVisor 生产环境配置清单
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor
handler: runsc
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: gvisor-config
  namespace: kube-system
data:
  config.toml: |
    [runsc_config]
      # 启用网络命名空间隔离
      network = "sandbox"
      # 启用文件系统隔离
      filesystem = "gofer"
      # 限制可访问的文件
      ro-mounts = ["/usr", "/etc", "/bin"]
      # 启用 Seccomp
      seccomp = "always"
```

### A.2 Seccomp 配置文件

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": ["accept", "bind", "close", "connect", "execve", "exit", "read", "write"],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

---

## 附录 B：参考文档

- [gVisor 官方文档](https://gvisor.dev/docs/)
- [Docker 安全最佳实践](https://docs.docker.com/engine/security/)
- [Kubernetes 安全上下文](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Seccomp 配置指南](https://docs.docker.com/engine/security/seccomp/)
- [OpenClaw 安全事件分析](https://github.com/OpenClaw/security-advisory)
- [OWASP 容器安全指南](https://owasp.org/www-project-container-security/)

---

**文档状态：** 完整
**下次评审日期：** 2026-05-25
**负责人：** 安全架构团队
