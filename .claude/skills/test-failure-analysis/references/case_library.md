# 测试失败分析案例库

按失败模式分类沉淀的典型 case，用于辅助后续同类问题的快速定位。

---

## 模式：动态表格行定位漂移（Locator 漂移）

### 案例：云硬盘-扩容 `test_volume_expand` 状态断言超时

**时间**：2026-06-03
**用例**：`test_volume_expand[params0]`（`new_size: 100`）
**根因分类**：用例问题

#### 现象

- `volume` fixture 创建云硬盘后，`assert_status(name, status="可用")` 等待 300 秒超时
- 报错显示实际状态为"正在使用"、25GiB、挂载到 `autotest-hj0pg`
- 但失败截图显示目标云硬盘 `autotest-yfbox` 状态已经是"可用"

#### 根因

`get_row_by_name` 遍历表格匹配到目标行后，返回 `target_rows.nth(i)`。在 `assert_status` 的 Playwright expect 重试期间，表格因新云硬盘创建导致行序变化，`nth(i)` 指向了另一行（状态为"正在使用"的其他云硬盘），持续空等至超时。

#### 关键证据链

1. **截图与报错状态矛盾**：截图目标行是"可用"，但报错捕获的是"正在使用"→ 监控对象错误
2. **Call log 行内容漂移**：expect 重试期间从"创建中 30GiB"变为"正在使用 25GiB"→ 目标行发生了变化
3. **同用例第二参数化通过**：`new_size: 500` 通过 → 排除环境与产品问题

#### 修复方向

- `get_row_by_name` 应返回基于文本过滤的稳定 locator（如 `tr.filter(has_text=name).first`），而非 `nth(i)`
- `assert_status` 可增加目标行名称校验，发现行漂移时提前报错而非空等超时

#### 排查口诀

> 看到"状态断言超时"，先问自己：截图里的目标资源状态真的不对吗？如果截图状态正常→ 极大概率是 **locator 漂移监控到了错误行**。

---

## 模式：Playwright fill 静默失效（表单填写未生效）

### 案例：CCE-修改时间同步服务器 `test_edit_time_sync_server` 成功消息断言超时

**时间**：2026-06-04
**用例**：`test_edit_time_sync_server`
**根因分类**：用例问题

#### 现象

- `cce_edit_time_sync` 方法执行后，`assert_popup_success("设置CCE集群时间同步器成功")` 等待 10 秒超时
- 报错显示等待 `.el-message__content` 未找到
- 失败截图显示"时间同步服务器"弹窗**仍然打开**，输入框为空（显示 placeholder），下方有红色校验错误"请输入有效的IP地址或域名"

#### 根因

Page Object 方法中先 `wait_for(state="visible")` 再 `fill()`，但 Element UI 表单组件在弹窗动画或 focus 未就绪时，`fill()` 可能未真正写入值（Playwright 不抛异常）。随后点击"确定"触发前端空值校验，弹窗未关闭，自然不会出现成功消息。

#### 关键证据链

1. **截图显示弹窗未关闭且输入框为空**：直接证明 `fill` 未生效，而非产品拒绝合法 IP
2. **步骤1 passed，步骤2 超时**：`cce_edit_time_sync` 内部无异常，但预期副作用（弹窗关闭）未发生 → 属于"静默失效"
3. **修复验证**：在 `fill()` 前增加 `click()` 确保 focus 后问题消失 → 确认根因是 focus 时机问题

#### 修复方向

- 对 Element UI 等组件化表单，**`fill()` 前显式 `click()` 确保 focus**，或在 `fill()` 后增加 `expect(input).to_have_value(value)` 断言兜底
- 审查同类封装方法，统一添加"填值后校验"，避免静默失效导致后续断言超时

#### 排查口诀

> 看到"弹窗/表单操作后断言超时"，先问自己：截图里弹窗真的关了吗？如果弹窗还开着且字段为空→ 极大概率是 **fill 未真正写入值**，而不是提交后端失败。

---
