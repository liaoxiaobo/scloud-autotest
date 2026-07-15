# Skill 实战案例：快速定位后端缺陷 + Playwright trace 的决定性作用

## 1. 案例价值

本案例面向测试开发团队，展示两个核心观点：

1. **/test-failure-analysis Skill 能够快速、系统化地定位失败根因**  
   通过结构化的证据收集和交叉验证，Skill 可以在几分钟内完成从"现象描述"到"根因分类"的完整分析。

2. **补全 Playwright trace（尤其是 network 抓包）对于问题定位具有决定性意义**  
   同一失败，无 trace 时只能给出"中置信度"的"用例问题"判断；补充 trace 后，直接拿到后端 API 请求/响应不一致的铁证，根因翻转为"产品缺陷（后端）"，置信度提升至"高"。

这是一个非常典型的"证据等级决定结论可靠性"的案例。

---

## 2. 失败现象概述

| 项 | 内容 |
|---|---|
| 用例名称 | `sugon_web.testcase.network.test_vpc_basic.TestVPCBasic#test_port_create_delete_manual_assign` |
| 用例标题 | 端口-创建和删除（手动分配-手动输入） |
| 服务域 | 网络服务 / 虚拟私有云 / 端口 |
| 发现时间 | 2026-07-15 |
| 测试环境 | 172.22.3.140，base 8.0.7.0 build 20260715_090416，deploy_mode: stack |
| 失败表象 | 创建端口弹窗提示"添加端口成功"，但后续删除时提示"未找到名称为 xxx 的数据行" |
| 最终根因分类 | **产品缺陷（后端）** |
| 最终置信度 | **高** |
| 已提交 Bug | [bug-view-430450](http://pm.mysugoncloud.com:82/bug-view-430450.html) |

两次运行的差异：

| 运行 | 预期 IP | 实际创建的 IP | 关键材料 | 初步结论 |
|---|---|---|---|---|
| 第一次 | 10.13.126.107 | 列表中无该 IP | Allure + 截图 + 日志 | 用例问题（中置信度） |
| 第二次 | 10.51.112.119 | 10.51.112.3 | 上述 + Playwright trace/network | 产品缺陷（高置信度） |

---

## 3. /test-failure-analysis Skill 使用过程

### 3.1 第一次调用：无 trace

输入材料：Allure result.json、失败截图、步骤日志、全链路日志、测试代码、Page Object 代码。

Skill 输出结论：

- 根因分类：**用例问题**
- 置信度：**中**
- 核心判断：用例标题为"手动输入"，但代码未传 quick_select=False，走了快速选择路径；且缺少创建结果的验证。
- 不确定点：缺少 Playwright trace，无法直接验证表单实际提交内容，无法排除后端问题。

### 3.2 第二次调用：补充 trace

输入材料：在第一次材料基础上，补充了 /Users/liaoxb/workspace/playwright-sugon/traces/trace_TestVPCBasic.zip。

Skill 输出结论：

- 根因分类：**产品缺陷（后端）**
- 置信度：**高**
- 核心判断：前端正确提交 ip_address: 10.51.112.119，后端返回 200 OK + "添加端口成功"，但实际创建的是 10.51.112.3。

### 3.3 两次结论对比

| 维度 | 第一次（无 trace） | 第二次（有 trace） |
|---|---|---|
| 根因分类 | 用例问题 | 产品缺陷（后端） |
| 置信度 | 中 | 高 |
| 能否定位后端 | 否，只能猜测 | 能，network 抓包直接证明 |
| 关键限制 | 无法确认表单实际提交值 | 无限制，证据链闭合 |

---

## 4. 决定性证据：trace.network 抓包

这是整个案例翻转的关键。

### 4.1 请求

POST /api/v1/vpc/ports

```json
{
  "network_id": "11b2cbf5-baa4-4abe-ac65-b35d23adda8b",
  "project_id": "admin-inner-project",
  "portSubnet": [
    {
      "ip_address": "10.51.112.119",
      "subnet_id": "5671c14b-afc6-456a-84a9-e13cf4b74fe5"
    }
  ],
  "mac_address": "",
  "port_encrypted_enabled": false
}
```

### 4.2 响应

```json
{
  "code": "OK",
  "message": "添加端口成功",
  "data": {
    "id": "6170a60a-7aa7-43ba-909c-21844681fef7",
    "fixed_ips": [
      {
        "subnet_id": "5671c14b-afc6-456a-84a9-e13cf4b74fe5",
        "ip_address": "10.51.112.3"
      }
    ]
  }
}
```

### 4.3 为什么这个证据是决定性的

- 请求中明确包含 ip_address: 10.51.112.119
- 响应中实际分配的 IP 是 10.51.112.3
- 响应 status 是 200 OK，message 是"添加端口成功"

这意味着：后端 API 在收到手动指定的 IP 后，没有按该 IP 创建端口，却返回了成功。没有任何前端交互方式（快速选择或手动输入）能够解释这种请求/响应不一致。

---

## 5. 给团队的启示

### 5.1 /test-failure-analysis Skill 的实战价值

1. **结构化**：强制按"读取案例库 -> 收集材料 -> 交叉验证 -> 输出结论"的流程执行，避免遗漏关键证据。
2. **可量化**：通过"置信度"和"证据等级"让结论可信度可见。
3. **快速**：在材料齐全的情况下，几分钟内即可完成一次完整的根因分析。
4. **可回溯**：输出格式统一，便于沉淀到知识库。

### 5.2 Playwright trace 的关键作用

| 证据类型 | 等级 | 能证明什么 | 本案例中的作用 |
|---|---|---|---|
| Allure result.json | 中 | 失败位置、错误信息 | 定位到删除时找不到行 |
| 失败截图 | 中高 | 页面视觉状态 | 证明列表中没有预期 IP |
| 全链路日志 | 中 | 操作顺序和断言结果 | 证明创建弹窗成功 |
| Playwright trace（network） | 最高 | 前端真实发送的请求和后端返回的响应 | 直接证明后端未按请求 IP 创建端口 |

关键结论：

> 当 UI 显示成功但后续状态不符合预期时，必须查看 trace 中的 network 抓包。只有网络请求/响应才能区分"前端提交错误"和"后端处理错误"。

### 5.3 后续最佳实践

1. **CI 中默认开启 tracing**  
   对于失败的用例，自动保留 trace 文件，供 /test-failure-analysis Skill 或人工深度分析使用。

2. **创建/修改类用例必须验证实际结果**  
   不要仅依赖"创建成功"弹窗，应断言资源的关键属性（如固定 IP、名称、状态）与预期一致。

3. **疑难失败优先补充 trace 后再调用 Skill**  
   如果一次分析置信度为"中"或"低"，应优先补全 trace 后再做第二次分析。

---

## 6. 第一次完整分析报告（无 Playwright trace）

### 0. 分析元数据

- 用例名称：`sugon_web.testcase.network.test_vpc_basic.TestVPCBasic#test_port_create_delete_manual_assign`
- 分析时间：2026-07-15
- 输入材料清单（按实际读取的材料逐项勾选，未获取的留空 [ ]）：
  - [x] Allure result.json（状态、trace、attachments 映射表）
  - [x] 失败信息附件（含 statusDetails.message）
  - [x] Allure 全链路日志附件
  - [x] 步骤日志附件
  - [x] 失败截图
  - [ ] Playwright trace（未提供）
  - [x] 测试代码
  - [x] Page Object 代码
  - [ ] Fixture 代码（未涉及失败链）
  - [ ] 其他

### 1. 结论

- 根因分类：**用例问题**
- 结论摘要：用例标题为"手动分配-手动输入"，但调用 port_create 时未显式传入 quick_select=False，实际走了"快速选择"路径；创建成功后也未验证目标 IP 是否出现在端口列表，直接执行删除导致找不到 10.13.126.107。
- 置信度：**中**
- 置信度理由：
  - 高可信度证据：失败截图明确显示端口 tab 中只有 3 个默认端口（10.13.126.1/2/3），没有目标 10.13.126.107；代码层面 port_create 默认 quick_select=True，而 test_port_create_delete_manual_assign 未覆盖该参数。
  - 不确定点：缺少 Playwright trace，无法直接验证表单提交时实际选中了哪个 IP/选项，也无法 100% 排除"后端返回成功但列表未刷新"的产品侧问题；但当前证据链更支持测试代码意图与实现不一致。

### 2. 关键证据

1. 用例意图与代码实现不匹配  
   test_port_create_delete_manual_assign 的 Allure 标题为"端口-创建和删除（手动分配-手动输入）"，但调用 port_create 时只传了 ip_address=port_ip，未传 quick_select=False。而 port_create 默认 quick_select=True，于是进入了"快速选择"分支，与用例名称暗示的"手动输入"模式不符。

2. 失败截图证明目标端口不存在  
   截图显示 VPC autotest-5i7 的端口 tab 中仅有 3 条记录：10.13.126.1（gw-port）、10.13.126.2（dhcp-port）、10.13.126.3。分页显示"共 3 条"，说明 10.13.126.107 从未出现在列表中。

3. 日志显示"创建成功"后立即删除失败  
   步骤1日志：断言通过，成功弹窗出现，文案包含"添加端口成功"。  
   步骤2日志：开始删除端口 10.13.126.107 -> 未找到名称为 10.13.126.107 的数据行。  
   说明用例在创建成功后直接假设目标 IP 已存在，缺少"列表中是否出现该 IP"的验证。

4. 用例缺少创建结果校验  
   同文件中 test_port_create_delete_quick_select 在创建后会调用 get_column_data 重新获取实际 IP，而 test_port_create_delete_manual_assign 直接拿随机生成的 port_ip 去删除，没有兜底校验。

### 3. 排除项

- 环境问题：SSH 登录、页面导航、VPC 创建均成功；同一浏览器上下文可正常操作其他 UI 元素，未见网络抖动或服务未就绪迹象。
- 产品缺陷：虽然存在"弹窗报成功但列表无端口"的表象，但现有材料无法直接证明后端真的创建了 10.13.126.107。更可能的解释是测试代码走了错误的"快速选择"路径，导致实际提交的不是预期 IP，或快速选择未选中有效值。若要进一步确认是否为产品问题，需要提供 Playwright trace 查看表单提交前的真实选中值。

### 4. 修复建议

短期修复：

1. 在 test_port_create_delete_manual_assign 中调用 port_create 时显式传入 quick_select=False，与用例标题"手动输入"保持一致。
2. 创建成功后增加断言，确认 port_ip 已出现在端口列表中，再执行删除。

长期建议：  
审查 port_create 的默认参数设计。当前 quick_select=True 作为默认值的语义是"快速选择"，对于标题明确为"手动输入"的用例容易造成误用。可考虑要求调用方必须显式指定 quick_select，或调整默认值为 False，避免默认行为与常见用例意图相反。

---

## 7. 第二次完整分析报告（含 Playwright trace / network 抓包）

### 0. 分析元数据

- 用例名称：`sugon_web.testcase.network.test_vpc_basic.TestVPCBasic#test_port_create_delete_manual_assign`
- 分析时间：2026-07-15
- 输入材料清单（按实际读取的材料逐项勾选，未获取的留空 [ ]）：
  - [x] Allure result.json
  - [x] 失败信息附件
  - [x] Allure 全链路日志附件
  - [x] 步骤日志附件
  - [x] 失败截图
  - [x] Playwright trace（含 DOM 快照、操作时间轴与 network 抓包）
  - [x] 测试代码
  - [x] Page Object 代码
  - [ ] Fixture 代码（未涉及失败链）
  - [x] 其他：trace.network 中 POST /api/v1/vpc/ports 的请求/响应完整抓包

### 1. 结论

- 根因分类：**产品缺陷**
- 结论摘要：前端按用户请求提交 ip_address: 10.51.112.119，后端返回 200 OK 与"添加端口成功"，但实际创建的端口固定 IP 被分配为 10.51.112.3；测试后续按预期 IP 删除时找不到目标行。
- 置信度：**高**
- 置信度理由：
  - Playwright trace 的 network 抓包是最高证据等级，直接证明请求与响应不一致。
  - 截图与 DOM 摘要显示新端口实际 IP 为 10.51.112.3，与响应数据一致。
  - 测试代码路径、前端操作日志、后端 API 响应三者无矛盾，证据链闭合。

### 2. 关键证据

1. 后端 API 请求与响应不一致（trace.network 最高等级证据）  
   POST /api/v1/vpc/ports：请求 body 中 ip_address 为 10.51.112.119，响应 status 为 200 OK，message 为"添加端口成功"，但实际 fixed_ips 为 10.51.112.3。这直接证明后端没有使用请求中指定的 IP，却返回了成功。

2. 失败截图与 DOM 摘要验证实际创建结果  
   端口 tab 中新增了一条记录（ID 6170a60a-7aa7-43ba-909c-21844681fef7），固定 IP 为 10.51.112.3，列表中不存在 10.51.112.119。该 ID 与 trace 响应中的 data.id 完全一致。

3. trace 操作时间轴证明前端正确提交了指定 IP  
   - fill("10.51.112.119") 成功写入快速选择框
   - get_by_text("10.51.112.119", exact=True).click() 成功选中下拉项
   - 点击"确定"后成功弹窗"添加端口成功"出现
   排除"前端未填值"或"选错下拉项"的推断。

4. 测试代码路径佐证  
   test_port_create_delete_manual_assign 调用 port_create(ip_address=port_ip) 时未传 quick_select=False，导致走的是"快速选择"分支而非"手动输入"分支。但这只影响前端交互方式，不影响后端 API 的处理结果；后端仍应尊重请求中的 ip_address。

### 3. 排除项

- 环境问题：同一环境 setup 成功、登录正常、VPC 创建成功、后端 API 返回 200，无网络抖动或服务未就绪迹象。
- 用例问题：虽然测试代码未验证实际创建 IP 存在不足，但失败直接原因是后端未按请求 IP 创建端口；用例代码本身不会导致后端响应中的 fixed_ips 与请求不一致。

### 4. 修复建议

短期修复（测试侧）：

1. 将 test_port_create_delete_manual_assign 中的 port_create 调用改为显式 quick_select=False，与用例标题"手动输入"保持一致。
2. 创建成功后增加断言，确认实际固定 IP 等于预期 IP，再执行删除；若不相等，应提前失败并暴露产品问题。

长期修复（产品侧）：  
后端 POST /api/v1/vpc/ports 在收到显式 ip_address 时，要么按该 IP 创建端口，要么在 IP 不可用时返回明确错误（如 400 Bad Request + "IP 已被占用/不在可分配范围"），不应静默分配其他 IP 后返回"添加端口成功"。

仍缺少的信息：无。当前证据已足以定位根因。

---

## 8. 附录：相关产物路径

| 产物类型 | 路径 |
|---|---|
| 第一次 Allure result | allure-result/network/test_vpc_basic/TestVPCBasic/de1f282c-bcaf-45e1-9880-46285c8dac0d-result.json |
| 第二次 Allure result | allure-result/network/test_vpc_basic/TestVPCBasic/94178cf1-4db6-4db1-a449-ffd1d920ed5c-result.json |
| Playwright trace | traces/trace_TestVPCBasic.zip |
| 测试代码 | sugon_web/testcase/network/test_vpc_basic.py:554-582 |
| Page Object | sugon_web/pages/network/vpc.py:629-662 |
| 本案例文档 | docs/test-failure-cases/port-create-delete-manual-assign-backend-defect.md |

---

## 9. 建议：回写至 Skill 历史案例库

本案例完美诠释了 /test-failure-analysis skill 中"证据等级优先于推断"的原则，建议作为新条目补充到：

`.claude/skills/test-failure-analysis/references/case_library.md`

建议新增模式标题：

> 后端 API 请求/响应不一致：UI 弹窗提示成功，但后续操作找不到目标资源 -> 使用 Playwright trace 的 network 抓包核对请求参数与实际返回数据。
