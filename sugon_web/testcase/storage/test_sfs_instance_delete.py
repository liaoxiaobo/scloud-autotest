import allure
import pytest
from sugon_web.utils.logger import allure_step_log


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-实例删除功能验证')
class TestSFSInstanceDelete:
    """验证文件存储 SFS 实例的删除功能，覆盖单一删除和批量删除两个场景。"""

    @allure.title("文件存储-删除单一实例")
    @pytest.mark.parametrize("sfs_instance", [{"count": 1, "protocol": "nfs"}], indirect=True)
    def test_sfs_delete_single(self, sfs_page, sfs_instance, ssh_host):
        """场景1：创建单个 SFS 实例，然后通过操作栏删除，验证 UI 和后台状态。"""
        name = sfs_instance["name"]

        with allure_step_log("步骤1: 执行删除操作"):
            sfs_page.sfs_instance_delete(name)

        with allure_step_log("步骤2: UI 断言-验证实例已不在列表中"):
            sfs_page.assert_deleted(name, timeout=60, refresh=True, refresh_interval=3)

        with allure_step_log("步骤3: 后台环境验证-通过 CLI 轮询确认实例已删除"):
            from sugon_web.testcase.storage._sfs_helpers import wait_for_sfs_instance_deleted
            wait_for_sfs_instance_deleted(ssh_host, name)

    @allure.title("文件存储-批量删除实例")
    @pytest.mark.parametrize(
        "sfs_instance",
        [{"count": 2, "protocol": ["nfs", "cifs"]}],
        indirect=True,
    )
    def test_sfs_delete_batch(self, sfs_page, sfs_instance, ssh_host):
        """场景2：创建两个 SFS 实例，通过列表复选框批量删除，验证 UI 和后台状态。"""
        names = [item["name"] for item in sfs_instance]

        with allure_step_log("步骤1: 勾选两个实例并执行批量删除"):
            sfs_page.sfs_instance_batch_delete(names)

        with allure_step_log("步骤2: UI 断言-验证两个实例均不在列表中"):
            sfs_page.assert_deleted(names, timeout=60, refresh=True, refresh_interval=3)

        with allure_step_log("步骤3: 后台环境验证-通过 CLI 轮询确认两个实例均已删除"):
            from sugon_web.testcase.storage._sfs_helpers import wait_for_sfs_instance_deleted
            for name in names:
                wait_for_sfs_instance_deleted(ssh_host, name)
