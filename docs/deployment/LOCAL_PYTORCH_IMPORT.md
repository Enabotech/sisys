# 本地 PyTorch 镜像导入指南

**版本:** 1.0.0
**日期:** 2026-03-23
**关联 Story:** 0.9 (CI/CD Pipeline 模板)

---

## 📦 镜像信息

**源文件路径:** `/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar`

**镜像规格:**
| 属性 | 值 |
|------|-----|
| **框架** | PyTorch |
| **版本** | 2.7.1 |
| **CUDA** | 12.8 |
| **cuDNN** | 9 |
| **类型** | devel (开发镜像) |
| **大小** | ~8GB |
| **基础系统** | Ubuntu 22.04 |

**包含组件:**
- ✅ PyTorch 2.7.1 (完整深度学习框架)
- ✅ CUDA 12.8 Toolkit (GPU 计算平台)
- ✅ cuDNN 9 (深度学习加速库)
- ✅ Python 3.11+
- ✅ 编译工具链 (gcc, g++, make)
- ✅ Git, Curl, Wget 等常用工具

---

## 🚀 导入步骤

### 步骤 1: 验证镜像文件完整性

```bash
# 检查文件是否存在
ls -lh /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar

# 检查文件大小 (应约为 8GB)
du -h /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar

# 验证文件完整性 (如果有 checksum 文件)
sha256sum /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

**预期输出:**
```
-rw-r--r-- 1 agimtech agimtech 8.2G Mar 20 10:00 pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
8.2G  /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

---

### 步骤 2: 导入到 Docker

```bash
# 导入镜像
docker load -i /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

**预期输出:**
```
Loaded image: pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

**验证导入:**
```bash
# 查看导入的镜像
docker images | grep pytorch
```

**预期输出:**
```
pytorch/pytorch   2.7.1-cuda12.8-cudnn9-devel   abc12345678   2 weeks ago   8.2GB
```

---

### 步骤 3: 本地 GPU 兼容性测试

```bash
# 测试 GPU 支持
docker run --rm --gpus all \
  pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "
import torch
print(f'PyTorch 版本：{torch.__version__}')
print(f'CUDA 版本：{torch.version.cuda}')
print(f'cuDNN 版本：{torch.backends.cudnn.version()}')
print(f'CUDA 可用：{torch.cuda.is_available()}')
print(f'CUDA 设备数：{torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'当前设备：{torch.cuda.get_device_name(0)}')
"
```

**预期输出:**
```
PyTorch 版本：2.7.1
CUDA 版本：12.8
cuDNN 版本：9
CUDA 可用：True
CUDA 设备数：1
当前设备：NVIDIA GeForce RTX 3090
```

---

### 步骤 4: 推送到 Harbor

```bash
# 1. 登录 Harbor (使用环境变量或 Secret)
# 推荐：使用环境变量
export HARBOR_REGISTRY="harbor.sisys.local"
export HARBOR_USERNAME="admin"  # 或使用 Robot Account
export HARBOR_PASSWORD="your_password"  # 或使用 Secret

# 2. Docker 登录
docker login -u "${HARBOR_USERNAME}" -p "${HARBOR_PASSWORD}" "${HARBOR_REGISTRY}"

# 3. 打标签
docker tag pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  ${HARBOR_REGISTRY}/sisys/pytorch-base:2.7.1-cuda12.8

# 4. 推送到 Harbor
docker push ${HARBOR_REGISTRY}/sisys/pytorch-base:2.7.1-cuda12.8
```

**预期输出:**
```
The push refers to repository [harbor.sisys.local/sisys/pytorch-base]
abc12345678: Pushed
def23456789: Pushed
...
2.7.1-cuda12.8: digest: sha256:abc123... size: 4567
```

---

### 步骤 5: Harbor 验证

```bash
# 1. 通过 API 验证镜像存在
curl -sf -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_REGISTRY}/api/v2.0/projects/sisys/repositories/pytorch-base/artifacts" \
  | jq '.[].tags[].name'

# 2. 拉取验证
docker pull ${HARBOR_REGISTRY}/sisys/pytorch-base:2.7.1-cuda12.8

# 3. 再次验证 GPU
docker run --rm --gpus all \
  ${HARBOR_REGISTRY}/sisys/pytorch-base:2.7.1-cuda12.8 \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

---

## 📝 自动化脚本

创建脚本 `scripts/image/import-pytorch.sh`:

```bash
#!/bin/bash
set -e

