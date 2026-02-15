---
description: 根据可用的设计工件，将现有任务转换为可操作的、依赖有序的 GitHub issues。
---

---
description: 根据可用的设计工件，将现有任务转换为可操作的、依赖有序的 GitHub issues。
tools: ['github/github-mcp-server/issue_write']
---

## 用户输入

```text
$ARGUMENTS
```

如果用户输入不为空，你**必须**在继续之前考虑用户输入。

## 概述

1. 从仓库根目录运行 `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks` 并解析 FEATURE_DIR 和 AVAILABLE_DOCS 列表。所有路径必须是绝对的。对于参数中的单引号，如 "I'm Groot"，使用转义语法：例如 'I'\''m Groot'（如果可能，使用双引号："I'm Groot"）。
2. 从执行的脚本中，提取**任务**的路径。
3. 通过运行以下命令获取 Git 远程：

```bash
git config --get remote.origin.url
```

> [!CAUTION]
> 仅当远程是 GITHUB URL 时才继续下一步

4. 对于列表中的每个任务，使用 GitHub MCP 服务器在代表 Git 远程的仓库中创建新 issue。

> [!CAUTION]
> 在任何情况下都不要在与远程 URL 不匹配的仓库中创建 issues

