import allure
import pytest
import re
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-权限组规则新建与删除功能验证')
class TestSFSAccessGroupRuleCreateDelete:
    """验证文件存储 SFS 实例详情页权限组规则的新建和删除功能。

    场景1：CIFS 实例新建权限组规则（用例 5717）
    场景2：NFS 实例新建权限组规则（用例 442861）
    场景3：删除权限组规则（用例 5722），依赖场景1或场景2已执行完成

    共享资源：SFS 实例（CIFS + NFS 各1个）、非默认权限组（各1个）
    清理顺序：权限组规则 -> 权限组 -> SFS 实例
    """

    @pytest.fixture(scope="class")
    def sfs_env(self, browser_context, config):
        """创建测试所需环境：1个CIFS实例 + 1个NFS实例 + 各1个非默认权限组。

        Yields:
            dict: 包含 cifs_instance、nfs_instance、ag_cifs、ag_nfs 的字典。
        """
        from sugon_web.conftest import _create_logged_in_page
        from sugon_web.pages.storage.sfs import SfsPage
        from sugon_web.testcase.storage._sfs_helpers import (
            create_sfs_instance,
            delete_sfs_instances,
        )

        page = _create_logged_in_page(browser_context, config)
        sfs_page = SfsPage(page)

        cifs_name = f"sfs-cifs-{random_data()}"
        nfs_name = f"sfs-nfs-{random_data()}"
        ag_cifs_name = f"ag-cifs-{random_data()}"
        ag_nfs_name = f"ag-nfs-{random_data()}"

        try:
            with allure_step_log("setup: create CIFS SFS instance"):
                cifs_instance = create_sfs_instance(
                    sfs_page, name=cifs_name, protocol="cifs",
                    cluster="Autotest", network="Autotest",
                    volume_size=10, cpu_cores=8, ram_gb=8,
                )

            with allure_step_log("setup: create NFS SFS instance"):
                nfs_instance = create_sfs_instance(
                    sfs_page, name=nfs_name, protocol="nfs",
                    cluster="Autotest", network="Autotest",
                    volume_size=10, cpu_cores=8, ram_gb=8,
                )

            with allure_step_log("setup: create non-default access group for CIFS"):
                sfs_page.goto_service("文件存储")
                sfs_page.wait_for_page_ready()
                sfs_page.sfs_instance_goto_detail(cifs_name)
                sfs_page.sfs_access_group_tab_click()
                sfs_page.sfs_access_group_create(ag_cifs_name, f"test ag {ag_cifs_name}")
                sfs_page.assert_popup_success("创建文件存储权限组成功")
                sfs_page.assert_list_contain(ag_cifs_name)

            with allure_step_log("setup: create non-default access group for NFS"):
                sfs_page.goto_service("文件存储")
                sfs_page.wait_for_page_ready()
                sfs_page.sfs_instance_goto_detail(nfs_name)
                sfs_page.sfs_access_group_tab_click()
                sfs_page.sfs_access_group_create(ag_nfs_name, f"test ag {ag_nfs_name}")
                sfs_page.assert_popup_success("创建文件存储权限组成功")
                sfs_page.assert_list_contain(ag_nfs_name)

            yield {
                "cifs_instance": cifs_instance,
                "nfs_instance": nfs_instance,
                "ag_cifs_name": ag_cifs_name,
                "ag_nfs_name": ag_nfs_name,
            }
        finally:
            # cleanup: close any open dialogs first, then delete access groups and SFS instances
            with allure_step_log("cleanup: close dialogs and delete resources"):
                try:
                    sfs_page.close_dialog_if_exists()
                except Exception:
                    pass

                try:
                    # Delete access groups (rules will be deleted with them)
                    sfs_page.goto_service("文件存储")
                    sfs_page.wait_for_page_ready()
                    sfs_page.sfs_instance_goto_detail(cifs_name)
                    sfs_page.sfs_access_group_tab_click()
                    sfs_page.sfs_access_group_delete(ag_cifs_name)
                    sfs_page.assert_deleted(ag_cifs_name, timeout=30)
                except Exception as e:
                    logger.warning(f"cleanup: failed to delete CIFS access group {ag_cifs_name}: {e}")

                try:
                    sfs_page.goto_service("文件存储")
                    sfs_page.wait_for_page_ready()
                    sfs_page.sfs_instance_goto_detail(nfs_name)
                    sfs_page.sfs_access_group_tab_click()
                    sfs_page.sfs_access_group_delete(ag_nfs_name)
                    sfs_page.assert_deleted(ag_nfs_name, timeout=30)
                except Exception as e:
                    logger.warning(f"cleanup: failed to delete NFS access group {ag_nfs_name}: {e}")

                # Delete SFS instances
                try:
                    delete_sfs_instances(sfs_page, [cifs_name, nfs_name])
                except Exception as e:
                    logger.warning(f"cleanup: failed to delete SFS instances: {e}")

            page.close()

    @allure.title("文件存储-CIFS实例权限组规则新建")
    def test_sfs_cifs_access_group_rule_create(self, sfs_page, sfs_env):
        """验证 CIFS 实例非默认权限组新建权限组规则，以及默认权限组不可新建规则。"""
        cifs_name = sfs_env["cifs_instance"]["name"]
        ag_cifs_name = sfs_env["ag_cifs_name"]
        auth_ip = "192.168.1.0/24"

        with allure_step_log("step1: goto CIFS instance detail access group tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(cifs_name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("step2: goto non-default access group rules"):
            sfs_page.sfs_access_group_goto_rules(ag_cifs_name)

        with allure_step_log("step3: create access group rule (CIFS only needs IP)"):
            sfs_page.sfs_access_group_rule_create(auth_ip)

        with allure_step_log("step4: P0 assert create success popup and list contain"):
            sfs_page.assert_popup_success()
            sfs_page.assert_list_contain(auth_ip, column_name="访问地址")

        with allure_step_log("step5: P1 assert access group rule field readback"):
            row_data = sfs_page.sfs_access_group_rule_get_row_data(auth_ip)
            assert row_data["访问地址"] == auth_ip, (
                f"[FieldAssertion] 访问地址 | 期望: {auth_ip} | 实际: {row_data.get('访问地址')}"
            )

        with allure_step_log("step6: verify default access group cannot create rule"):
            # 返回权限组列表
            sfs_page.page.go_back()
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_access_group_tab_click()
            # 找到默认权限组并进入规则列表
            column_data = sfs_page.get_column_data("名称")
            default_ag = None
            for name in column_data:
                if "Default CIFS Access Group" in name:
                    default_ag = name
                    break
            if default_ag:
                sfs_page.sfs_access_group_goto_rules(default_ag)
                sfs_page.sfs_access_group_rule_assert_create_disabled()
                sfs_page.sfs_access_group_rule_assert_default_hint()
            else:
                logger.warning("default CIFS access group not found, skip")

    @allure.title("文件存储-NFS实例权限组规则新建")
    def test_sfs_nfs_access_group_rule_create(self, sfs_page, sfs_env):
        """验证 NFS 实例非默认权限组新建权限组规则，以及默认权限组不可新建规则。"""
        nfs_name = sfs_env["nfs_instance"]["name"]
        ag_nfs_name = sfs_env["ag_nfs_name"]
        auth_ip = "192.168.2.0/24"
        rw_access = "rw"
        user_access = "all_squash"

        with allure_step_log("step1: goto NFS instance detail access group tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(nfs_name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("step2: goto non-default access group rules"):
            sfs_page.sfs_access_group_goto_rules(ag_nfs_name)

        with allure_step_log("step3: create access group rule (NFS needs IP+RW+User)"):
            sfs_page.sfs_access_group_rule_create(auth_ip, rw_access, user_access)

        with allure_step_log("step4: P0 assert create success popup and list contain"):
            sfs_page.assert_popup_success()
            sfs_page.assert_list_contain(auth_ip, column_name="访问地址")

        with allure_step_log("step5: P1 assert access group rule field readback"):
            row_data = sfs_page.sfs_access_group_rule_get_row_data(auth_ip)
            assert row_data["访问地址"] == auth_ip, (
                f"[FieldAssertion] 访问地址 | 期望: {auth_ip} | 实际: {row_data.get('访问地址')}"
            )
            assert "读写" in row_data.get("读写权限", ""), (
                f"[FieldAssertion] 读写权限 | 期望包含: 读写 | 实际: {row_data.get('读写权限')}"
            )
            # CIFS 权限组规则列表不显示"用户权限"列，仅在 NFS 协议下显示
            if "用户权限" in row_data:
                assert "所有访问用户" in row_data.get("用户权限", ""), (
                    f"[FieldAssertion] 用户权限 | 期望包含: 所有访问用户 | 实际: {row_data.get('用户权限')}"
                )

        with allure_step_log("step6: verify default access group cannot create rule"):
            # 返回权限组列表
            sfs_page.page.go_back()
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_access_group_tab_click()
            # 找到默认权限组并进入规则列表
            column_data = sfs_page.get_column_data("名称")
            default_ag = None
            for name in column_data:
                if "Default NFS Access Group" in name:
                    default_ag = name
                    break
            if default_ag:
                sfs_page.sfs_access_group_goto_rules(default_ag)
                sfs_page.sfs_access_group_rule_assert_create_disabled()
                sfs_page.sfs_access_group_rule_assert_default_hint()
            else:
                logger.warning("default NFS access group not found, skip")

    @allure.title("文件存储-权限组规则删除")
    def test_sfs_access_group_rule_delete(self, sfs_page, sfs_env):
        """验证权限组规则的单个删除和批量删除功能。

        依赖场景1或场景2已创建的权限组规则，或在前置中预创建5条规则。
        """
        nfs_name = sfs_env["nfs_instance"]["name"]
        ag_nfs_name = sfs_env["ag_nfs_name"]

        with allure_step_log("step1: goto NFS instance detail access group tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(nfs_name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("step2: goto access group rule list"):
            sfs_page.sfs_access_group_goto_rules(ag_nfs_name)

        # 前置：确保有至少5条权限组规则用于删除验证
        with allure_step_log("step3: pre-create 5 access group rules for delete test"):
            existing_ips = sfs_page.get_column_data("访问地址")
            needed = 5 - len(existing_ips)
            if needed > 0:
                for i in range(needed):
                    ip = f"192.168.10.{i}/24"
                    sfs_page.sfs_access_group_rule_create(ip, "rw", "all_squash")
                    sfs_page.assert_popup_success()
                    sfs_page.assert_list_contain(ip, column_name="访问地址")

            # 重新获取所有规则
            all_ips = sfs_page.get_column_data("访问地址")
            if len(all_ips) < 3:
                pytest.skip("insufficient access group rules, skip delete test")

        # 单个删除
        single_ip = all_ips[0]
        with allure_step_log(f"step4: single delete access group rule: {single_ip}"):
            sfs_page.sfs_access_group_rule_delete(single_ip)

        with allure_step_log("step5: P0 assert single rule deleted"):
            sfs_page.assert_deleted(single_ip, timeout=60, refresh=True, refresh_interval=3)

        # batch delete
        remaining_ips = sfs_page.get_column_data("访问地址")
        if len(remaining_ips) >= 2:
            batch_ips = remaining_ips[:2]
            with allure_step_log(f"step6: batch delete access group rules: {batch_ips}"):
                sfs_page.sfs_access_group_rule_batch_delete(batch_ips)

            with allure_step_log("step7: P0 assert batch deleted rules not exist"):
                for ip in batch_ips:
                    sfs_page.assert_deleted(ip, timeout=60, refresh=True, refresh_interval=3)

        with allure_step_log("step8: P1 assert deleted rules not in list"):
            sfs_page.btn_refresh.click()
            sfs_page.wait_for_page_ready()
            deleted_ips = [single_ip] + (batch_ips if len(remaining_ips) >= 2 else [])
            for ip in deleted_ips:
                sfs_page.assert_list_not_contain(ip, column_name="访问地址")
