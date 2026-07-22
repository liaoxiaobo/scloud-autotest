
## 1. 当前整体架构图（6 层依赖关系）

### 1.1 架构说明

下图展示框架的**静态代码依赖结构**，共 6 个层级（L5 → L0）。箭头表示「上层组件对下层组件的依赖或调用关系」。

核心约束：
- **上层可以调用下层，下层不可反向依赖上层**。
- 跨层穿透（如 Fixture 直接调 SSH、断言层直接调 SSH）属于架构异味，在图中用红色虚线标出。

```mermaid
graph TD
    subgraph L5 ["L5 测试层 — 只写步骤、断言与 Allure 注解"]
        T["test_*.py"]
    end

    subgraph L4 ["L4 资源层 — Fixture 生命周期 + Helper 纯函数"]
        F1["sugon_web/conftest.py<br/>browser / context / page / ssh_host"]
        F2["sugon_web/testcase/conftest.py<br/>vm / volume / eip 等参数化 Fixture"]
        F3["_xxx_fixtures.py + _xxx_helpers.py<br/>_build_xxx / _prepare_xxx"]
    end

    subgraph L3 ["L3 页面对象层 — UI 元素与单步操作"]
        P0["BasePage<br/>9 个 Mixin 组合"]
        P1["EcsPage<br/>pages/compute/ecs/ 包"]
        P2["EvsPage"]
        P3["VpcPage / 其他服务 Page"]
    end

    subgraph L2 ["L2 断言层 — 即时反馈 + 后端状态"]
        A1["PresentationAssertMixin<br/>UI 弹窗/提示断言"]
        A2["BusinessAssertMixin<br/>后端字段断言"]
    end

    subgraph L1 ["L1 后端验证层 — SSH + CLI"]
        S1["SSHClientBase<br/>连接/命令执行"]
        S2["ScliMixin<br/>scli 表格解析"]
        S3["CloudOpsMixin<br/>OpenStack 操作"]
    end

    subgraph L0 ["L0 基础设施层 — 零业务语义"]
        I1["Playwright 封装<br/>CustomLocator + expect 补丁"]
        I2["Config<br/>base.yaml + env.yaml + CLI"]
        I3["Utils<br/>logger / data / decorators / hooks"]
    end

    %% 正常依赖（上层 → 下层）
    T --> F2
    T --> P1
    T --> A2

    F2 --> P1
    F2 --> S3
    F2 --> F3

    P1 --> P0
    P0 --> I1
    P0 --> A1
    P0 --> A2

    A2 --> S2
    S3 --> S1
    I1 --> I2

    %% 跨层穿透（红色虚线标出）
    F2 -.->|"Fixture 直接调 SSH"| S1
    A2 -.->|"断言直接调 SSH"| S2

    %% 样式
    style T fill:#e1f5fe
    style F2 fill:#fff3e0
    style P1 fill:#e8f5e9
    style A2 fill:#fce4ec
    style S1 fill:#f3e5f5
    style S2 fill:#f3e5f5
    style I1 fill:#eeeeee
    style I2 fill:#eeeeee
    style I3 fill:#eeeeee
```

### 1.2 各层职责对照

| 层级 | 代表文件/类 | 核心职责 |
|------|------------|---------|
| L5 测试层 | `test_*.py` | 只写测试步骤、断言与 Allure 注解 |
| L4 资源层 | `conftest.py`、`_xxx_fixtures.py`、`_xxx_helpers.py` | 管理资源生命周期、环境组装 |
| L3 页面对象层 | `BasePage` + `EcsPage`/`EvsPage`/... | 封装页面元素定位器和单步业务操作 |
| L2 断言层 | `PopupAssertionMixin`、`EcsAssertionMixin` | 验证 UI 即时反馈与后端实际状态 |
| L1 后端验证层 | `SSHClientBase`、`ScliMixin`、`CloudOpsMixin` | SSH 连接与后端 CLI 操作 |
| L0 基础设施层 | `Playwright` 封装、`Config`、`Utils` | 零业务语义的基础能力 |

---

## 2. Fixture 作用域关系

```mermaid
graph LR
    subgraph Session [session 级]
        B["browser"]
        CFG["config"]
        SSH["ssh_host"]
        JH["jump_host"]
    end

    subgraph Class [class 级]
        BC["browser_context<br/>保持登录态"]
        SVM["ssh_vm"]
    end

    subgraph Function [function 级]
        P["page<br/>新建标签页并自动登录"]
    end

    B --> BC
    BC --> P
    JH --> SVM
    SSH --> SVM
```

---

## 3. 当前架构的关键跨层穿透点

```mermaid
graph LR
    subgraph L4 [L4 资源层]
        VM["vm fixture"]
    end

    subgraph L2 [L2 断言层]
        BA["BusinessAssertMixin"]
    end

    subgraph L1 [L1 SSH 层]
        SH["ssh_host.run"]
    end

    VM -.->|"直接调用 ssh_host.run 等待后端状态"| SH
    BA -.->|"直接调用 ssh_vm 执行 SSH 命令"| SH

    style VM fill:#fff3e0
    style BA fill:#fce4ec
    style SH fill:#f3e5f5
```

> 这些跨层穿透是后续架构优化的重点目标：应通过新增 L1.5 查询服务层进行隔离，使 Fixture 与断言层不再直接依赖 SSH 连接细节。
