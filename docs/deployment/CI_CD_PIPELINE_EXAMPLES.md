# CI/CD Pipeline 完整 YAML 示例

**版本：** 1.0
**日期：** 2026-03-05
**适用：** Gitea Actions + K3S + Harbor + ArgoCD

---

## 📋 完整 Pipeline YAML 示例

### 示例 1: Python 项目完整 Pipeline

```yaml
# .gitea/workflows/ci-cd-pipeline.yml
name: SISYS CI/CD Pipeline

on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main, develop]

env:
  # 镜像仓库配置
  REGISTRY: harbor.local
  IMAGE_NAME: ${{ gitea.repository }}
  IMAGE_TAG: ${{ gitea.sha }}

  # Python 版本配置
  PYTHON_VERSION: '3.11'
  POETRY_VERSION: '1.8.0'

  # K3S 配置
  KUBECONFIG_DATA: ${{ secrets.KUBECONFIG_DATA }}

jobs:
  # ========== 阶段 1: 代码质量门禁 ==========
  code-quality:
    name: Code Quality
    runs-on: ubuntu-latest
    container: python:3.11-slim
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Poetry
        run: |
          pip install poetry==$POETRY_VERSION
          poetry config virtualenvs.create false

      - name: Install dependencies
        run: poetry install --with dev

      - name: Ruff Lint
        run: |
          poetry run ruff check src/ tests/
          echo "✅ Ruff linting passed"

      - name: Ruff Format
        run: |
          poetry run ruff format src/ tests/ --check
          echo "✅ Ruff formatting passed"

      - name: MyPy Type Check
        run: |
          poetry run mypy src/ --ignore-missing-imports
          echo "✅ MyPy type checking passed"

      - name: Domain Layer Zero-Dependency Check
        run: |
          python -c "
import ast
import sys

forbidden = {'fastapi', 'pydantic', 'sqlalchemy', 'redis', 'qdrant'}
for file in ['src/domain/**/*.py']:
    with open(file) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(f in alias.name for f in forbidden):
                    print(f'❌ Forbidden import: {alias.name}')
                    sys.exit(1)
print('✅ Domain layer zero-dependency check passed')
          "

  # ========== 阶段 2: 单元测试 ==========
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    container: python:3.11-slim
    needs: code-quality
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Poetry
        run: |
          pip install poetry==$POETRY_VERSION
          poetry config virtualenvs.create false

      - name: Install dependencies
        run: poetry install --with test

      - name: Run pytest with coverage
        run: |
          poetry run pytest tests/unit/ \
            --cov=src \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=80 \
            -v
          echo "✅ Unit tests passed"

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests

  # ========== 阶段 3: 集成测试 ==========
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_sisys
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Poetry
        run: |
          pip install poetry==$POETRY_VERSION
          poetry config virtualenvs.create false

      - name: Install dependencies
        run: poetry install --with test

      - name: Run integration tests
        run: |
          poetry run pytest tests/integration/ \
            --cov=src \
            --cov-report=xml \
            -v \
            --tb=short
          echo "✅ Integration tests passed"

  # ========== 阶段 4: 安全扫描 ==========
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install Poetry
        run: pip install poetry==$POETRY_VERSION

      - name: Install dependencies
        run: poetry install --only main

      - name: Bandit Security Scan
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json
          echo "✅ Bandit scan completed"

      - name: Safety Dependency Scan
        run: |
          pip install safety
          safety check --json > safety-report.json
          echo "✅ Safety scan completed"

      - name: Upload security reports
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
          retention-days: 30

  # ========== 阶段 5: 镜像构建和推送 ==========
  build-and-push:
    name: Build and Push
    runs-on: ubuntu-latest
    needs: [integration-tests, security-scan]
    if: github.event_name == 'push' && (github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v'))
    outputs:
      image_digest: ${{ steps.build.outputs.digest }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Harbor
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ secrets.HARBOR_USERNAME }}
          password: ${{ secrets.HARBOR_PASSWORD }}

      - name: Generate image tags
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}

      - name: Build and push Docker image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.prod
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: Upload Trivy results
        uses: actions/upload-artifact@v4
        with:
          name: trivy-results
          path: trivy-results.sarif
          retention-days: 30

  # ========== 阶段 6: ArgoCD 自动部署 ==========
  deploy:
    name: Deploy to K3S
    runs-on: ubuntu-latest
    needs: build-and-push
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: http://sisys.local
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup kubectl
        uses: azure/setup-kubectl@v3
        with:
          version: 'v1.28.0'

      - name: Configure kubeconfig
        run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBECONFIG_DATA }}" | base64 -d > ~/.kube/config
          chmod 600 ~/.kube/config

      - name: Update image tag in manifests
        run: |
          cd k8s/manifests
          sed -i "s|image: .*|image: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ env.IMAGE_TAG }}|g" deployment.yaml

      - name: Commit and push manifest changes
        run: |
          git config --global user.name 'Gitea Actions'
          git config --global user.email 'actions@gitea.local'
          git add k8s/manifests/deployment.yaml
          git commit -m "Update image tag to ${{ env.IMAGE_TAG }} [skip ci]"
          git push

      - name: Wait for ArgoCD sync
        run: |
          # ArgoCD will auto-sync the manifest changes
          echo "⏳ Waiting for ArgoCD to sync..."
          sleep 30

      - name: Verify deployment
        run: |
          kubectl rollout status deployment/sisys -n sisys --timeout=300s
          echo "✅ Deployment verified"

      - name: Health check
        run: |
          curl -f http://sisys.local/health || exit 1
          echo "✅ Health check passed"
```

---

### 示例 2: Node.js 项目 Pipeline

```yaml
# .gitea/workflows/nodejs-ci-cd.yml
name: Node.js CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: harbor.local
  IMAGE_NAME: ${{ gitea.repository }}
  NODE_VERSION: '20'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    container: node:${{ env.NODE_VERSION }}
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: npm ci

      - name: ESLint
        run: npm run lint

      - name: Prettier Check
        run: npm run format:check

      - name: TypeScript Check
        run: npm run type-check

      - name: Unit Tests
        run: npm run test:unit -- --coverage

      - name: Integration Tests
        run: npm run test:integration

  build-and-deploy:
    needs: lint-and-test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ gitea.sha }} .
          docker push ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ gitea.sha }}
```

---

### 示例 3: 多环境部署 Pipeline

```yaml
# .gitea/workflows/multi-env-deploy.yml
name: Multi-Environment Deploy

on:
  push:
    tags:
      - 'v*'

env:
  REGISTRY: harbor.local
  IMAGE_NAME: ${{ gitea.repository }}

jobs:
  deploy-dev:
    runs-on: ubuntu-latest
    environment: development
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Dev
        run: |
          # 部署到开发环境
          kubectl set image deployment/sisys sisys=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ gitea.ref }} -n sisys-dev

  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    needs: deploy-dev
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Staging
        run: |
          # 部署到预发布环境
          kubectl set image deployment/sisys sisys=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ gitea.ref }} -n sisys-staging

  deploy-prod:
    runs-on: ubuntu-latest
    environment: production
    needs: deploy-staging
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Production
        run: |
          # 部署到生产环境
          kubectl set image deployment/sisys sisys=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ gitea.ref }} -n sisys-prod
```

---

## ✅ 验收标准

- [ ] Pipeline YAML 可直接复制使用
- [ ] 所有阶段配置完整
- [ ] 环境变量配置清晰
- [ ] 密钥配置说明完整
- [ ] 故障排查指南完整

---

**下一步：** 复制示例 YAML 到 `.gitea/workflows/` 目录并根据项目需求调整
