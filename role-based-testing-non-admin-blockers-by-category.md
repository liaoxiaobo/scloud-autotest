# 非 admin 角色不可执行用例清单（按阻塞点 × 模块分类）

> 分析范围：`sugon_web/testcase/` 下全部 166 个 `test_*.py` 文件
> 扫描维度：直接/间接依赖 ops、硬编码项目、admin-only fixture、全局运营面权限
> 分析日期：2026-06-23
> 说明：本文档先按**阻塞点类型**一级分类，再按**模块**二级分类；同一用例可能因多个阻塞点被重复列出，文末给出重叠说明与去重汇总。

---

## 阻塞点总览

| 阻塞点类型 | 影响模块 | 涉及用例数（未去重） |
|-----------|---------|-------------------|
| 直接/间接依赖 `ops_page` / `OpsPage` | compute、network | 14 |
| 硬编码 `"默认项目"` | network | 4 |
| admin-only fixture | compute、backup、network | 24 |
| 全局运营面权限（IAM） | iam | 75 |
| **去重后总计** | **4 个模块** | **约 108** |

> 注：存在多处重叠，例如 4 个 ER 用例同时命中"依赖 ops"和"硬编码默认项目"。
> 另：OBS 用例虽硬编码组织 `sugoncloud/智能云事业部`，但公共测试即运行在该组织下，故当前环境不构成阻塞点，详见文末附录。

---

## 一、直接/间接依赖 ops_page / OpsPage

### 1.1 compute 模块（4 个用例）

| 文件 | 用例名 | 依赖方式 |
|------|-------|---------|
| `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | 参数注入 `ops_page` |
| `test_bms_011_017_cleanup.py` | `test_bms_011_instance_delete` | 参数注入 `ops_page`；实例不存在时回退调用 BMS_001 |
| `test_bms_011_017_cleanup.py` | `test_bms_012_register_delete` | 参数注入 `ops_page` |
| `test_bms_011_017_cleanup.py` | `test_bms_016_switch_group_delete` | 参数注入 `ops_page` |

### 1.2 network 模块（10 个用例）

| 文件 | 用例名 | 依赖方式 |
|------|-------|---------|
| `test_er_vpc_connectivity.py` | `test_er_vpc_connectivity` | 参数注入 `ops_page`，经 `_create_vm_and_bind_mfip` 调用 |
| `test_er_vpc_connectivity_non_ha.py` | `test_er_vpc_connectivity_non_ha` | 同上 |
| `test_er_peer_connection.py` | `test_er_peer_connection_ha2ha` | 参数注入 `ops_page` |
| `test_er_peer_connection.py` | `test_er_peer_connection_noha2noha` | 参数注入 `ops_page` |
| `test_peer_connect_routing.py` | `test_peer_connect_vpc_routing` | 参数注入 `ops_page` |
| `test_tm_inner_instance_validation.py` | `test_tm_inner_instance_validation` | 方法内部 `ops_page = OpsPage(tm_page.page)` |
| `test_tm_session_edit_validation.py` | `test_tm_session_edit_validation` | 方法内部 `ops_page = OpsPage(tm_page.page)` |
| `test_slb_peer_connect.py` | `TestLbPeerConnectScenario::test_lb_peer_connect_scenario` | 通过 `_lb_peer_fixtures.py::lb_peer_vms` 间接引入 |
| `test_slb_peer_connect.py` | `TestSlbV1HttpPeerForwardScenario::test_http_peer_forward` | 同上 |
| `test_slb_peer_connect.py` | `TestSlbV2HttpPeerForwardScenario::test_http_peer_forward` | 同上 |

### 1.3 涉及的 fixture 文件

| fixture 文件 | 创建 OpsPage 的 fixture | 影响范围 |
|-------------|------------------------|---------|
| `_lb_peer_fixtures.py` | `lb_peer_vms` | `test_slb_peer_connect.py` 全部用例 |

---

## 二、硬编码 "默认项目"

> 注：以下 4 个用例**同时属于阻塞点一**（依赖 `ops_page`）。

### 2.1 network 模块（4 个用例）

| 文件 | 用例名 | 硬编码位置 |
|------|-------|-----------|
| `test_er_vpc_connectivity.py` | `test_er_vpc_connectivity` | `_create_vm_and_bind_mfip(..., "默认项目", ...)` |
| `test_er_vpc_connectivity_non_ha.py` | `test_er_vpc_connectivity_non_ha` | 同上 |
| `test_er_peer_connection.py` | `test_er_peer_connection_ha2ha` | `_create_vm_and_bind_mfip(..., "默认项目", ...)` |
| `test_er_peer_connection.py` | `test_er_peer_connection_noha2noha` | 同上 |

---

## 三、admin-only fixture

### 3.1 pool fixture（1 个用例）

| 文件 | 用例名 | fixture |
|------|-------|---------|
| `test_ecs_basic.py` | `test_ecs_mount_bare_disk` | `pool` |

### 3.2 bms_instance fixture（2 个用例）

> 注：以下 2 个用例**同时属于阻塞点一**（依赖 `ops_page`）。

| 文件 | 用例名 | fixture |
|------|-------|---------|
| `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | `bms_instance` |
| `test_bms_011_017_cleanup.py` | `test_bms_011_instance_delete` | `bms_instance` |

