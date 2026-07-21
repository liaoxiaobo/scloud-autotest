import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.testcase.storage._sfs_helpers import (
    create_sfs_instance,
    delete_sfs_instances,
)


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-实例详情-挂载点新建与删除功能验证')
class TestSFSMountpointCreateDelete:
    """验证文件存储 SFS 实例详情页挂载点的新建和删除功能。

    场景1：NFS 实例新建挂载点（用例 5704）
    场景2：CIFS 实例新建挂载点（用例 5706）

    共享资源：SFS 实例（NFS + CIFS 各1个）、非默认权限组（各1个）
    清理顺序：删除挂载点 -> 删除权限组 -> 删除 SFS 实例
    """

    @pytest.fixture(scope="class")
    def sfs_mount_env(self, browser_context, config):
        """准备测试所需环境：新建1个NFS实例 + 1个CIFS实例 + 各1个非默认权限组。

        每个测试类独立创建专属实例，避免并行执行时资源竞争（其他测试的 teardown 删除共享实例）。
        清理时删除本 fixture 创建的全部资源（SFS实例、权限组、挂载点）。

        Yields:
            dict: 包含 nfs_name、cifs_name、ag_nfs_name、ag_cifs_name 的字典。
        """
        from sugon_web.conftest import _create_logged_in_page
        from sugon_web.pages.storage.sfs import SfsPage

        page = _create_logged_in_page(browser_context, config)
        sfs_page = SfsPage(page)

        created_instances = []
        ag_nfs_name = f"ag-nfs-{random_data()}"
        ag_cifs_name = f"ag-cifs-{random_data()}"

        nfs_name = None
        cifs_name = None

        try:
            with allure_step_log("setup: create dedicated NFS SFS instance"):
                nfs_name = f"sfs-mount-nfs-{random_data()}"
                logger.info(f"创建专属 NFS 实例: {nfs_name}")
                create_sfs_instance(
                    sfs_page, name=nfs_name, protocol="nfs",
                    cluster="Autotest", network="Autotest", subnet="Autotest(10",
                    volume_size=10, cpu_cores=8, ram_gb=8,
                )
                created_instances.append(nfs_name)

            with allure_step_log("setup: create dedicated CIFS SFS instance"):
                cifs_name = f"sfs-mount-cifs-{random_data()}"
                logger.info(f"创建专属 CIFS 实例: {cifs_name}")
                create_sfs_instance(
                    sfs_page, name=cifs_name, protocol="cifs",
                    cluster="Autotest", network="Autotest", subnet="Autotest(10",
                    volume_size=10, cpu_cores=8, ram_gb=8,
                )
                created_instances.append(cifs_name)

            with allure_step_log("setup: create non-default access group for NFS"):
                sfs_page.goto_service("文件存储")
                sfs_page.wait_for_page_ready()
                sfs_page.sfs_instance_goto_detail(nfs_name)
                sfs_page.sfs_access_group_tab_click()
                sfs_page.sfs_access_group_create(ag_nfs_name, f"test ag {ag_nfs_name}")
                sfs_page.assert_popup_success("创建文件存储权限组成功")
                sfs_page.assert_list_contain(ag_nfs_name)

            with allure_step_log("setup: create non-default access group for CIFS"):
                sfs_page.goto_service("文件存储")
                sfs_page.wait_for_page_ready()
                sfs_page.sfs_instance_goto_detail(cifs_name)
                sfs_page.sfs_access_group_tab_click()
                sfs_page.sfs_access_group_create(ag_cifs_name, f"test ag {ag_cifs_name}")
                sfs_page.assert_popup_success("创建文件存储权限组成功")
                sfs_page.assert_list_contain(ag_cifs_name)

            yield {
                "nfs_name": nfs_name,
                "cifs_name": cifs_name,
                "ag_nfs_name": ag_nfs_name,
                "ag_cifs_name": ag_cifs_name,
            }
        except Exception as e:
            logger.error(f"setup failed: {e}")
            raise
        finally:
            with allure_step_log("cleanup: delete mountpoints"):
                try:
                    sfs_page.close_dialog_if_exists()
                except Exception:
                    pass

                def _cleanup_mountpoints(instance_name, desc_keyword):
                    """删除指定实例上描述匹配的本测试创建的挂载点。"""
                    sfs_page.goto_service("文件存储")
                    sfs_page.wait_for_page_ready()
                    sfs_page.sfs_instance_goto_detail(instance_name)
                    sfs_page.sfs_mountpoint_tab_click()
                    ids = sfs_page.sfs_mountpoint_get_column_data("挂载点ID")
                    descs = sfs_page.sfs_mountpoint_get_column_data("描述")
                    target_ids = [
                        mid for mid, d in zip(ids, descs)
                        if d.strip() == desc_keyword and mid.strip()
                    ]
                    if not target_ids:
                        logger.info(f"cleanup: no mountpoints to delete for {instance_name}")
                        return
                    sfs_page.sfs_mountpoint_batch_delete(target_ids)
                    sfs_page.assert_deleted(target_ids, timeout=60, refresh=True, refresh_interval=3)
                    logger.info(f"cleanup: deleted mountpoints for {instance_name}: {target_ids}")

                if nfs_name:
                    try:
                        _cleanup_mountpoints(nfs_name, "NFS测试验证")
                    except Exception as e:
                        logger.warning(f"cleanup: failed to delete NFS mountpoints: {e}")

                if cifs_name:
                    try:
                        _cleanup_mountpoints(cifs_name, "CIFS测试验证")
                    except Exception as e:
                        logger.warning(f"cleanup: failed to delete CIFS mountpoints: {e}")

            with allure_step_log("cleanup: delete access groups"):
                if nfs_name:
                    try:
                        sfs_page.goto_service("文件存储")
                        sfs_page.wait_for_page_ready()
                        sfs_page.sfs_instance_goto_detail(nfs_name)
                        sfs_page.sfs_access_group_tab_click()
                        sfs_page.sfs_access_group_delete(ag_nfs_name)
                        sfs_page.assert_deleted(ag_nfs_name, timeout=30)
                    except Exception as e:
                        logger.warning(f"cleanup: failed to delete NFS access group {ag_nfs_name}: {e}")

                if cifs_name:
                    try:
                        sfs_page.goto_service("文件存储")
                        sfs_page.wait_for_page_ready()
                        sfs_page.sfs_instance_goto_detail(cifs_name)
                        sfs_page.sfs_access_group_tab_click()
                        sfs_page.sfs_access_group_delete(ag_cifs_name)
                        sfs_page.assert_deleted(ag_cifs_name, timeout=30)
                    except Exception as e:
                        logger.warning(f"cleanup: failed to delete CIFS access group {ag_cifs_name}: {e}")

            # 删除本 fixture 创建的全部 SFS 实例
            if created_instances:
                with allure_step_log(f"cleanup: delete created SFS instances {created_instances}"):
                    try:
                        delete_sfs_instances(sfs_page, created_instances)
                    except Exception as e:
                        logger.warning(f"cleanup: failed to delete created SFS instances {created_instances}: {e}")

            page.close()

    @allure.title("文件存储-NFS实例挂载点新建")
    def test_sfs_nfs_mountpoint_create(self, sfs_page, sfs_mount_env):
        """验证 NFS 实例挂载点新建功能：默认权限组和非默认权限组各创建一个挂载点，
        验证挂载点列表数据一致性。
        """
        nfs_name = sfs_mount_env["nfs_name"]
        ag_nfs_name = sfs_mount_env["ag_nfs_name"]
        desc = "NFS测试验证"

        with allure_step_log("步骤1: 进入 NFS 实例详情页挂载点 Tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(nfs_name)
            sfs_page.sfs_mountpoint_tab_click()

        with allure_step_log("步骤2: 新建挂载点（默认权限组）"):
            # 默认权限组名称格式为 "Default NFS Access Group"
            # 挂载点列表没有"名称"列，用"权限组名称"列获取默认权限组
            column_data = sfs_page.sfs_mountpoint_get_column_data("权限组名称")
            default_ag = None
            for ag_name in column_data:
                if "Default" in ag_name and "NFS" in ag_name:
                    default_ag = ag_name
                    break
            if not default_ag:
                default_ag = "Default NFS Access Group"
            sfs_page.sfs_mountpoint_create(default_ag, desc)

        with allure_step_log("步骤3: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("执行成功")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤4: 新建挂载点（非默认权限组）"):
            sfs_page.sfs_mountpoint_create(ag_nfs_name, desc)

        with allure_step_log("步骤5: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("执行成功")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤6: P1 断言-挂载点列表数据一致性"):
            mount_paths = sfs_page.sfs_mountpoint_get_column_data("挂载点路径")
            assert len(mount_paths) >= 2, (
                f"[ListAssertion] 挂载点数量 | 期望: >=2 | 实际: {len(mount_paths)}"
            )
            group_names = sfs_page.sfs_mountpoint_get_column_data("权限组名称")
            assert default_ag in group_names, (
                f"[FieldAssertion] 默认权限组挂载点 | 期望包含: {default_ag} | 实际: {group_names}"
            )
            assert ag_nfs_name in group_names, (
                f"[FieldAssertion] 非默认权限组挂载点 | 期望包含: {ag_nfs_name} | 实际: {group_names}"
            )
            descriptions = sfs_page.sfs_mountpoint_get_column_data("描述")
            assert desc in descriptions, (
                f"[FieldAssertion] 挂载点描述 | 期望包含: {desc} | 实际: {descriptions}"
            )

    @allure.title("文件存储-CIFS实例挂载点新建")
    def test_sfs_cifs_mountpoint_create(self, sfs_page, sfs_mount_env):
        """验证 CIFS 实例挂载点新建功能：默认权限组和非默认权限组各创建一个挂载点，
        验证挂载点列表数据一致性。
        """
        cifs_name = sfs_mount_env["cifs_name"]
        ag_cifs_name = sfs_mount_env["ag_cifs_name"]
        desc = "CIFS测试验证"

        with allure_step_log("步骤1: 进入 CIFS 实例详情页挂载点 Tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(cifs_name)
            sfs_page.sfs_mountpoint_tab_click()

        with allure_step_log("步骤2: 新建挂载点（默认权限组）"):
            # 默认权限组名称格式为 "Default CIFS Access Group"
            # 挂载点列表没有"名称"列，用"权限组名称"列获取默认权限组
            column_data = sfs_page.sfs_mountpoint_get_column_data("权限组名称")
            default_ag = None
            for ag_name in column_data:
                if "Default" in ag_name and "CIFS" in ag_name:
                    default_ag = ag_name
                    break
            if not default_ag:
                default_ag = "Default CIFS Access Group"
            sfs_page.sfs_mountpoint_create(default_ag, desc)

        with allure_step_log("步骤3: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("执行成功")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤4: 新建挂载点（非默认权限组）"):
            sfs_page.sfs_mountpoint_create(ag_cifs_name, desc)

        with allure_step_log("步骤5: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("执行成功")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤6: P1 断言-挂载点列表数据一致性"):
            mount_paths = sfs_page.sfs_mountpoint_get_column_data("挂载点路径")
            assert len(mount_paths) >= 2, (
                f"[ListAssertion] 挂载点数量 | 期望: >=2 | 实际: {len(mount_paths)}"
            )
            group_names = sfs_page.sfs_mountpoint_get_column_data("权限组名称")
            assert default_ag in group_names, (
                f"[FieldAssertion] 默认权限组挂载点 | 期望包含: {default_ag} | 实际: {group_names}"
            )
            assert ag_cifs_name in group_names, (
                f"[FieldAssertion] 非默认权限组挂载点 | 期望包含: {ag_cifs_name} | 实际: {group_names}"
            )
            descriptions = sfs_page.sfs_mountpoint_get_column_data("描述")
            assert desc in descriptions, (
                f"[FieldAssertion] 挂载点描述 | 期望包含: {desc} | 实际: {descriptions}"
            )