# =============================================================================
# PyTorch 镜像导入脚本
# =============================================================================
# 用途：将本地备份的 PyTorch 镜像导入 Docker 并推送到 Harbor
# 关联 Story: 0.9 (CI/CD Pipeline 模板)
# =============================================================================

# 配置变量
SOURCE_FILE="/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar"
HARBOR_REGISTRY="${HARBOR_REGISTRY:-harbor.sisys.local}"
HARBOR_PROJECT="${HARBOR_PROJECT:-sisys}"
IMAGE_NAME="pytorch-base"
IMAGE_TAG="2.7.1-cuda12.8"

echo "=========================================="
echo "PyTorch 镜像导入脚本"
echo "=========================================="
echo "源文件：${SOURCE_FILE}"
echo "目标：${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

# 步骤 1: 验证源文件
echo "📦 步骤 1: 验证源文件..."
if [ ! -f "${SOURCE_FILE}" ]; then
    echo "❌ 错误：源文件不存在 ${SOURCE_FILE}"
    exit 1
fi

FILE_SIZE=$(du -h "${SOURCE_FILE}" | cut -f1)
echo "✅ 文件大小：${FILE_SIZE}"

# 步骤 2: 导入到 Docker
echo "📥 步骤 2: 导入到 Docker..."
docker load -i "${SOURCE_FILE}"
echo "✅ 导入完成"

# 步骤 3: 本地验证
echo "🧪 步骤 3: 本地 GPU 验证..."
docker run --rm --gpus all \
  pytorch/pytorch:${IMAGE_TAG}-devel \
  python3 -c "
import torch
print(f'✅ PyTorch 版本：{torch.__version__}')
print(f'✅ CUDA 版本：{torch.version.cuda}')
print(f'✅ CUDA 可用：{torch.cuda.is_available()}')
"

# 步骤 4: 推送到 Harbor
echo "📤 步骤 4: 推送到 Harbor..."

# 检查是否已登录
if ! docker info 2>&1 | grep -q "${HARBOR_REGISTRY}"; then
    echo "⚠️  未登录 Harbor，请先执行：docker login ${HARBOR_REGISTRY}"
    echo "    或设置环境变量："
    echo "    export HARBOR_USERNAME=xxx"
    echo "    export HARBOR_PASSWORD=xxx"
    exit 1
fi

# 打标签
docker tag pytorch/pytorch:${IMAGE_TAG}-devel \
  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}

# 推送
docker push ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}

echo "✅ 推送完成"

# 步骤 5: 最终验证
echo "🔍 步骤 5: 最终验证..."
docker pull ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}
docker run --rm --gpus all \
  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} \
  python3 -c "import torch; print('✅ Harbor 镜像验证通过')"

echo ""
echo "=========================================="
echo "✅ PyTorch 镜像导入完成！"
echo "=========================================="
echo ""
echo "使用示例:"
echo "  docker run --rm --gpus all ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} python3"
echo ""
```

**使用脚本:**
```bash
# 赋予执行权限
chmod +x scripts/image/import-pytorch.sh

# 设置环境变量
export HARBOR_USERNAME="admin"
export HARBOR_PASSWORD="your_password"

# 执行脚本
./scripts/image/import-pytorch.sh
```

---

## 🔧 在 CI/CD Pipeline 中使用

### CI Pipeline 配置示例

```yaml
# .gitea/workflows/ci.yaml
env:
  DEPENDENCY_IMAGE: harbor.sisys.local/sisys/dependency:latest
  PYTORCH_BASE: harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8

jobs:
  unit-test:
    runs-on: [self-hosted, gpu]
    container:
      image: ${{ env.DEPENDENCY_IMAGE }}
      options: --gpus all
    steps:
    - name: Verify GPU Environment
      run: |
        echo "=== PyTorch Base Image ==="
        docker run --rm --gpus all ${{ env.PYTORCH_BASE }} \
          python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### Dockerfile.dependency 示例

```dockerfile
# docker/Dockerfile.dependency
# Layer 2: 基于本地 PyTorch 镜像构建项目依赖

FROM harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8 AS base

LABEL maintainer="Agimtech <agimtech@example.com>"
LABEL description="SISYS Project Dependency Image"
LABEL version="1.0.0"

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.0 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PATH="/opt/poetry/bin:$PATH"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    libz-dev \
    tesseract-ocr \
    libtesseract-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && poetry --version

# 配置国内镜像源
RUN poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple/ \
    && poetry source add --priority=primary aliyun https://mirrors.aliyun.com/pypi/simple/

# 复制依赖文件
WORKDIR /workspace
COPY pyproject.toml poetry.lock ./

# 安装项目依赖
RUN poetry install --no-root --no-interaction --no-ansi \
    && python3 -c "import torch, fastapi, sqlalchemy, langgraph, prefect; print('✅ All dependencies OK')"

# 清理缓存
RUN pip cache purge \
    && poetry cache clear pypi --all \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 验证 GPU
RUN python3 -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'"

WORKDIR /workspace
CMD ["/bin/bash"]
```

