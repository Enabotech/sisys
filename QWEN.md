## Qwen Added Memories
- ArgoCD v3.2.7 安装方法：1) 创建命名空间 kubectl create namespace argocd；2) 安装指定版本 kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.2.7/manifests/install.yaml；3) 等待就绪 kubectl wait --for=condition=Ready pods --all -n argocd --timeout=600s；4) 安装 CLI curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/v3.2.7/argocd-linux-amd64 && chmod +x argocd && sudo mv argocd /usr/local/bin/；5) 获取密码 kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d；6) 登录 argocd login localhost:8080 --insecure --username admin --password $PASSWORD

- sudo密码H9yglwH7sdyj
