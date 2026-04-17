#!/bin/bash

# ================= 默认参数 =================
OLD_REGISTRIES=""
NEW_REGISTRY=""
MATCH_PATTERN=""
DRY_RUN=false

# ================= 帮助信息 =================
usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "模式 1: 本地重命名 (打 Tag)"
    echo "  -or, --old-registries  <列表>    旧 Registry (逗号分隔)，如 'docker.io,ghcr.io'"
    echo "  -nr, --new-registry    <路径>    新 Registry 前缀，如 'harbor.sisys.local/sisys/tools'"
    echo ""
    echo "模式 2: 远程推送"
    echo "  -matchtags           <模式>      匹配并推送镜像，支持通配符 '*'"
    echo "                                   示例: -matchtags 'harbor.sisys.local/sisys/tools/*'"
    echo ""
    echo "通用选项:"
    echo "  -n, --dry-run                     模拟执行，仅打印命令"
    echo "  -h, --help                        显示帮助"
    exit 1
}

# ================= 参数解析 =================
while [[ $# -gt 0 ]]; do
    case $1 in
        -or|--old-registries) OLD_REGISTRIES="$2"; shift 2 ;;
        -nr|--new-registry) NEW_REGISTRY="$2"; shift 2 ;;
        -matchtags) MATCH_PATTERN="$2"; shift 2 ;;
        -n|--dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage ;;
        *) echo "❌ 未知参数: $1"; usage ;;
    esac
done

# ================= 逻辑入口 =================

# [模式 1]: 本地 Tag
if [[ -n "$OLD_REGISTRIES" && -n "$NEW_REGISTRY" ]]; then
    echo "🚀 [模式 1] 本地 Registry 替换..."
    echo "📋 源: $OLD_REGISTRIES  ->  目标: $NEW_REGISTRY"
    echo "================================================"

    # 预加载镜像列表 (性能优化)
    EXISTING_IMAGES=$(sudo k3s ctr -n k8s.io images list -q 2>/dev/null)
    IFS=',' read -r -a OLD_REG_ARRAY <<< "$OLD_REGISTRIES"

    sudo k3s crictl images | tail -n +2 | while read -r IMAGE TAG IMAGE_ID SIZE; do
        [[ -z "$TAG" || "$TAG" == "<none>" ]] && continue
        IFS=',' read -ra TAG_ARRAY <<< "$TAG"

        for SINGLE_TAG in "${TAG_ARRAY[@]}"; do
            FULL_IMAGE="$IMAGE:$SINGLE_TAG"
            for OLD_REG in "${OLD_REG_ARRAY[@]}"; do
                OLD_REG=$(echo "$OLD_REG" | tr -d '[:space:]')
                if [[ "$IMAGE" == "$OLD_REG"/* || "$IMAGE" == "$OLD_REG" ]]; then
                    RELATIVE_PATH="${IMAGE#$OLD_REG}"
                    RELATIVE_PATH="${RELATIVE_PATH#/}"
                    NEW_IMAGE="$NEW_REGISTRY/$RELATIVE_PATH:$SINGLE_TAG"

                    if echo "$EXISTING_IMAGES" | grep -Fxq "$NEW_IMAGE"; then
                        echo "⏭️ 跳过 (已存在): $NEW_IMAGE"
                    else
                        echo "🔄 Tag: $FULL_IMAGE -> $NEW_IMAGE"
                        [[ "$DRY_RUN" == false ]] && sudo k3s ctr -n k8s.io images tag "$FULL_IMAGE" "$NEW_IMAGE" >/dev/null 2>&1
                    fi
                    break
                fi
            done
        done
    done
    echo "✅ 本地 Tag 任务完成"
fi

# [模式 2]: 远程推送
if [[ -n "$MATCH_PATTERN" ]]; then
    echo "🚀 [模式 2] 远程镜像推送..."
    echo "📋 匹配模式: $MATCH_PATTERN"
    echo "================================================"

    HARBOR_HOST=$(echo "$MATCH_PATTERN" | cut -d'/' -f1)

    # 预检认证 (使用 sudo 检查 Root 目录，避免权限拒绝)
    if sudo [ -f "/root/.docker/config.json" ]; then
        if ! sudo grep -q "$HARBOR_HOST" "/root/.docker/config.json"; then
            echo "⚠️  警告: 未在 /root/.docker/config.json 中找到 $HARBOR_HOST 的认证信息"
            echo "   请执行: sudo docker login $HARBOR_HOST"
        fi
    else
        echo "⚠️  警告: 未找到 /root/.docker/config.json"
    fi

    sudo k3s crictl images | tail -n +2 | while read -r IMAGE TAG IMAGE_ID SIZE; do
        [[ -z "$TAG" || "$TAG" == "<none>" ]] && continue
        IFS=',' read -ra TAG_ARRAY <<< "$TAG"

        for SINGLE_TAG in "${TAG_ARRAY[@]}"; do
            FULL_IMAGE="$IMAGE:$SINGLE_TAG"

            # 匹配逻辑
            if [[ "$FULL_IMAGE" == $MATCH_PATTERN ]]; then
                echo "📤 Push: $FULL_IMAGE"

                if [[ "$DRY_RUN" == true ]]; then
                    echo "   📝 (模拟) 推送中..."
                else
                    # 推送镜像 (增加详细错误输出)
                    ERROR_LOG=$(sudo k3s ctr -n k8s.io images push "$FULL_IMAGE" 2>&1)
                    if [[ $? -eq 0 ]]; then
                        echo "   ✅ 成功"
                    else
                        # 提取关键错误信息
                        ERR_MSG=$(echo "$ERROR_LOG" | grep -oP '(content digest.*not found|unauthorized|timeout|refused)' | head -n 1)
                        if [[ -n "$ERR_MSG" ]]; then
                            echo "   ❌ 失败: $ERR_MSG"
                        else
                            echo "   ❌ 失败 (未知错误)"
                        fi
                    fi
                fi
            fi
        done
    done
    echo "✅ 推送任务完成"
fi

if [[ -z "$OLD_REGISTRIES" && -z "$MATCH_PATTERN" ]]; then
    usage
fi