---

## 🛠️ 故障排除

### 问题 1: 导入失败

**错误信息:**
```
open /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar: no such file or directory
```

**解决方案:**
```bash
# 检查文件路径
ls -la /mnt/x/backup/images/

# 检查挂载点
mount | grep /mnt/x

# 如果是网络挂载，确保连接正常
ping -c 3 <nas-ip>
```

---

### 问题 2: GPU 不可用

**错误信息:**
```
CUDA not available
```

**解决方案:**
```bash
# 1. 验证 NVIDIA Docker 已安装
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi

# 2. 检查 GPU Operator
kubectl get pods -n gpu-operator

# 3. 验证容器运行时
kubectl describe node <node-name> | grep -A 5 "Allocated resources"
```

---

### 问题 3: Harbor 推送失败

**错误信息:**
```
unauthorized: authentication required
```

**解决方案:**
```bash
# 1. 重新登录
docker logout harbor.sisys.local
docker login -u admin -p your_password harbor.sisys.local

# 2. 检查 Robot Account 权限
# Harbor UI → 项目 → sisys → 机器人账户 → 检查权限

# 3. 使用 Secret (K8s 环境)
kubectl create secret docker-registry harbor-secret \
  --docker-server=harbor.sisys.local \
  --docker-username=admin \
  --docker-password=your_password \
  --docker-email=admin@example.com \
  -n sisys
```

---

### 问题 4: 镜像拉取超时

**错误信息:**
```
net/http: TLS handshake timeout
```

**解决方案:**
```bash
# 1. 检查网络连接
ping harbor.sisys.local

# 2. 配置 Docker 镜像加速
# /etc/docker/daemon.json
{
  "registry-mirrors": [
    "https://harbor.sisys.local"
  ]
}

# 3. 重启 Docker
sudo systemctl restart docker
```

---

## 📊 镜像版本管理

### 版本命名规范

```
harbor.sisys.local/sisys/pytorch-base:{pytorch-version}-cuda{cuda-version}

示例:
- 2.7.1-cuda12.8 (当前版本)
- 2.5.0-cuda12.4 (历史版本)
- 2.3.0-cuda12.1 (历史版本)
```

### 更新策略

| 场景 | 操作 | 频率 |
|------|------|------|
| **PyTorch 小版本更新** | 更新 tag，保留旧版本 | 每月 |
| **CUDA 大版本更新** | 创建新 tag，测试兼容性 | 每季度 |
| **安全补丁** | 立即更新，通知团队 | 按需 |

---

## 📈 性能监控

### 镜像大小趋势

```bash
# 查看 Harbor 中镜像大小
curl -sf -u "admin:password" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/pytorch-base/artifacts" \
  | jq '.[] | {tag: .tags[0].name, size: .size}'
```

### 拉取时间监控

```bash
# 测试拉取时间
time docker pull harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8

# 预期：本地网络 < 30 秒
#       远程网络 < 2 分钟
```

---

## ✅ 检查清单

| 项目 | 状态 | 验证命令 |
|------|------|---------|
| [ ] 源文件完整性 | ⬜ | `ls -lh /mnt/x/backup/images/...` |
| [ ] Docker 导入成功 | ⬜ | `docker images \| grep pytorch` |
| [ ] GPU 兼容性测试 | ⬜ | `docker run --rm --gpus all ...` |
| [ ] Harbor 登录 | ⬜ | `docker login harbor.sisys.local` |
| [ ] 镜像推送成功 | ⬜ | `docker push ...` |
| [ ] Harbor 验证 | ⬜ | `curl .../api/v2.0/...` |
| [ ] CI Pipeline 集成 | ⬜ | 触发 CI 测试 |
| [ ] 文档更新 | ⬜ | 本文档 |

---

## 🔗 相关文档

- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [预构建镜像维护指南](./PREBUILT_IMAGE_MAINTENANCE.md)
- [Gitea Runner 配置](./GITEA_RUNNER_CONFIG.md)
- [Harbor 镜像仓库使用指南](./HARBOR_USAGE.md)

---

**最后更新:** 2026-03-23
**维护者:** Agimtech DevOps Team
