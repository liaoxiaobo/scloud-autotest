# 资源前置检查

这个目录用于沉淀自动化运行前的资源检查能力，目标是在执行 Playwright/pytest 用例前先判断当前环境是否满足模块运行条件。

架构介绍图见 `ARCHITECTURE.md`。

## 目录职责

- `profiles/resource_requirements.yaml`：资源画像，维护各业务模块的资源峰值和 IAM 配额最大值。
- `profiles/envs.example.json`：多个环境可用资源输入示例。
- `profiles/check_suites.yaml`：Jenkins/命令行关键词展开配置。
- `profiles/health_rules.yaml`：环境健康巡检规则。
- `collectors/`：环境资源采集器目录。当前先提供静态 JSON 采集，后续可以在这里接入云平台 API。
- `demand.py`：读取资源画像并计算模块需求。
- `matrix.py`：判断多个环境是否满足需求。
- `report.py`：终端表格和配额输出。
- `cli.py`：命令行入口。

## 常用命令

查看单模块资源最大值：

```powershell
python -m sugon_web.tools.preflight --modules network --mode max
```

用关键词展开资源模块：

```powershell
python -m sugon_web.tools.preflight --suite network --mode max
```

查看多个模块保守总量，并按 2 个 worker 放大：

```powershell
python -m sugon_web.tools.preflight --modules network,storage --mode sum --workers 2
```

检查单个环境是否满足：

```powershell
python -m sugon_web.tools.preflight --modules network --mode max --actual-json env_available.json
```

检查多个环境哪些可执行：

```powershell
python -m sugon_web.tools.preflight --modules network --mode max --envs-json sugon_web/tools/preflight/profiles/envs.example.json
```

输出 JSON，方便 CI 或调度脚本消费：

```powershell
python -m sugon_web.tools.preflight --modules all --mode sum --json
```

统计环境健康巡检结果：

```powershell
python -m sugon_web.tools.preflight.health_check --health-json sugon_web/tools/preflight/profiles/health.example.json
```

一次性展开全部前端、后台、运维巡检健康检查：

```powershell
python -m sugon_web.tools.preflight.health_check --suite preflight-all --health-json sugon_web/tools/preflight/profiles/health.example.json
```

只展开后台健康检查项：

```powershell
python -m sugon_web.tools.preflight.health_check --suite backend --health-json sugon_web/tools/preflight/profiles/health.example.json
```

只展开前端健康检查项：

```powershell
python -m sugon_web.tools.preflight.health_check --suite frontend --health-json sugon_web/tools/preflight/profiles/health.example.json
```

通过页面执行运维一键巡检：

```powershell
pytest sugon_web/testcase/preflight/test_environment_health.py -m preflight --host <env-host>
```

## 输入格式

单环境文件支持直接写可用值，也支持 `available/free/remaining` 或 `total-used`：

```json
{
  "ecs_instances": 20,
  "eip": {"available": 10},
  "evs_extra_gib": {"total": 3000, "used": 500}
}
```

多环境文件以环境名作为一级 key：

```json
{
  "env-a": {"ecs_instances": 20, "eip": 10},
  "env-b": {"ecs_instances": 8, "eip": 3}
}
```

健康巡检文件也支持多环境输入：

```json
{
  "env-a": {
    "frontend": {"reachable": true, "login": true, "ops_page": true},
    "backend": {"system_disk_usage_pct": 72, "pods_abnormal": 0},
    "inspection": {"status": "passed", "failed": 0, "warnings": 0}
  }
}
```

## 落地建议

第一阶段先维护 `profiles/resource_requirements.yaml` 和静态环境 JSON，用脚本输出“哪些环境满足”。第二阶段执行 `testcase/preflight/test_environment_health.py`，把运维一键巡检结果保存成健康 JSON。第三阶段在 `collectors/` 下接入云平台资源和后台健康 API，把 5 套环境的实时剩余资源、系统盘、Pod 状态生成统一 JSON。第四阶段把资源矩阵和健康矩阵接入自动化入口，在 pytest 执行前失败快返，或者根据矩阵自动选择同时满足“资源足够 + 环境健康”的环境。
