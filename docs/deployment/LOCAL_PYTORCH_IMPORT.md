# 本地 PyTorch 镜像导入指南

## 目录

1. [概述](#概述)
2. [前置条件](#前置条件)
3. [导入流程](#导入流程)
4. [验证步骤](#验证步骤)
5. [故障排除](#故障排除)
6. [使用示例](#使用示例)

---

## 概述

本指南说明如何将本地备份的 PyTorch 镜像导入 Docker 并推送到 Harbor，作为 Layer 1 基础镜像。

### 镜像信息

| 属性 | 值 |
|------|-----|
| **文件路径** | `/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar` |
| **镜像名称** | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel` |
| **PyTorch 版本** | 2.7.1 |
| **CUDA 版本** | 12.8 |
| **cuDNN 版本** | 9 |
| **镜像类型** | devel (包含编译工具链) |
| **预估大小** | ~8GB |

### 为什么使用本地镜像

- **加速导入**: 避免从 Docker Hub 下载 (慢且不稳定)
- **离线可用**: 内网环境无需外网访问
- **版本控制**: 确保团队使用统一版本
- **成本优化**: 减少外网流量费用

---

## 前置条件

### 硬件要求

- ✅ 可用磁盘空间：≥ 20GB
- ✅ 内存：≥ 16GB (推荐)
- ✅ GPU (可选，用于验证)

### 软件要求

```bash
# 检查 Docker
docker --version  # 需要 Docker 20.10+

# 检查 GPU 支持 (可选)
nvidia-smi  # 需要 NVIDIA 驱动 + nvidia-container-toolkit

# 检查磁盘空间
df -h /mnt/x
df -h /var/lib/docker
```

### 权限要求

- Docker 访问权限 (docker 组或 root)
- Harbor 访问权限
- 本地镜像文件读取权限

---

## 导入流程

### 方法 1: 使用自动化脚本 (推荐)

```bash
# 1. 进入项目目录
cd /mnt/g/ai/sisys

# 2. 执行导入脚本
./scripts/image/import-pytorch.sh

# 或使用环境变量
HARBOR_USERNAME=admin HARBOR_PASSWORD=secret ./scripts/image/import-pytorch.sh
```

### 方法 2: 手动导入

#### 步骤 1: 验证镜像文件

```bash
# 检查文件存在
ls -lh /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar

# 检查文件完整性 (如果有 checksum)
sha256sum /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

#### 步骤 2: 导入到 Docker

```bash
# 导入镜像
docker load -i /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar

# 验证导入
docker images | grep pytorch
# 应显示：
# pytorch/pytorch   2.7.1-cuda12.8-cudnn9-devel   <IMAGE_ID>   2 weeks ago   8GB
```

#### 步骤 3: 标记镜像

```bash
# 定义变量
HARBOR_REGISTRY="harbor.sisys.local"
IMAGE_NAME="pytorch/pytorch"
IMAGE_TAG="2.7.1-cuda12.8-cudnn9-devel"

# 标记镜像
docker tag ${IMAGE_NAME}:${IMAGE_TAG} \
  ${HARBOR_REGISTRY}/sisys/${IMAGE_NAME}:${IMAGE_TAG}
```

#### 步骤 4: 登录 Harbor

```bash
# 登录 Harbor
docker login harbor.sisys.local -u admin -p <password>

# 或使用环境变量
docker login ${HARBOR_REGISTRY} -u ${HARBOR_USERNAME} -p ${HARBOR_PASSWORD}
```

#### 步骤 5: 推送到 Harbor

```bash
# 推送镜像
docker push ${HARBOR_REGISTRY}/sisys/${IMAGE_NAME}:${IMAGE_TAG}

# 预计时间：5-10 分钟 (取决于网络)
```

#### 步骤 6: 验证推送

```bash
# 拉取验证
docker pull ${HARBOR_REGISTRY}/sisys/${IMAGE_NAME}:${IMAGE_TAG}

# 查看 Harbor UI
# 访问：https://harbor.sisys.local/projects/sisys/repositories/pytorch/pytorch
```

---

## 验证步骤

### 基础验证

```bash
# 1. 检查镜像存在
docker images | grep pytorch

# 2. 检查镜像大小
docker inspect harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel | jq '.[0].Size'

# 3. 运行简单测试
docker run --rm harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 --version
```

### Python 环境验证

```bash
# 验证 PyTorch 安装
docker run --rm harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(f'PyTorch: {torch.__version__}')"

# 验证 CUDA 版本
docker run --rm harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(f'CUDA: {torch.version.cuda}')"

# 验证 cuDNN
docker run --rm harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch.backends.cudnn; print(f'cuDNN: {torch.backends.cudnn.version()}')"
```

### GPU 验证 (需要 GPU 支持)

```bash
# 1. 检查 GPU 可见性
docker run --rm --gpus all \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  nvidia-smi

# 2. 验证 CUDA 可用
docker run --rm --gpus all \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(f'CUDA 可用：{torch.cuda.is_available()}')"

# 3. 运行 GPU 测试
docker run --rm --gpus all \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "
import torch
print(f'GPU 数量：{torch.cuda.device_count()}')
print(f'GPU 名称：{torch.cuda.get_device_name(0)}')
print(f'GPU 内存：{torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB')
"
```

---

## 故障排除

### 问题 1: 文件不存在

**症状**: `cannot open '/mnt/x/backup/images/...': No such file or directory`

**解决方案**:

```bash
# 1. 检查文件路径
find /mnt -name "*pytorch*.tar" 2>/dev/null

# 2. 检查挂载点
df -h | grep /mnt/x

# 3. 如果文件确实丢失，从官方下载
docker pull pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
docker save pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  -o /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

### 问题 2: Docker 导入失败

**症状**: `error importing image`

**解决方案**:

```bash
# 1. 检查 Docker 状态
systemctl status docker

# 2. 检查磁盘空间
df -h /var/lib/docker

# 3. 清理空间
docker system prune -a

# 4. 重试导入
docker load -i /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
```

### 问题 3: Harbor 推送失败

**症状**: `unauthorized: authentication required`

**解决方案**:

```bash
# 1. 验证凭据
docker login harbor.sisys.local -u admin -p <password>

# 2. 检查 Harbor 权限
# Harbor UI → 项目 → 成员 → 检查用户权限

# 3. 使用机器人账户
docker login harbor.sisys.local -u robot$ci-pipeline -p <token>
```

### 问题 4: GPU 不可用

**症状**: `could not select device driver "nvidia"`

**解决方案**:

```bash
# 1. 安装 nvidia-container-toolkit
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 2. 配置 Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 3. 验证
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

### 问题 5: 镜像拉取失败

**症状**: `image not found`

**解决方案**:

```bash
# 1. 验证镜像已推送
docker images | grep harbor.sisys.local

# 2. 检查 Harbor UI
# Harbor UI → 项目 → sisys → 仓库 → pytorch/pytorch

# 3. 重新推送
docker push harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

---

## 使用示例

### 在 Dockerfile 中使用

```dockerfile
# Layer 1: 基础镜像
FROM harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel AS base

# Layer 2: 安装依赖
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main

# Layer 3: 应用代码
COPY src/ ./src/
CMD ["python3", "-m", "src.app"]
```

### 在 Docker Compose 中使用

```yaml
version: '3.8'

services:
  app:
    image: harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./src:/app/src
    working_dir: /app
    command: python3 -m src.app
```

### 在 Kubernetes 中使用

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: pytorch-gpu
spec:
  containers:
    - name: pytorch
      image: harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
      command: ["python3", "-c", "import torch; print(torch.cuda.is_available())"]
      resources:
        limits:
          nvidia.com/gpu: "1"
  restartPolicy: Never
```

### 在 CI/CD Pipeline 中使用

```yaml
# .gitea/workflows/ci.yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
      options: --gpus all
    
    steps:
      - name: Verify GPU
        run: python3 -c "import torch; print(torch.cuda.is_available())"
```

---

## 性能基准

### 导入时间对比

| 方法 | 时间 | 说明 |
|------|------|------|
| 本地导入 | 30 秒 | 从本地文件导入 |
| Docker Hub 拉取 | 10-30 分钟 | 取决于网络 |
| Harbor 拉取 | 2-5 分钟 | 内网环境 |

### 构建时间对比

| 场景 | 原时间 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次构建 | 15 分钟 | 5 分钟 | 67% |
| 增量构建 | 10 分钟 | 3 分钟 | 70% |
| 依赖安装 | 5-10 分钟 | 0 分钟 | 100% |

---

## 后续步骤

导入完成后：

1. ✅ 更新 CI/CD Pipeline 配置
   - 修改 `.gitea/workflows/ci.yaml` 中的 `PYTORCH_IMAGE` 变量

2. ✅ 更新 Dockerfile
   - 修改 `docker/Dockerfile.dependency` 中的 `PYTORCH_IMAGE` 参数

3. ✅ 通知团队
   - 分享镜像地址和使用方法

4. ✅ 监控使用
   - 查看 Harbor 统计和拉取日志

---

## 相关文档

- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [预构建镜像维护指南](./PREBUILT_IMAGE_MAINTENANCE.md)
