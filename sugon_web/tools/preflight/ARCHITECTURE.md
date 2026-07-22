# 自动化前置环境检查架构图

如需汇报展示版，可直接打开 `PREFLIGHT_ARCHITECTURE_VISUAL.html`，样式参考流程海报图设计。

## 整体架构

```mermaid
flowchart TB
    Jenkins["Jenkins 参数 MARK<br/>preflight-all / frontend / backend / inspection / network"] --> Suite["关键词展开<br/>profiles/check_suites.yaml"]

    Suite --> HealthRun["健康巡检执行<br/>testcase/preflight/test_environment_health.py"]
    Suite --> ResourceRun["资源检查执行<br/>python -m sugon_web.tools.preflight"]

    HealthRun --> Frontend["前端检查<br/>登录 / 页面访问 / 运维入口"]
    HealthRun --> Backend["后台检查<br/>系统盘 / Pod 状态"]
    HealthRun --> Inspection["运维一键巡检<br/>巡检状态 / 失败项 / 告警项"]

    Frontend --> HealthJson["健康快照 JSON<br/>preflight-results/health_HOST.json"]
    Backend --> HealthJson
    Inspection --> HealthJson

    HealthJson --> HealthRules["健康规则<br/>profiles/health_rules.yaml"]
    HealthRules --> HealthMatrix["健康矩阵<br/>health_check.py"]

    ResourceRun --> ResourceProfile["资源画像<br/>profiles/resource_requirements.yaml"]
    ResourceRun --> EnvResources["环境资源输入<br/>envs.json / envs.example.json"]
    ResourceProfile --> ResourceMatrix["资源矩阵<br/>matrix.py"]
    EnvResources --> ResourceMatrix

    HealthMatrix --> Decision["最终前置结论<br/>哪些环境健康"]
    ResourceMatrix --> Decision2["资源结论<br/>哪些环境资源满足"]

    Decision --> Gate["自动化执行准入"]
    Decision2 --> Gate
```

## Jenkins 执行链路

```mermaid
sequenceDiagram
    participant User as 用户
    participant Jenkins as Jenkins
    participant Pytest as Pytest Preflight
    participant UI as 前端/运维页面
    participant SSH as 后台 SSH
    participant Tool as preflight 工具

    User->>Jenkins: MARK=preflight-all
    Jenkins->>Jenkins: 识别为前置检查关键词
    Jenkins->>Pytest: 运行 test_environment_health.py
    Pytest->>UI: 登录并进入运维一键巡检
    UI-->>Pytest: 返回巡检结果
    Pytest->>SSH: 采集系统盘和 Pod 状态
    SSH-->>Pytest: 返回后台健康数据
    Pytest->>Pytest: 合并 frontend/backend/inspection
    Pytest-->>Jenkins: 写入 preflight-results/health_HOST.json
    Jenkins->>Tool: health_check --suite preflight-all
    Tool-->>Jenkins: 输出健康矩阵和可执行环境结论
```

## 目录职责

```mermaid
flowchart LR
    Profiles["profiles/<br/>配置与规则"] --> Core["核心计算<br/>demand / health / matrix"]
    Collectors["collectors/<br/>采集器扩展点"] --> Core
    Core --> CLI["命令入口<br/>cli.py / health_check.py"]
    Suites["suites.py<br/>关键词展开"] --> CLI
    CLI --> Output["输出<br/>表格 / JSON / Jenkins 日志"]
```

## 推荐关键词

| Jenkins MARK | 含义 | 展开内容 |
| --- | --- | --- |
| `preflight-all` | 完整健康前置检查 | 前端 + 后台 + 运维一键巡检 |
| `frontend` | 前端健康检查 | 登录、页面访问、运维入口 |
| `backend` | 后台健康检查 | 系统盘、Pod 状态 |
| `inspection` | 运维巡检检查 | 一键巡检状态、失败项、告警项 |
| `network` | 网络模块资源检查 | 网络相关资源需求 |
| `storage` | 存储模块资源检查 | 存储相关资源需求 |
| `compute` | 计算模块资源检查 | 计算相关资源需求 |