### 3.3 vm_backup / _get_enabled_backup_nodes fixture（18 个用例）

| 文件 | 用例名 |
|------|-------|
| `test_back_basic.py` | `test_backup_create_scenario` |
| `test_back_basic.py` | `test_backup_once` |
| `test_back_basic.py` | `test_backup_search` |
| `test_back_basic.py` | `test_backup_task_start` |
| `test_back_basic.py` | `test_backup_edit_name` |
| `test_back_basic.py` | `test_backup_edit_vm` |
| `test_back_basic.py` | `test_backup_edit_policy` |
| `test_back_basic.py` | `test_backup_batch_operation` |
| `test_back_basic.py` | `test_backup_exec_full` |
| `test_back_basic.py` | `test_backup_reset_task` |
| `test_back_basic.py` | `test_backup_auto_migrate` |
| `test_back_basic.py` | `test_backup_manually_migrate` |
| `test_back_basic.py` | `test_resume_create_scenario` |
| `test_back_basic.py` | `test_resume_scenarios` |
| `test_back_basic.py` | `test_backup_migrate_start` |
| `test_back_recycle.py` | `test_backup_recovery` |
| `test_back_recycle.py` | `test_backup_recycle_search` |
| `test_back_recycle.py` | `test_backup_recycle_delete` |

### 3.4 `_lb_peer_fixtures.py::lb_peer_vms` fixture（3 个用例）

> 注：以下 3 个用例**同时属于阻塞点一**（依赖 `OpsPage`）。

| 文件 | 用例名 | fixture |
|------|-------|---------|
| `test_slb_peer_connect.py` | `TestLbPeerConnectScenario::test_lb_peer_connect_scenario` | `lb_peer_vms` |
| `test_slb_peer_connect.py` | `TestSlbV1HttpPeerForwardScenario::test_http_peer_forward` | `lb_peer_vms` |
| `test_slb_peer_connect.py` | `TestSlbV2HttpPeerForwardScenario::test_http_peer_forward` | `lb_peer_vms` |

---

## 四、全局运营面权限（IAM）

### 4.1 iam 模块（75 个用例 / 11 个文件）

