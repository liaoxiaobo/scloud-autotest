## 1. 测试执行流程图（端到端数据流）

### 1.1 流程说明

下图展示一次完整测试执行的**端到端数据流**：从 Jenkins Pipeline 触发，到 Allure 报告生成，最终飞书推送通知，形成闭环。

```mermaid
sequenceDiagram
    autonumber
    participant J as Jenkins CI
    participant P as pytest 引擎
    participant C as Config 配置系统
    participant F as Fixture 系统
    participant PO as PageObject
    participant PW as Playwright
    participant W as Web UI
    participant A as 断言层
    participant S as SSH 后端
    participant AL as Allure 报告
    participant FE as 飞书通知

    J->>P: 触发 Pipeline 执行
    P->>C: 加载配置（base.yaml → env.yaml → CLI 参数）
    P->>F: 初始化 session 级 fixtures
    F-->>P: 返回 browser + ssh_host
    P->>F: 初始化 function 级 fixtures
    F-->>P: 返回已登录 page

    loop 遍历所有测试方法
        P->>PO: 调用 ecs_create(request)
        PO->>PW: click / fill / select
        PW->>W: 发起 HTTP 请求
        W-->>PW: 返回页面响应
        PW-->>PO: 操作完成
        PO-->>P: 返回创建结果

        P->>A: assert_vm_status(name, "运行中")
        A->>S: scli guest_show
        S-->>A: 返回后端状态
        A-->>P: 断言通过 / 失败

        alt 断言失败
            P->>AL: attach 截图 + trace + 日志
        end

        P->>F: yield 结束，进入 teardown
        F-->>P: 清理 vm / volume 完成
    end

    P->>AL: 生成 allure-report
    AL->>FE: 推送测试结果摘要
    AL->>FE: 推送 AI 失败分析结果
    FE-->>J: 构建结果通知
```

### 1.2 关键阶段说明

| 阶段 | 说明 | 对应组件 |
|------|------|---------|
| 1. 触发执行 | Jenkins Pipeline 调用 pytest 命令 | Jenkins → pytest |
| 2. 配置加载 | 三层配置合并：base.yaml → env.yaml → CLI 参数 | `Config` |
| 3. Session 初始化 | 创建 browser、ssh_host 等会话级资源 | `sugon_web/conftest.py` |
| 4. Function 初始化 | 每个测试方法新建 page 并自动登录 | `_create_logged_in_page` |
| 5. UI 操作 | PageObject 调用 Playwright 与 Web UI 交互 | `EcsPage` → Playwright → Web UI |
| 6. 后端断言 | 断言层通过 SSH 执行 scli 命令验证实际状态 | `EcsAssertionMixin` → `SSHClientBase` |
| 7. 失败现场 | 断言失败时自动截图、附加 trace 到 Allure | `pytest_runtest_makereport` |
| 8. 资源清理 | yield 结束后按依赖顺序清理资源 | `vm` fixture teardown |
| 9. 报告生成 | Allure 汇总测试结果与环境信息 | Allure |
| 10. 通知推送 | 飞书机器人推送结果摘要 + AI 失败分析 | 飞书通知 |
