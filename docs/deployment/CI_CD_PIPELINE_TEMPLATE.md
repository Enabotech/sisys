# CI/CD Pipeline 模板配置指南

本文档提供完整的 CI/CD Pipeline 模板，涵盖代码质量、测试、安全扫描和部署流程。

## 目录

- [CI/CD Pipeline 模板配置指南](#cicd-pipeline-模板配置指南)
  - [目录](#目录)
  - [1. Pipeline 模板结构](#1-pipeline-模板结构)
    - [1.1 标准模板结构](#11-标准模板结构)
    - [1.2 可复用 Workflows](#12-可复用-workflows)
    - [1.3 环境变量配置](#13-环境变量配置)
  - [2. 代码质量门禁配置](#2-代码质量门禁配置)
    - [2.1 ESLint 配置](#21-eslint-配置)
    - [2.2 Prettier 配置](#22-prettier-配置)
    - [2.3 TypeScript 类型检查](#23-typescript-类型检查)
    - [2.4 SonarQube 集成](#24-sonarqube-集成)
  - [3. 单元测试配置](#3-单元测试配置)
    - [3.1 Jest 配置](#31-jest-配置)
    - [3.2 pytest 配置](#32-pytest-配置)
    - [3.3 测试覆盖率报告](#33-测试覆盖率报告)
    - [3.4 测试并行化](#34-测试并行化)
  - [4. 集成测试配置](#4-集成测试配置)
    - [4.1 Playwright E2E 测试](#41-playwright-e2e-测试)
    - [4.2 API 集成测试](#42-api-集成测试)
    - [4.3 数据库集成测试](#43-数据库集成测试)
    - [4.4 K3S 集群测试](#44-k3s-集群测试)
  - [5. 安全扫描配置](#5-安全扫描配置)
    - [5.1 依赖漏洞扫描](#51-依赖漏洞扫描)
    - [5.2 容器镜像扫描](#52-容器镜像扫描)
    - [5.3 代码安全扫描](#53-代码安全扫描)
    - [5.4 密钥泄露检测](#54-密钥泄露检测)
  - [6. 镜像构建和推送](#6-镜像构建和推送)
    - [6.1 Docker 构建优化](#61-docker-构建优化)
    - [6.2 Harbor 推送配置](#62-harbor-推送配置)
    - [6.3 多架构构建](#63-多架构构建)
    - [6.4 镜像签名](#64-镜像签名)
  - [7. ArgoCD 自动部署](#7-argocd-自动部署)
    - [7.1 GitOps 配置](#71-gitops-配置)
    - [7.2 自动同步配置](#72-自动同步配置)
    - [7.3 多环境部署](#73-多环境部署)
    - [7.4 回滚策略](#74-回滚策略)

---

## 1. Pipeline 模板结构

### 1.1 标准模板结构

```yaml
# .gitea/workflows/ci-cd-pipeline.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: harbor.example.com
  IMAGE_NAME: ${{ github.repository }}
  PYTHON_VERSION: '3.12'
  NODE_VERSION: '20'

jobs:
  # ========== 代码质量阶段 ==========
  code-quality:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: ESLint
        run: npm run lint

      - name: Prettier Check
        run: npm run format:check

      - name: TypeScript Check
        run: npm run type-check

  # ========== 单元测试阶段 ==========
  unit-tests:
    runs-on: docker
    needs: code-quality
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run Unit Tests
        run: |
          pytest tests/unit \
            --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=junit.xml

      - name: Upload Coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: junit.xml

  # ========== 集成测试阶段 ==========
  integration-tests:
    runs-on: kubernetes
    needs: unit-tests
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - name: Run Integration Tests
        run: pytest tests/integration --db-url=postgresql://postgres:testpass@postgres:5432/test

  # ========== 安全扫描阶段 ==========
  security-scan:
    runs-on: docker
    needs: code-quality
    steps:
      - uses: actions/checkout@v4

      - name: Dependency Scan
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

      - name: Secret Scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # ========== 构建阶段 ==========
  build:
    runs-on: docker
    needs: [integration-tests, security-scan]
    if: github.event_name == 'push'
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Harbor
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ secrets.HARBOR_USERNAME }}
          password: ${{ secrets.HARBOR_PASSWORD }}

      - name: Extract Metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=sha,prefix=sha-

      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache,mode=max

  # ========== 部署阶段 ==========
  deploy-dev:
    runs-on: docker
    needs: build
    if: github.ref == 'refs/heads/develop'
    environment: development
    steps:
      - uses: actions/checkout@v4

      - name: Update Dev Environment
        run: |
          kubectl config use-context dev-cluster
          kubectl set image deployment/app app=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          kubectl rollout status deployment/app

  deploy-prod:
    runs-on: docker
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Trigger ArgoCD Sync
        run: |
          argocd app sync production-app --async
          argocd app wait production-app --health
```

### 1.2 可复用 Workflows

创建可复用的 Workflow 模板：

```yaml
# .gitea/workflows/templates/unit-test.yml
name: Reusable Unit Test Workflow

on:
  workflow_call:
    inputs:
      python-version:
        required: false
        type: string
        default: '3.12'
      test-path:
        required: false
        type: string
        default: 'tests'
      coverage-threshold:
        required: false
        type: number
        default: 80

jobs:
  test:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}

      - name: Install Dependencies
        run: pip install -r requirements.txt -r requirements-test.txt

      - name: Run Tests
        run: |
          pytest ${{ inputs.test-path }} \
            --cov=src \
            --cov-fail-under=${{ inputs.coverage-threshold }} \
            --junitxml=junit.xml

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: junit.xml
```

使用可复用 Workflow：

```yaml
# .gitea/workflows/main.yml
name: Main Pipeline

on:
  push:
    branches: [main]

jobs:
  unit-tests:
    uses: ./.gitea/workflows/templates/unit-test.yml
    with:
      python-version: '3.12'
      test-path: 'tests/unit'
      coverage-threshold: 85
```

### 1.3 环境变量配置

```yaml
# .gitea/workflows/env-config.yml
env:
  # 通用配置
  CI: 'true'
  LOG_LEVEL: 'info'

  # 应用配置
  APP_ENV: 'production'
  APP_DEBUG: 'false'

  # 数据库配置
  DB_HOST: 'postgres.default.svc'
  DB_PORT: '5432'
  DB_NAME: 'appdb'

  # Redis 配置
  REDIS_HOST: 'redis.default.svc'
  REDIS_PORT: '6379'

  # Harbor 配置
  HARBOR_REGISTRY: 'harbor.example.com'
  HARBOR_PROJECT: 'sisys'

  # Kubernetes 配置
  KUBE_NAMESPACE: 'sisys-prod'
  KUBE_CONTEXT: 'prod-cluster'
```

---

## 2. 代码质量门禁配置

### 2.1 ESLint 配置

```javascript
// .eslintrc.js
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    project: './tsconfig.json',
  },
  plugins: ['@typescript-eslint', 'import', 'prettier'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:@typescript-eslint/recommended-requiring-type-checking',
    'plugin:import/typescript',
    'prettier',
  ],
  rules: {
    'prettier/prettier': 'error',
    '@typescript-eslint/explicit-function-return-type': 'warn',
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    'import/order': [
      'error',
      {
        groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
        'newlines-between': 'always',
      },
    ],
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
  overrides: [
    {
      files: ['**/*.test.ts', '**/*.spec.ts'],
      rules: {
        '@typescript-eslint/no-explicit-any': 'off',
        '@typescript-eslint/no-non-null-assertion': 'off',
      },
    },
  ],
};
```

CI 配置：

```yaml
- name: ESLint
  run: |
    npm run lint
    if [ $? -ne 0 ]; then
      echo "ESLint failed. Please fix the errors."
      exit 1
    fi
```

### 2.2 Prettier 配置

```javascript
// .prettierrc
module.exports = {
  printWidth: 100,
  tabWidth: 2,
  useTabs: false,
  semi: true,
  singleQuote: true,
  quoteProps: 'as-needed',
  trailingComma: 'es5',
  bracketSpacing: true,
  arrowParens: 'always',
  endOfLine: 'lf',
  overrides: [
    {
      files: '*.md',
      options: {
        proseWrap: 'always',
      },
    },
  ],
};
```

```javascript
// .prettierignore
node_modules
dist
build
coverage
*.min.js
```

CI 配置：

```yaml
- name: Prettier Check
  run: |
    npm run format:check
    if [ $? -ne 0 ]; then
      echo "Code formatting issues found. Run 'npm run format' to fix."
      exit 1
    fi
```

### 2.3 TypeScript 类型检查

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noImplicitThis": true,
    "alwaysStrict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "incremental": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

CI 配置：

```yaml
- name: TypeScript Check
  run: |
    npx tsc --noEmit
    if [ $? -ne 0 ]; then
      echo "TypeScript compilation errors found."
      exit 1
    fi
```

### 2.4 SonarQube 集成

```yaml
- name: SonarQube Scan
  uses: sonarsource/sonarqube-scan-action@v3
  env:
    SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
  with:
    args: >
      -Dsonar.projectKey=sisys
      -Dsonar.organization=my-org
      -Dsonar.sources=src
      -Dsonar.tests=tests
      -Dsonar.python.coverage.reportPaths=coverage.xml
      -Dsonar.typescript.lcov.reportPaths=coverage/lcov.info
```

质量门禁配置（在 SonarQube UI 中）：

```
- 新代码覆盖率 >= 80%
- 新代码重复率 <= 3%
- 新代码异味 <= 5
- 新代码 Bug = 0
- 新代码安全热点 = 0
- 新代码漏洞 = 0
```

---

## 3. 单元测试配置

### 3.1 Jest 配置

```javascript
// jest.config.js
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: ['**/*.test.ts', '**/*.spec.ts'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
  },
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/**/*.test.ts',
    '!src/index.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html', 'clover'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@test/(.*)$': '<rootDir>/tests/$1',
  },
  verbose: true,
  testTimeout: 10000,
};
```

### 3.2 pytest 配置

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-report=xml
    --cov-report=html
    --junitxml=junit.xml
    --maxfail=5
    -ra
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow running tests
    e2e: End-to-end tests
    db: Tests requiring database
    api: API tests
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
asyncio_mode = auto
```

```python
# conftest.py
import pytest
from typing import Generator

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """测试数据库 URL"""
    return "postgresql://postgres:testpass@localhost:5432/test_db"

@pytest.fixture
def client() -> Generator:
    """测试客户端"""
    from app.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_external_service() -> Mock:
    """模拟外部服务"""
    with patch('app.services.external.ExternalService') as mock:
        yield mock
```

### 3.3 测试覆盖率报告

```yaml
- name: Generate Coverage Report
  run: |
    pytest tests/unit \
      --cov=src \
      --cov-report=xml \
      --cov-report=html \
      --cov-report=term-missing \
      --cov-fail-under=80

- name: Upload Coverage to Harbor
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: |
      htmlcov/
      coverage.xml
    retention-days: 30

- name: Publish Coverage Badge
  run: |
    # 生成覆盖率徽章
    coverage=$(grep -o '"coverage": [0-9.]*' coverage.json | grep -o '[0-9.]*')
    echo "Coverage: $coverage%"
```

### 3.4 测试并行化

```yaml
- name: Run Tests in Parallel
  run: |
    # 使用 pytest-xdist 并行执行
    pip install pytest-xdist
    pytest tests/unit -n auto --cov=src --cov-report=xml

- name: Shard Tests
  run: |
    # 分片执行测试
    TOTAL_SHARDS=4
    SHARD_ID=${{ matrix.shard }}

    pytest tests/unit \
      --shard-id=$SHARD_ID \
      --total-shards=$TOTAL_SHARDS \
      --junitxml=junit-${SHARD_ID}.xml

strategy:
  matrix:
    shard: [1, 2, 3, 4]
```

---

## 4. 集成测试配置

### 4.1 Playwright E2E 测试

```yaml
# .gitea/workflows/e2e-tests.yml
name: E2E Tests

on:
  workflow_call:
    inputs:
      base-url:
        required: true
        type: string

jobs:
  e2e:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Run E2E Tests
        run: npx playwright test
        env:
          BASE_URL: ${{ inputs.base-url }}

      - name: Upload Test Results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 7
```

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html'], ['junit', { outputFile: 'junit.xml' }]],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
```

### 4.2 API 集成测试

```python
# tests/integration/test_api.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
@pytest.mark.integration
class TestAPIIntegration:

    @pytest.fixture
    async def client(self) -> AsyncClient:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_health_endpoint(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_authenticated_endpoint(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = await client.get("/api/users", headers=headers)
        assert response.status_code == 200
```

### 4.3 数据库集成测试

```yaml
# .gitea/workflows/db-integration-tests.yml
name: Database Integration Tests

on:
  workflow_call:

jobs:
  db-tests:
    runs-on: kubernetes
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 3

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Run Database Migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql://test:testpass@postgres:5432/testdb

      - name: Run DB Integration Tests
        run: pytest tests/integration/db --db-url=postgresql://test:testpass@postgres:5432/testdb
```

### 4.4 K3S 集群测试

```yaml
# .gitea/workflows/k3s-tests.yml
name: K3S Cluster Tests

on:
  workflow_call:

jobs:
  k3s-tests:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Start K3S Container
        run: |
          docker run -d --name k3s \
            --privileged \
            -p 6443:6443 \
            -p 80:80 \
            -p 443:443 \
            rancher/k3s:latest

      - name: Wait for K3S Ready
        run: |
          until docker exec k3s kubectl get nodes | grep Ready; do
            sleep 5
          done

      - name: Copy Kubeconfig
        run: |
          docker cp k3s:/etc/rancher/k3s/k3s.yaml ./kubeconfig
          export KUBECONFIG=$(pwd)/kubeconfig

      - name: Deploy Test Application
        run: |
          kubectl apply -f k8s/test-app.yaml
          kubectl wait --for=condition=available deployment/test-app --timeout=120s

      - name: Run K3S Tests
        run: pytest tests/integration/k3s --kubeconfig=./kubeconfig

      - name: Cleanup
        if: always()
        run: docker rm -f k3s
```

---

## 5. 安全扫描配置

### 5.1 依赖漏洞扫描

```yaml
# .gitea/workflows/security-scan.yml
name: Security Scan

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # 每天 2 AM 运行

jobs:
  dependency-scan:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      # Python 依赖扫描
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install pip-audit
        run: pip install pip-audit

      - name: Run pip-audit
        run: |
          pip-audit --format json --output pip-audit-results.json || true

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: pip-audit-results
          path: pip-audit-results.json

      # Node.js 依赖扫描
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Run npm audit
        run: |
          npm audit --json > npm-audit-results.json || true

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: npm-audit-results
          path: npm-audit-results.json

      # Snyk 扫描
      - name: Run Snyk
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high
```

### 5.2 容器镜像扫描

```yaml
- name: Build Image
  uses: docker/build-push-action@v5
  with:
    context: .
    push: false
    tags: local-test:latest
    load: true

- name: Run Trivy Scan
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'local-test:latest'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
    exit-code: '1'

- name: Upload Trivy Results
  uses: actions/upload-artifact@v4
  with:
    name: trivy-results
    path: trivy-results.sarif

- name: Harbor Scan
  run: |
    # 使用 Harbor 内置扫描
    curl -X POST \
      -H "Authorization: Bearer $HARBOR_TOKEN" \
      https://harbor.example.com/api/v2.0/projects/sisys/repositories/app/artifacts/latest/scan
```

### 5.3 代码安全扫描

```yaml
- name: Run Semgrep
  uses: returntocorp/semgrep-action@v1
  with:
    config: >-
      p/security-audit
      p/secrets
      p/owasp-top-ten
      p/xss
    generate_sarif: "1"

- name: Upload Semgrep Results
  uses: actions/upload-artifact@v4
  with:
    name: semgrep-results
    path: semgrep.sarif

- name: Run Bandit (Python)
  run: |
    pip install bandit
    bandit -r src -f json -o bandit-results.json
```

### 5.4 密钥泄露检测

```yaml
- name: Run Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}

- name: Run TruffleHog
  run: |
    pip install truffleHog
    trufflehog --regex --entropy=False . > trufflehog-results.txt || true

- name: Custom Secret Scan
  run: |
    # 自定义密钥模式扫描
    grep -rE "(password|secret|api_key|token)\s*[=:]\s*['\"][^'\"]+['\"]" \
      --include="*.py" --include="*.js" --include="*.yaml" \
      src/ || true
```

---

## 6. 镜像构建和推送

### 6.1 Docker 构建优化

```dockerfile
# Dockerfile
# 多阶段构建优化
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine AS runner

WORKDIR /app

# 创建非 root 用户
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# 复制依赖
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

# 复制应用代码
COPY --chown=nodejs:nodejs . .

USER nodejs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -q --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/index.js"]
```

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build with Cache
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache
    cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:buildcache,mode=max
    build-args: |
      BUILD_DATE=${{ github.event.head_commit.timestamp }}
      VCS_REF=${{ github.sha }}
```

### 6.2 Harbor 推送配置

```yaml
- name: Login to Harbor
  uses: docker/login-action@v3
  with:
    registry: harbor.example.com
    username: ${{ secrets.HARBOR_USERNAME }}
    password: ${{ secrets.HARBOR_PASSWORD }}

- name: Push to Harbor
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: |
      harbor.example.com/sisys/app:${{ github.sha }}
      harbor.example.com/sisys/app:latest
    labels: |
      org.opencontainers.image.source=${{ github.event.repository.html_url }}
      org.opencontainers.image.revision=${{ github.sha }}
      org.opencontainers.image.version=${{ github.ref_name }}
```

### 6.3 多架构构建

```yaml
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3

- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build Multi-arch Image
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    platforms: linux/amd64,linux/arm64
    tags: |
      harbor.example.com/sisys/app:${{ github.sha }}
      harbor.example.com/sisys/app:latest
```

### 6.4 镜像签名

```yaml
- name: Install Cosign
  uses: sigstore/cosign-installer@v3

- name: Sign Image
  run: |
    cosign sign --yes \
      harbor.example.com/sisys/app:${{ github.sha }}
  env:
    COSIGN_USERNAME: ${{ secrets.COSIGN_USERNAME }}
    COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}

- name: Verify Signature
  run: |
    cosign verify \
      --key cosign.pub \
      harbor.example.com/sisys/app:${{ github.sha }}
```

---

## 7. ArgoCD 自动部署

### 7.1 GitOps 配置

```yaml
# .gitea/workflows/argocd-deploy.yml
name: ArgoCD Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      image-tag:
        required: true
        type: string

jobs:
  deploy:
    runs-on: docker
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4

      - name: Setup ArgoCD CLI
        run: |
          curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
          chmod +x argocd
          sudo mv argocd /usr/local/bin/

      - name: Login to ArgoCD
        run: |
          argocd login argocd.example.com \
            --username ${{ secrets.ARGOCD_USERNAME }} \
            --password ${{ secrets.ARGOCD_PASSWORD }} \
            --insecure

      - name: Update Image Tag
        run: |
          # 更新 Kustomize 配置
          cd k8s/${{ inputs.environment }}
          kustomize edit set image app=harbor.example.com/sisys/app:${{ inputs.image-tag }}

      - name: Commit Changes
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add k8s/${{ inputs.environment }}/kustomization.yaml
          git commit -m "Update app image to ${{ inputs.image-tag }}"
          git push

      - name: Sync ArgoCD Application
        run: |
          argocd app sync sisys-${{ inputs.environment }} --async
          argocd app wait sisys-${{ inputs.environment }} --health --timeout 300
```

### 7.2 自动同步配置

```yaml
# argocd-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sisys-production
  namespace: argocd
spec:
  project: sisys

  source:
    repoURL: https://gitea.example.com/sisys/infra-config.git
    targetRevision: HEAD
    path: k8s/production

  destination:
    server: https://kubernetes.default.svc
    namespace: sisys-prod

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m

  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas

  healthChecks:
    - group: apps
      kind: Deployment
      check: |
        hs = {}
        if obj.status.readyReplicas == obj.spec.replicas then
          hs.status = "Healthy"
          hs.message = "Deployment is healthy"
        else
          hs.status = "Progressing"
          hs.message = "Waiting for deployment to be ready"
        end
        return hs
```

### 7.3 多环境部署

```yaml
# environments-config.yaml
environments:
  development:
    namespace: sisys-dev
    replicas: 1
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
    autoSync: true
    prune: true

  staging:
    namespace: sisys-staging
    replicas: 2
    resources:
      requests:
        cpu: 250m
        memory: 256Mi
      limits:
        cpu: 1000m
        memory: 1Gi
    autoSync: true
    prune: true

  production:
    namespace: sisys-prod
    replicas: 3
    resources:
      requests:
        cpu: 500m
        memory: 512Mi
      limits:
        cpu: 2000m
        memory: 4Gi
    autoSync: false  # 生产环境需要手动确认
    prune: true
    requireManualApproval: true
```

### 7.4 回滚策略

```yaml
- name: Health Check After Deploy
  run: |
    for i in {1..10}; do
      HEALTH=$(argocd app get sisys-production -o json | jq .status.health.status)
      if [ "$HEALTH" == "\"Healthy\"" ]; then
        echo "Deployment successful"
        exit 0
      fi
      echo "Waiting for healthy status... ($i/10)"
      sleep 30
    done

    echo "Deployment unhealthy, triggering rollback"
    argocd app rollback sisys-production
    exit 1

- name: Manual Approval Gate
  if: github.ref == 'refs/heads/main'
  uses: trstringer/manual-approval@v1
  with:
    secret: ${{ github.TOKEN }}
    approvers: admin1,admin2
    minimum-approvals: 1
    issue-title: "Deploy to Production"
    issue-body: "Please approve the deployment to production"
```

---

## 附录：完整 Pipeline 示例

```yaml
# .gitea/workflows/complete-pipeline.yml
name: Complete CI/CD Pipeline

on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: harbor.example.com
  IMAGE_NAME: sisys/app

jobs:
  # ========== 验证阶段 ==========
  validate:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4
      - name: Code Quality
        run: |
          npm ci
          npm run lint
          npm run format:check
          npx tsc --noEmit

  # ========== 测试阶段 ==========
  test:
    runs-on: docker
    needs: validate
    steps:
      - uses: actions/checkout@v4
      - name: Unit Tests
        run: |
          pip install -r requirements.txt -r requirements-test.txt
          pytest tests/unit --cov=src --cov-fail-under=80

  # ========== 安全阶段 ==========
  security:
    runs-on: docker
    needs: validate
    steps:
      - uses: actions/checkout@v4
      - name: Security Scan
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

  # ========== 构建阶段 ==========
  build:
    runs-on: docker
    needs: [test, security]
    if: github.event_name == 'push'
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

  # ========== 部署阶段 ==========
  deploy-dev:
    runs-on: docker
    needs: build
    if: github.ref == 'refs/heads/develop'
    environment: development
    steps:
      - name: Deploy to Dev
        run: kubectl set image deployment/app app=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

  deploy-prod:
    runs-on: docker
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    environment: production
    steps:
      - name: Deploy to Prod
        run: argocd app sync sisys-production --async
```
