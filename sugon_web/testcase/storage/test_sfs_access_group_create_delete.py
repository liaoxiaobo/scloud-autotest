import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-权限组新建与删除功能验证')
class TestSFSAccessGroupCreateDelete:
    """验证文件存储 SFS 实例详情页权限组的新建和删除功能。

    场景1：新建权限组（用例 5694）
    场景2：删除权限组（用例 5695）

    每个测试方法独立创建/清理 NFS SFS 实例，避免依赖环境预置实例。
    """

    @allure.title("文件存储-权限组新建")
    def test_sfs_access_group_create(self, sfs_page, sfs_instance):
        """在 SFS 实例详情页权限组 Tab 中新建权限组并验证。"""
        instance_name = sfs_instance["name"]
        logger.info(f"使用本用例创建的 SFS 实例: {instance_name}")

        ag_name = f"ag-{random_data()}"
        ag_desc = f"测试权限组_desc_{random_data()}!@#"

        with allure_step_log("步骤1: 进入实例详情页并切换到权限组 Tab"):
            sfs_page.sfs_instance_goto_detail(instance_name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("步骤2: 打开新建权限组弹窗并填写表单"):
            sfs_page.sfs_access_group_create(ag_name, ag_desc)

        with allure_step_log("步骤3: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("创建文件存储权限组成功")
            sfs_page.assert_list_contain(ag_name)

        with allure_step_log("步骤4: P1 断言-权限组列表字段回读"):
            row_data = sfs_page.sfs_access_group_get_row_data(ag_name)
            assert row_data["名称"] == ag_name, (
                f"[FieldAssertion] 权限组名称 | 期望: {ag_name} | 实际: {row_data.get('名称')}"
            )
            assert row_data["描述"] == ag_desc, (
                f"[FieldAssertion] 权限组描述 | 期望: {ag_desc} | 实际: {row_data.get('描述')}"
            )
            assert row_data["挂载点数量"] == "0", (
                f"[FieldAssertion] 挂载点数量 | 期望: 0 | 实际: {row_data.get('挂载点数量')}"
            )

        # 将创建的权限组名称存入 instance_marker，供场景2使用
        pytest.instance_marker = ag_name

    @allure.title("文件存储-权限组删除")
    def test_sfs_access_group_delete(self, sfs_page, sfs_instance):
        """在 SFS 实例详情页权限组 Tab 中删除权限组并验证。

        包括：单个删除、批量删除、验证不可删除场景（默认权限组、挂载点>0）。
        """
        instance_name = sfs_instance["name"]
        logger.info(f"使用本用例创建的 SFS 实例: {instance_name}")

        ag_name_create = f"ag-del-{random_data()}"
        ag_name_batch1 = f"ag-batch1-{random_data()}"
        ag_name_batch2 = f"ag-batch2-{random_data()}"

        with allure_step_log("步骤1: 进入实例详情页权限组 Tab"):
            sfs_page.sfs_instance_goto_detail(instance_name)
            sfs_page.sfs_access_group_tab_click()

        # ---- 前置：创建3个用于后续删除验证的权限组 ----
        with allure_step_log("步骤2: 前置创建3个权限组用于删除验证"):
            for ag_name in [ag_name_create, ag_name_batch1, ag_name_batch2]:
                sfs_page.sfs_access_group_create(ag_name, f"测试权限组 {ag_name}")
                sfs_page.assert_popup_success("创建文件存储权限组成功")
                sfs_page.assert_list_contain(ag_name)

        # ---- 场景2-步骤2：删除单个权限组 ----
        with allure_step_log("步骤3: 删除单个权限组"):
            sfs_page.sfs_access_group_delete(ag_name_create)

        with allure_step_log("步骤4: P0 断言-验证单个权限组已删除"):
            sfs_page.assert_deleted(ag_name_create, timeout=60, refresh=True, refresh_interval=3)

        # ---- 场景2-步骤3：批量删除权限组 ----
        with allure_step_log("步骤5: 批量删除2个权限组"):
            sfs_page.sfs_access_group_batch_delete([ag_name_batch1, ag_name_batch2])

        with allure_step_log("步骤6: P0 断言-验证批量删除的权限组已不存在"):
            sfs_page.assert_deleted(ag_name_batch1, timeout=60, refresh=True, refresh_interval=3)
            sfs_page.assert_deleted(ag_name_batch2, timeout=60, refresh=True, refresh_interval=3)

        # ---- 场景2-步骤5：验证不可删除场景 ----
        with allure_step_log("步骤7: 验证默认权限组和挂载点>0的权限组不可删除"):
            # 获取当前权限组列表，找出默认权限组和挂载点>0的权限组
            column_data = sfs_page.get_column_data("名称")
            default_ag = None
            mounted_ag = None

            for name in column_data:
                row_data = sfs_page.sfs_access_group_get_row_data(name)
                mount_count = int(row_data.get("挂载点数量", "0") or "0")
                # 默认权限组：名称为 "Default NFS Access Group" 或 type 相关特征
                if "Default" in name or "default" in name.lower():
                    default_ag = name
                if mount_count > 0:
                    mounted_ag = name

            if default_ag:
                logger.info(f"找到默认权限组: {default_ag}")
                sfs_page.sfs_access_group_assert_delete_disabled(default_ag)
            else:
                logger.warning("未找到默认权限组，跳过默认权限组不可删除验证")

            if mounted_ag and mounted_ag != default_ag:
                logger.info(f"找到挂载点>0的权限组: {mounted_ag}")
                sfs_page.sfs_access_group_assert_delete_disabled(mounted_ag)
            elif mounted_ag == default_ag:
                logger.info(f"挂载点>0的权限组与默认权限组相同({mounted_ag})，已验证")
            else:
                logger.warning("未找到挂载点数量>0的权限组，跳过该验证")

        # ---- 清理：删除剩余的测试权限组（场景2步骤3批量删除后如有剩余）----
        with allure_step_log("步骤8: 清理测试数据"):
            # 重新获取列表，清理所有非默认且挂载点为0的测试权限组
            sfs_page.btn_refresh.click()
            sfs_page.wait_for_page_ready()
            column_data = sfs_page.get_column_data("名称")
            for name in column_data:
                if name.startswith("ag-"):
                    row_data = sfs_page.sfs_access_group_get_row_data(name)
                    mount_count = int(row_data.get("挂载点数量", "0") or "0")
                    if mount_count == 0:
                        sfs_page.sfs_access_group_delete(name)
                        sfs_page.assert_deleted(name, timeout=30, refresh=True, refresh_interval=3)