| 文件 | 用例名 |
|------|-------|
| `test_iam_01_org_create.py` | `test_iam_create_org_and_login` |
| `test_iam_02_org_quota.py` | `test_iam_modify_compute_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_storage_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_network_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_disaster_recovery_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_database_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_bigdata_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_security_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_middleware_quota` |
| `test_iam_02_org_quota.py` | `test_iam_modify_container_quota` |
| `test_iam_03_org_child.py` | `test_iam_create_child_org` |
| `test_iam_03_org_child.py` | `test_iam_modify_child_org` |
| `test_iam_04_user_create.py` | `test_iam_create_user` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_alias` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_phone` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_email` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_extra` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_role` |
| `test_iam_05_user_modify.py` | `test_iam_verify_role_detail` |
| `test_iam_05_user_modify.py` | `test_iam_modify_user_combined` |
| `test_iam_06_user_admin_ops.py` | `test_iam_user_status_toggle` |
| `test_iam_06_user_admin_ops.py` | `test_iam_reset_password` |
| `test_iam_06_user_admin_ops.py` | `test_iam_user_expiry_past` |
| `test_iam_06_user_admin_ops.py` | `test_iam_user_expiry_today` |
| `test_iam_06_user_admin_ops.py` | `test_iam_user_expiry_future` |
| `test_iam_07_user_access_control.py` | `test_ip_deny` |
| `test_iam_07_user_access_control.py` | `test_ip_allow` |
| `test_iam_07_user_access_control.py` | `test_date_range` |
| `test_iam_07_user_access_control.py` | `test_date_past` |
| `test_iam_07_user_access_control.py` | `test_date_future` |
| `test_iam_07_user_access_control.py` | `test_date_today` |
| `test_iam_07_user_access_control.py` | `test_time_match` |
| `test_iam_07_user_access_control.py` | `test_time_mismatch` |
| `test_iam_07_user_access_control.py` | `test_combined_deny_ip` |
| `test_iam_07_user_access_control.py` | `test_combined_deny_time` |
| `test_iam_07_user_access_control.py` | `test_combined_deny_date` |
| `test_iam_07_user_access_control.py` | `test_combined_allow` |
| `test_iam_09_org_modify.py` | `test_iam_modify_org_name` |
| `test_iam_10_user_batch_ops.py` | `test_iam_batch_modify_user_status` |
| `test_iam_10_user_batch_ops.py` | `test_iam_batch_reset_password` |
| `test_iam_10_user_batch_ops.py` | `test_iam_batch_set_user_expiry` |
| `test_iam_10_user_batch_ops.py` | `test_iam_batch_access_control` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_alias` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_phone` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_email` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_extra` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_role` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_verify_role_detail` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_modify_combined` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_status_toggle` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_reset_password` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_expiry_past` |
| `test_iam_11_tenant_user_ops.py` | `test_iam_tenant_expiry_today` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_ip_deny` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_ip_allow` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_date_range` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_date_past` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_date_today` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_time_match` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_time_mismatch` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_combined_deny_ip` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_combined_deny_time` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_combined_deny_date` |
| `test_iam_11_tenant_user_ops.py` | `test_tenant_combined_allow` |
| `test_iam_12_project_management.py` | `test_iam_create_project` |
| `test_iam_12_project_management.py` | `test_iam_edit_project` |
| `test_iam_12_project_management.py` | `test_iam_modify_compute_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_storage_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_network_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_disaster_recovery_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_database_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_bigdata_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_security_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_middleware_quota` |
| `test_iam_12_project_management.py` | `test_iam_modify_container_quota` |

---

## 五、重叠说明

以下用例同时出现在多个阻塞点中，去重时只计一次：

| 用例 | 所属阻塞点 |
|------|-----------|
| `test_bms_001_soft_create.py::test_bms_create_with_page_image` | ops_page 依赖、bms_instance fixture |
| `test_bms_011_017_cleanup.py::test_bms_011_instance_delete` | ops_page 依赖、bms_instance fixture |
| `test_er_vpc_connectivity.py::test_er_vpc_connectivity` | ops_page 依赖、硬编码"默认项目" |
| `test_er_vpc_connectivity_non_ha.py::test_er_vpc_connectivity_non_ha` | ops_page 依赖、硬编码"默认项目" |
| `test_er_peer_connection.py::test_er_peer_connection_ha2ha` | ops_page 依赖、硬编码"默认项目" |
| `test_er_peer_connection.py::test_er_peer_connection_noha2noha` | ops_page 依赖、硬编码"默认项目" |
| `test_slb_peer_connect.py::TestLbPeerConnectScenario::test_lb_peer_connect_scenario` | ops_page 依赖、`lb_peer_vms` fixture |
| `test_slb_peer_connect.py::TestSlbV1HttpPeerForwardScenario::test_http_peer_forward` | ops_page 依赖、`lb_peer_vms` fixture |
| `test_slb_peer_connect.py::TestSlbV2HttpPeerForwardScenario::test_http_peer_forward` | ops_page 依赖、`lb_peer_vms` fixture |

---

## 六、按模块汇总（去重后）

| 模块 | 不可执行用例数（去重后） | 主要阻塞点 |
|------|------------------------|-----------|
| compute | 5 | ops_page、admin-only fixture |
| network | 10 | ops_page、硬编码"默认项目" |
| backup | 18 | admin-only fixture |
| iam | 75 | 全局运营面权限 |
| **合计** | **108** | - |

> 注：storage (OBS) 用例虽硬编码组织 `sugoncloud/智能云事业部`，但公共测试即运行在该组织下，当前环境不构成阻塞点，详见附录。

---

## 七、用例改造结果

以下用例因最近两次代码提交已具备在非 admin 角色下执行的能力，已从阻塞点清单中解决。

### 7.1 通过 `ops_page` fixture 改造解决（9 个用例）

提交 `6e61778` 改造了 `ops_page` fixture：admin 角色使用普通 page，非 admin 角色自动切换为 `admin_page`。因此以下原本依赖 `ops_page` 的用例不再被自动 skip。

#### compute 模块（4 个）

| 文件 | 用例名 | 原阻塞点 |
|------|-------|---------|
| `test_bms_001_soft_create.py` | `test_bms_create_with_page_image` | 阻塞点一：ops_page 依赖 |
| `test_bms_011_017_cleanup.py` | `test_bms_011_instance_delete` | 阻塞点一：ops_page 依赖 |
| `test_bms_011_017_cleanup.py` | `test_bms_012_register_delete` | 阻塞点一：ops_page 依赖 |
| `test_bms_011_017_cleanup.py` | `test_bms_016_switch_group_delete` | 阻塞点一：ops_page 依赖 |

#### network 模块（5 个）

| 文件 | 用例名 | 原阻塞点 |
|------|-------|---------|
| `test_er_vpc_connectivity.py` | `test_er_vpc_connectivity` | 阻塞点一：ops_page 依赖 |
| `test_er_vpc_connectivity_non_ha.py` | `test_er_vpc_connectivity_non_ha` | 阻塞点一：ops_page 依赖 |
| `test_er_peer_connection.py` | `test_er_peer_connection_ha2ha` | 阻塞点一：ops_page 依赖 |
| `test_er_peer_connection.py` | `test_er_peer_connection_noha2noha` | 阻塞点一：ops_page 依赖 |
| `test_peer_connect_routing.py` | `test_peer_connect_vpc_routing` | 阻塞点一：ops_page 依赖 |

### 7.2 通过 `pool` fixture 间接解决（1 个用例）

`pool` fixture 依赖 `ops_page`，ops_page 改造后 `pool` 在非 admin 角色下也可通过 `admin_page` 执行存储池操作。

| 模块 | 文件 | 用例名 | 原阻塞点 |
|------|------|-------|---------|
| compute | `test_ecs_basic.py` | `test_ecs_mount_bare_disk` | 阻塞点三：admin-only fixture（pool） |

### 7.3 合计已解决

| 原阻塞点 | 已解决用例数 |
|---------|------------|
| 阻塞点一：ops_page 依赖 | 9 |
| 阻塞点三：admin-only fixture | 1 |
| **合计** | **10** |

### 7.4 仍受阻塞的关联用例

以下用例虽然部分解决了 ops_page 问题，但仍存在其他阻塞点：

| 用例 | 已解决部分 | 剩余阻塞点 |
|------|-----------|-----------|
| `test_bms_001_soft_create.py::test_bms_create_with_page_image` | ops_page 可用 | `bms_instance` fixture 仍依赖 BMS 基础设施前置条件 |
| `test_bms_011_017_cleanup.py::test_bms_011_instance_delete` | ops_page 可用 | `bms_instance` fixture 仍依赖 BMS 基础设施前置条件 |

---

## 附录：OBS 组织硬编码（当前环境非阻塞点）

### 背景说明

经确认，**公共测试即运行在 `sugoncloud/智能云事业部` 组织下的一个项目**。因此，OBS 用例中硬编码的 `org_name=["sugoncloud", "智能云事业部"]` 与当前测试环境的组织上下文一致，**在非 admin 角色下仍可正常执行**，不构成当前环境的阻塞点。

### 涉及用例（23 个 / 17 个文件）

| 文件 | 用例名 |
|------|-------|
| `test_obs_bucket_create.py` | `test_obs_bucket_create_cancel` |
| `test_obs_bucket_create.py` | `test_obs_bucket_create_success` |
| `test_obs_bucket_delete.py` | `test_obs_bucket_delete_validation` |
| `test_obs_bucket_quota_modify.py` | `test_obs_bucket_capacity_limit_modify` |
| `test_obs_bucket_quota_modify.py` | `test_obs_bucket_object_limit_modify` |
| `test_obs_bucket_acl.py` | `test_obs_bucket_acl_configure` |
| `test_obs_bucket_acl.py` | `test_obs_bucket_acl_write_permission` |
| `test_obs_bucket_acl.py` | `test_obs_bucket_acl_public_access_validation` |
| `test_obs_bucket_acl.py` | `test_obs_disable_access_key` |
| `test_obs_bucket_storage_policy.py` | `test_obs_bucket_storage_policy_configure` |
| `test_obs_bucket_lifecycle.py` | `test_obs_bucket_lifecycle_create_all_objects` |
| `test_obs_credential_create.py` | `test_obs_credential_create_access_key` |
| `test_obs_object_acl.py` | `test_obs_object_acl_configure` |
| `test_obs_object_acl_user_roles.py` | `test_obs_object_acl_user_roles` |
| `test_obs_object_download_types.py` | `test_obs_object_download_types_validation` |
| `test_obs_object_metadata_add_existing.py` | `test_obs_object_metadata_add_existing_validation` |
| `test_obs_object_metadata_delete.py` | `test_obs_object_metadata_delete_validation` |
| `test_obs_object_metadata_edit.py` | `test_obs_object_metadata_edit_validation` |
| `test_obs_mirror_backsource.py` | `test_obs_mirror_backsource_rule_effective` |
| `test_obs_redirect_backsource.py` | `test_obs_redirect_backsource_rule_effective` |
| `test_obs_proxy_add_custom_domain.py` | `test_obs_proxy_add_custom_domain` |
| `test_obs_batch_upload_in_folder.py` | `test_obs_batch_upload_in_folder` |

### 潜在风险与建议

虽然当前环境不受影响，但硬编码组织路径存在以下风险：

1. **可移植性差**：切换到其他组织/项目的测试环境时，所有 OBS 用例将因组织路径不匹配而失败。
2. **维护成本高**：组织名称变更时需批量修改 17 个文件。
3. **无法验证非该组织下的用户场景**：如果未来需要测试普通租户用户访问 OBS，硬编码会限制测试覆盖。

**建议改造为动态获取当前用户组织**：

```python
# 改造前
org_name = ["sugoncloud", "智能云事业部"]

# 改造后
org_name = _get_current_user_org(page)  # 从当前登录用户上下文或 Config 动态读取
```

改造优先级：**低**。当前可先集中精力处理 ops_page 依赖、admin-only fixture 和 IAM 权限等真实阻塞点。
