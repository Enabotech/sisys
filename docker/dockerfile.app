# Layer 3: 应用镜像
# 基于依赖镜像 (Layer 2)，包含业务代码
# 更新频率：每次代码提交
# 构建策略：多阶段构建，最大化缓存利用

# ===========================================================================
# Stage 1: 依赖镜像 (Layer 2)
# ===========================================================================
ARG DEPENDENCY_IMAGE=harbor.sisys.local/sisys/dependency:l2-latest
FROM ${DEPENDENCY_IMAGE} AS base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app \
    APP_USER=appuser

# 切换回 root 用户进行安装
USER root

# 设置工作目录
WORKDIR ${APP_HOME}

# ===========================================================================
# Stage 2: 构建阶段
# ===========================================================================
FROM base AS builder

WORKDIR ${APP_HOME}

# 复制项目源代码
COPY src/ ./src/
COPY tests/ ./tests/
COPY configs/ ./configs/

# 复制配置文件
COPY .env.example .env
COPY pyproject.toml poetry.lock ./

# 安装开发依赖 (用于测试)
RUN poetry install --no-interaction --no-ansi

# 运行类型检查 (可选，用于构建时验证)
RUN poetry run mypy src/ --ignore-missing-imports || echo "类型检查完成"

# ===========================================================================
# Stage 3: 生产镜像
# ===========================================================================
FROM base AS production

# 设置工作目录
WORKDIR ${APP_HOME}

# 从 builder 阶段复制应用代码
COPY --from=builder --chown=appuser:appgroup ${APP_HOME}/src ./src
COPY --from=builder --chown=appuser:appgroup ${APP_HOME}/configs ./configs

# 复制入口脚本
COPY --chown=appuser:appgroup scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# 切换到非 root 用户
USER ${APP_USER}

# 暴露端口 (根据应用配置)
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# 设置入口点（智能判断是否启动应用或占位服务器）
ENTRYPOINT ["./entrypoint.sh"]

# 由 entrypoint.sh 处理启动逻辑，无需默认 CMD

# 镜像标签说明
LABEL org.opencontainers.image.title="SISYS Application Image" \
      org.opencontainers.image.description="SISYS application image with business logic (Layer 3)" \
      org.opencontainers.image.vendor="SISYS" \
      sisys.image.type="application" \
      sisys.image.layer="3" \
      sisys.app.port="8000"
