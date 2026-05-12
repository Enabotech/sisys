#!/usr/bin/env python3
with open("/home/agimtech/sisys/README.md", "r", encoding="utf-8") as f:
    content = f.read()

start_marker = "## 🏗️ 技术架构"
end_marker = "## 📏 质量指标"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found")
    exit(1)

new_architecture = """## 🏗️ 技术架构

```mermaid
graph TB
    subgraph Users["👤 用户层"]
        Executive["🏢 高管视图"]
        Analyst["📊 分析师视图"]
        Consultant["💼 顾问视图"]
        Integration["🔗 API 集成"]
    end

    subgraph Interface["🎯 接口层"]
        CLI["🖥️ CLI · Typer"]
        REST["🌐 REST API · FastAPI"]
        Skills["📋 Skills · L1/L2/L3"]
    end

    subgraph Application["⚙️ 应用层"]
        Doc["📄 文档处理"]
        Strategic["📊 战略分析"]
        Agent["🤖 Agent 协作"]
        Planning["📋 规划生成"]
    end

    subgraph Domain["💎 领域层"]
        subgraph Entities["核心实体"]
            D[Document]
            A[Agent]
            T[Tool]
            P[Plan]
            C[Checkpoint]
            Ar[Archive]
            R[RoutingLog]
        end
        subgraph Services["领域服务接口"]
            RAG[RAGService]
            TS[ToolService]
            AS[AgentService]
            PS[PlanService]
            ES[EvalService]
        end
    end

    subgraph Infrastructure["🏗️ 基础设施层"]
        subgraph Storage["💾 六层存储"]
            L0["📁 L0 · MEMORY.md"]
            L1["⚡ L1 · Redis"]
            L2["🗄️ L2 · PostgreSQL"]
            L3["🔮 L3 · Qdrant"]
            L4["📦 L4 · MinIO WORM"]
            L5["🕸️ L5 · Neo4j"]
        end
        subgraph Compute["⚡ 事件与计算"]
            MQ[🐰 RabbitMQ]
            RedisPS[📡 Redis Pub/Sub]
            Docker[🐳 Docker 沙箱]
            Lite[🤖 LiteLLM]
        end
    end

    Users --> Interface
    Interface --> Application
    Application --> Domain
    Domain --> Infrastructure

    style Users fill:#e1f5fe,stroke:#01579b
    style Interface fill:#e8f5e9,stroke:#2e7d32
    style Application fill:#fff3e0,stroke:#ef6c00
    style Domain fill:#fce4ec,stroke:#c2185b
    style Infrastructure fill:#f3e5f5,stroke:#7b1fa2
    style Storage fill:#e0f7fa,stroke:#00838f
    style Compute fill:#fff8e1,stroke:#f9a825
```

| 层级 | 组件 | 说明 |
|------|------|------|
| **用户层** | 高管/分析师/顾问视图 + API | 三视图架构 |
| **接口层** | CLI + REST API + Skills | Agent 友好接口 |
| **应用层** | 文档/战略分析/Agent协作/规划 | 用例服务 |
| **领域层** | 7 实体 + 5 服务接口 | 六边形核心 |
| **存储** | L0-MEMORY → L5-Neo4j | 六层分级 |
| **计算** | RabbitMQ + Docker + LiteLLM | 事件驱动 |

---

"""

new_content = content[:start_idx] + new_architecture + content[end_idx:]

with open("/home/agimtech/sisys/README.md", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done")
