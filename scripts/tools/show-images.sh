#!/bin/bash
echo "📦 K3s 镜像使用情况"
echo "==================="

# 获取正在使用的镜像（包括 Init 容器）
USED=$(kubectl get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{range .spec.initContainers[*]}{.image}{"\n"}{end}{end}' 2>/dev/null | sort -u)

echo ""
echo "✅ 正在使用的镜像:"
echo "-------------------"
USED_COUNT=0
echo "$USED" | while read -r img; do
    [ -n "$img" ] && echo "  $img" && USED_COUNT=$((USED_COUNT + 1))
done

echo ""
echo "🗑️  可能未使用的镜像:"
echo "-------------------"

CLEANABLE_COUNT=0
TOTAL_SIZE_KB=0

# 解析 crictl images 输出 (跳过标题行)
sudo k3s crictl images 2>/dev/null | tail -n +2 | while IFS= read -r line; do
    # 提取字段: IMAGE TAG IMAGE_ID SIZE
    # 格式: harbor.sisys.local/sisys/app   v1.0.0   604ea0c2c17f9   65.4MB
    IMAGE=$(echo "$line" | awk '{print $1}')
    TAG=$(echo "$line" | awk '{print $2}')
    ID=$(echo "$line" | awk '{print $3}')
    SIZE_STR=$(echo "$line" | awk '{print $4}')

    # 组合完整镜像名
    if [ "$TAG" = "<none>" ]; then
        FULL_NAME="$IMAGE"
    else
        FULL_NAME="$IMAGE:$TAG"
    fi

    # 提取前7位 SHA256
    SHORT_ID=$(echo "$ID" | cut -c1-7)

    # 检查是否正在使用
    if echo "$USED" | grep -q "$FULL_NAME"; then
        : # 正在使用
    else
        # 提取大小数值 (MB -> KB for calculation)
        SIZE_MB=$(echo "$SIZE_STR" | grep -oP '[0-9.]+')
        if echo "$SIZE_STR" | grep -q "MB"; then
            SIZE_KB=$(echo "$SIZE_MB * 1024" | bc 2>/dev/null | cut -d. -f1)
        elif echo "$SIZE_STR" | grep -q "GB"; then
            SIZE_KB=$(echo "$SIZE_MB * 1048576" | bc 2>/dev/null | cut -d. -f1)
        else
            SIZE_KB=0
        fi

        # 显示: 镜像名 (sha256:xxx) [大小]
        printf "  🗑️  %-50s (sha256:%-7s) [%s]\n" "$FULL_NAME" "$SHORT_ID" "$SIZE_STR"
    fi
done

echo ""
echo "💡 清理命令: sudo k3s crictl rmi --prune"
