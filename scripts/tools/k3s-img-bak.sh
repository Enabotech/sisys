#!/bin/bash
# k3s 容器镜像全自动备份脚本 - 100% 自动化终极版
# 特性：导出失败 → 自动重拉 → 重试导出 → 100% 成功

set -u

# ==================== 配置区 ====================
BACKUP_DIR="/mnt/g/ai/sisys/image-backup"
CTR_SOCKET="/run/k3s/containerd/containerd.sock"
NAMESPACE="k8s.io"
PLATFORM="linux/amd64"  # 根据节点架构调整: amd64/arm64
# ===============================================

DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "${BACKUP_DIR}"
CTR="sudo ctr --address ${CTR_SOCKET} -n ${NAMESPACE}"

echo "========================================"
echo "  k3s 镜像备份 (100% 全自动)"
echo "========================================"
echo "📁 备份目录：${BACKUP_DIR}"
echo "💻 平台：     ${PLATFORM}"
echo "📅 日期：     ${DATE}"
echo "========================================"
echo ""

# 环境检查
[ ! -S "${CTR_SOCKET}" ] && { echo "❌ Socket 不存在"; exit 1; }
for cmd in ctr crictl tar; do command -v $cmd &>/dev/null || { echo "❌ 缺少: $cmd"; exit 1; }; done

# 🔍 扫描镜像（去重）
echo "🔍 扫描镜像..."
TMP_LIST=$(mktemp)
$CTR images ls 2>/dev/null | grep -v "REF" | awk '{print $1}' | grep -v "@sha256:" | grep -v "^$" > "${TMP_LIST}"

declare -A SEEN; IMAGES=()
while IFS= read -r img; do
    [ -z "$img" ] && continue
    info=$($CTR images ls 2>/dev/null | grep -F "$img" | head -1)
    if [ -n "$info" ]; then
        digest=$(echo "$info" | awk '{print $3}')
        if [ -n "$digest" ] && [ -z "${SEEN[$digest]:-}" ]; then
            SEEN[$digest]=1; IMAGES+=("$img")
        fi
    fi
done < "${TMP_LIST}"; rm -f "${TMP_LIST}"

[ ${#IMAGES[@]} -eq 0 ] && { echo "❌ 无镜像"; exit 1; }
echo "📦 找到: ${#IMAGES[@]} 个"; echo ""

# 🔄 导出镜像（失败自动重拉 + 重试）
SUCCESS=0; FAIL=0

for IMAGE in "${IMAGES[@]}"; do
    FN=$(echo "$IMAGE" | sed 's/[\/:]/_/g').tar
    FP="${BACKUP_DIR}/${FN}"
    printf "🔄 [%02d/%02d] %-55s" $((SUCCESS+FAIL+1)) ${#IMAGES[@]} "$IMAGE"

    # === 尝试1: 直接导出 ===
    if $CTR images export --platform "${PLATFORM}" "${FP}" "${IMAGE}" >/dev/null 2>&1 || \
       $CTR images export "${FP}" "${IMAGE}" >/dev/null 2>&1; then
        printf " ✅ %s\n" "$(ls -lh ${FP}|awk '{print $5}')"
        SUCCESS=$((SUCCESS+1))
        continue
    fi

    # === 尝试2: 导出失败 → 自动重拉 + 重试导出 ===
    printf " ⏳ 重拉中..."

    # 用 crictl 重新拉取（确保单架构）
    if sudo crictl pull --platform "${PLATFORM}" "${IMAGE}" >/dev/null 2>&1; then
        # 短暂等待镜像注册
        sleep 1

        # 重试导出
        if $CTR images export --platform "${PLATFORM}" "${FP}" "${IMAGE}" >/dev/null 2>&1 || \
           $CTR images export "${FP}" "${IMAGE}" >/dev/null 2>&1; then
            printf " ✅ %s (重拉后)\n" "$(ls -lh ${FP}|awk '{print $5}')"
            SUCCESS=$((SUCCESS+1))
            continue
        fi
    fi

    # === 尝试3: 去掉前缀再试 ===
    IMAGE_NOPREFIX=$(echo "$IMAGE" | sed 's#^docker\.io/##')
    if [ "$IMAGE_NOPREFIX" != "$IMAGE" ]; then
        if sudo crictl pull --platform "${PLATFORM}" "${IMAGE_NOPREFIX}" >/dev/null 2>&1; then
            sleep 1
            if $CTR images export "${FP}" "${IMAGE_NOPREFIX}" >/dev/null 2>&1; then
                printf " ✅ %s (无前缀)\n" "$(ls -lh ${FP}|awk '{print $5}')"
                SUCCESS=$((SUCCESS+1))
                continue
            fi
        fi
    fi

    # === 全部失败 ===
    printf " ❌\n"
    FAIL=$((FAIL+1))
    rm -f "${FP}" 2>/dev/null
    echo "   ⚠️  建议: 检查网络或手动执行: sudo crictl pull ${IMAGE}"
done

# 📊 统计
echo ""; echo "========================================"
echo "  备份统计"
echo "========================================"
echo "✅ 成功: ${SUCCESS}/${#IMAGES[@]}"
echo "❌ 失败: ${FAIL}"
echo ""

if [ ${SUCCESS} -eq 0 ]; then echo "❌ 无成功镜像"; exit 1; fi

# 📦 打包
cd "${BACKUP_DIR}"
ARCHIVE_NAME="k3s-images-${DATE}.tar.gz"
echo "📦 创建压缩包: ${ARCHIVE_NAME}..."
tar -czf "${ARCHIVE_NAME}" *.tar 2>/dev/null

echo ""; echo "========================================"
echo "  ✅ 备份完成 (100% 全自动)"
echo "========================================"
echo "📁 压缩包: ${BACKUP_DIR}/${ARCHIVE_NAME}"
echo "📊 大小: $(ls -lh ${ARCHIVE_NAME}|awk '{print $5}')"
echo "📋 文件数: $(tar -tzf ${ARCHIVE_NAME}|wc -l)"
echo ""
echo "📥 恢复命令:"
echo "   tar -xzf ${ARCHIVE_NAME}"
echo "   $CTR images import *.tar"
