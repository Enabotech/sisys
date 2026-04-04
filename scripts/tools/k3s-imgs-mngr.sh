#!/bin/bash
# 默认参数
OLD_REGISTRIES=""
NEW_REGISTRY=""
usage() {
    echo "用法: $0 -or <old_registries> -nr <new_registry>"
    echo "示例: $0 -or 'docker.io,ghcr.io' -nr 'harbor.sisys.local/sisys/tools'"
    exit 1
}
# 1. 参数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -or|--old-registries) OLD_REGISTRIES="$2"; shift 2 ;;
        -nr|--new-registry) NEW_REGISTRY="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "❌ 未知参数: $1"; usage ;;
    esac
done
if [[ -z "$OLD_REGISTRIES" || -z "$NEW_REGISTRY" ]]; then
    usage
fi
IFS=',' read -r -a OLD_REG_ARRAY <<< "$OLD_REGISTRIES"
echo "🚀 开始执行 Registry 迁移任务..."
echo "📋 源: ${OLD_REG_ARRAY[*]}  ->  目标: $NEW_REGISTRY"
echo "================================================"
# 2. 性能优化：一次性获取所有已存在的镜像名称 (仅 REF)
echo "⏳ 正在扫描本地镜像库..."
EXISTING_IMAGES=$(sudo k3s ctr -n k8s.io images list -q 2>/dev/null)
# 3. 处理逻辑
sudo k3s crictl images | tail -n +2 | while read -r IMAGE TAG IMAGE_ID SIZE; do
    if [[ -z "$TAG" || "$TAG" == "<none>" ]]; then
        continue
    fi
    # 🛡️ 安全修补：处理 crictl 可能输出的逗号分隔 Tag (如 v1,v2)
    IFS=',' read -ra TAG_ARRAY <<< "$TAG"
    for SINGLE_TAG in "${TAG_ARRAY[@]}"; do
        FULL_IMAGE="$IMAGE:$SINGLE_TAG"
        for OLD_REG in "${OLD_REG_ARRAY[@]}"; do
            OLD_REG=$(echo "$OLD_REG" | tr -d '[:space:]')
            # 匹配前缀
            if [[ "$IMAGE" == "$OLD_REG"/* || "$IMAGE" == "$OLD_REG" ]]; then
                # 提取相对路径 (保留 Organization/Project)
                RELATIVE_PATH="${IMAGE#$OLD_REG}"
                RELATIVE_PATH="${RELATIVE_PATH#/}"
                NEW_IMAGE="$NEW_REGISTRY/$RELATIVE_PATH:$SINGLE_TAG"
                # 内存匹配检查 (-Fxq 确保整行严格匹配)
                if echo "$EXISTING_IMAGES" | grep -Fxq "$NEW_IMAGE"; then
                    echo "⏭️ 跳过 (已存在):$NEW_IMAGE"
                else
                    echo "🔄 正在处理: $FULL_IMAGE"
                    # 执行 Tag (禁止 rm，确保安全)
                    if sudo k3s ctr -n k8s.io images tag "$FULL_IMAGE" "$NEW_IMAGE" >/dev/null 2>&1; then
                        echo "✅ 成功 -> $NEW_IMAGE"
                    else
                        echo "❌ 失败 -> $FULL_IMAGE"
                    fi
                fi
                # 命中一个源仓库后跳出里层循环
                break
            fi
        done
    done
done
echo "🎉 全部完成！"
