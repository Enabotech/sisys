# YAML Configuration Comments Style Guide

**Created:** 2026-03-19  
**Story:** 0.7-argocd-continuous-deployment  
**LOW-1 Fix**

---

## Purpose

Standardize YAML configuration comments across the project for consistency and maintainability.

---

## General Principles

1. **Technical Configuration**: Use **English** comments
2. **Operational Documentation**: Use **Chinese** comments (for local team)
3. **Security Annotations**: Use `# pragma: allowlist secret` on separate line

---

## Comment Format

### 1. File Header Comments

```yaml
---
# ArgoCD Gitea Repository Credentials
# Purpose: ArgoCD connection to Gitea code repository
# Story 0.7: Task 4 - Gitea Integration
#
# Security Fix (CRITICAL-1): 2026-03-19
# - Remove plaintext token, use environment variable injection
# - Use Kustomize secretGenerator or External Secrets Operator
```

**Rules:**
- Use `#` followed by space
- First line: Component name
- Second line: Purpose description
- Third line: Story reference
- Blank line before detailed notes

### 2. Section Comments

```yaml
# =============================================================================
# 1. Container Security Configuration
# =============================================================================
```

**Rules:**
- Use separator lines for major sections
- Include section number and title
- Use consistent separator length

### 3. Inline Comments

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-gitea-creds
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repo-creds  # ArgoCD repo credentials
```

**Rules:**
- Two spaces before `#`
- Brief explanation
- Use English

### 4. Security Comments

```yaml
stringData:
  # Gitea Personal Access Token - injected via environment variable
  # Generate: Gitea → Settings → Applications → Generate New Token
  # Scopes: repository, user
  password: "${GITEA_ADMIN_TOKEN}"
  # pragma: allowlist secret
```

**Rules:**
- Place `# pragma: allowlist secret` on separate line
- After the sensitive field
- Explain token/secret source above the field

---

## Language Guidelines

### Use English For:
- ✅ YAML configuration comments
- ✅ Technical explanations
- ✅ Command examples
- ✅ API references

### Use Chinese For:
- ✅ Operational runbooks
- ✅ Troubleshooting guides
- ✅ User-facing documentation
- ✅ Team-specific notes

---

## Examples

### Good Example

```yaml
---
# ArgoCD Traefik IngressRoute Configuration
# Purpose: Expose ArgoCD web interface via Traefik
# Story 0.7: Task 2 - ArgoCD Deployment
#
# TLS Configuration (MEDIUM-2): 2026-03-19
# - Use cert-manager for Let's Encrypt certificates
# - Auto-renewal 15 days before expiration

apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: argocd-server
  namespace: argocd
  labels:
    app: argocd
    story: "0.7"
  annotations:
    description: "ArgoCD web interface IngressRoute"
    # TLS certificate managed by cert-manager
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  entryPoints:
    - websecure  # Traefik HTTPS entrypoint
  routes:
    - match: Host(`argocd.sisys.local`)
      kind: Rule
      services:
        - name: argocd-server
          port: 80  # Container HTTP port
          passHostHeader: true
          serversTransport: argocd-http
  tls:
    secretName: argocd-tls-secret  # Managed by cert-manager
```

### Bad Example

```yaml
---
# ArgoCD Traefik IngressRoute 配置
# 描述：使用 Traefik IngressRoute 暴露 ArgoCD Web 界面
# 修复：暂时移除 Middleware 依赖以测试基本路由
# pragma: allowlist secret

apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: argocd-server
  namespace: argocd
  labels:
    app: argocd
    story: "0.7"
  annotations:
    description: "ArgoCD Web 界面 IngressRoute"
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`argocd.sisys.local`)  # 域名配置
      kind: Rule
      services:
        - name: argocd-server
          port: 80
          passHostHeader: true
          serversTransport: argocd-http
  tls:
    secretName: argocd-tls-secret  # pragma: allowlist secret
```

**Issues:**
- ❌ Mixed Chinese and English
- ❌ `pragma` at end of line instead of separate line
- ❌ Inconsistent comment style

---

## Migration Guide

### For Existing Files

1. **Scan for Chinese comments**
   ```bash
   grep -r "#" deployments/argocd/*.yaml | grep -E "[\u4e00-\u9fff]"
   ```

2. **Translate to English**
   - Use technical translation tools
   - Keep proper nouns (product names, URLs)

3. **Update pragma comments**
   - Move to separate line
   - Place after sensitive field

4. **Review and test**
   - Verify YAML syntax
   - Test configuration

---

## Tools

### Linting

Use `yamllint` to check comment style:

```bash
yamllint deployments/argocd/
```

### Automated Checks

Add to CI/CD pipeline:

```yaml
# .github/workflows/lint.yaml
- name: Lint YAML comments
  run: |
    yamllint deployments/argocd/ --config-file .yamllint.yaml
```

---

## References

- [YAML Comment Best Practices](https://yaml.org/spec/)
- [Kubernetes Conventions](https://kubernetes.io/docs/concepts/)
- [GitOps Best Practices](https://opengitops.dev/)

---

**Last Updated:** 2026-03-19  
**Maintained By:** DevOps Team
