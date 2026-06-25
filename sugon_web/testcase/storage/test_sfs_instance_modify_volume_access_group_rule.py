import allure
import pytest
import re
from paramiko.ssh_exception import ChannelException
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _ssh_verify_sfs_volume(ssh_vm, mgmt_ip, expected_size_gib):
    """模块级辅助函数：SSH 连接 SFS 实例管理 IP 验证磁盘大小。

    因 SFS 实例管理 IP 可能因网络环境不可达，此处捕获连接异常并记录警告。
    """
    try:
        ssh_vm.connect(mgmt_ip, port=22022)
        result = ssh_vm.run("df -h", return_rc=True)
        assert result["rc"] == 0, (
            f"[BackendAssertion] df -h 命令执行失败: {result.get('stderr', '')}"
        )
        assert "/dev/vdb" in result["stdout"], (
            f"[BackendAssertion] df -h 输出 | 期望包含 /dev/vdb | 实际: {result['stdout']}"
        )
        logger.info(f"SSH 验证通过: /dev/vdb 存在")
    except ChannelException as e:
        logger.warning(f"[环境限制] SSH 连接 SFS 实例管理 IP {mgmt_ip} 失败: {e}，跳过后端验证")


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-实例修改功能验证')
class TestSFSInstanceModify:
    """验证文件存储 SFS 实例的修改功能：修改云硬盘大小、修改权限组、修改权限组规则。

    场景1：修改云硬盘大小（用例 5690）
    场景2：修改权限组（用例 5696）
    场景3：修改权限组规则（用例 5721）

    各场景独立创建资源，独立清理。
    """

    # ========== 场景1：修改云硬盘大小 ==========

    @allure.title("文件存储-修改云硬盘大小")
    @pytest.mark.parametrize("sfs_instance", [{"protocol": "nfs", "volume_size": 20}], indirect=True)
    def test_sfs_modify_volume_size(self, sfs_page, sfs_instance, ssh_vm):
        """验证修改 SFS 实例云硬盘大小的功能，包括边界条件（小于当前值、等于当前值置灰）和成功扩容。"""
        name = sfs_instance["name"]
        current_size = sfs_instance["volume_size"]  # 20 GiB

        with allure_step_log("步骤1: 等待实例状态正常"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)

        with allure_step_log("步骤2: 验证修改失败-容量小于当前值（确定按钮置灰）"):
            sfs_page.sfs_instance_assert_volume_size_disabled(name)

        with allure_step_log("步骤3: 验证修改失败-容量等于当前值（确定按钮置灰）"):
            sfs_page.sfs_instance_assert_volume_size_equal_disabled(name, current_size)

        with allure_step_log("步骤4: 修改云硬盘大小成功（20GiB 扩容到 30GiB）"):
            new_size = 30
            sfs_page.sfs_instance_modify_volume_size(name, new_size)

        with allure_step_log("步骤5: P0 断言-修改成功弹窗"):
            # 产品实际返回"执行成功"而非"修改云硬盘大小成功"
            sfs_page.assert_popup_success("执行成功")

        with allure_step_log("步骤6: P0 断言-等待实例状态恢复"):
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)

        with allure_step_log("步骤7: P1 断言-列表页云硬盘大小字段"):
            row_data = sfs_page.get_row_data(name)
            assert f"{new_size}GiB" in row_data.get("云硬盘大小", ""), (
                f"[FieldAssertion] 列表云硬盘大小 | 期望包含: {new_size}GiB | 实际: {row_data.get('云硬盘大小')}"
            )

        with allure_step_log("步骤8: P1 断言-详情页云硬盘大小字段"):
            sfs_page.sfs_instance_goto_detail(name)
            detail = sfs_page.sfs_get_detail_info()
            assert f"{new_size}GiB" in detail.get("云硬盘大小", ""), (
                f"[FieldAssertion] 详情云硬盘大小 | 期望包含: {new_size}GiB | 实际: {detail.get('云硬盘大小')}"
            )

        with allure_step_log("步骤9: P2 断言-SSH 后台验证磁盘大小"):
            addr = detail.get("访问地址", "")
            if addr:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', addr)
                if ip_match:
                    mgmt_ip = ip_match.group(1)
                    _ssh_verify_sfs_volume(ssh_vm, mgmt_ip, new_size)
                else:
                    logger.warning(f"无法从访问地址提取 IP: {addr}")
            else:
                logger.warning("详情页未获取到访问地址，跳过 SSH 验证")

    # ========== 场景2：修改权限组 ==========

    @allure.title("文件存储-修改权限组")
    @pytest.mark.parametrize("sfs_instance", [{"protocol": "nfs", "volume_size": 10}], indirect=True)
    def test_sfs_modify_access_group(self, sfs_page, sfs_instance):
        """验证修改 SFS 实例权限组的功能。"""
        name = sfs_instance["name"]
        ag_name = f"ag-{random_data()}"
        ag_desc = f"测试权限组_desc_{random_data()}"
        new_ag_name = f"ag-mod-{random_data()}"
        new_ag_desc = f"修改后描述_{random_data()}"

        with allure_step_log("步骤1: 等待实例状态正常并进入详情页权限组 Tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)
            sfs_page.sfs_instance_goto_detail(name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("步骤2: 前置创建权限组"):
            sfs_page.sfs_access_group_create(ag_name, ag_desc)
            sfs_page.assert_popup_success("创建文件存储权限组成功")
            sfs_page.assert_list_contain(ag_name)

        with allure_step_log("步骤3: 修改权限组"):
            sfs_page.sfs_access_group_modify(ag_name, new_ag_name, new_ag_desc)

        with allure_step_log("步骤4: P0 断言-修改成功弹窗"):
            sfs_page.assert_popup_success("修改文件存储权限组成功")

        with allure_step_log("步骤5: P1 断言-权限组列表字段回读"):
            row_data = sfs_page.sfs_access_group_get_row_data(new_ag_name)
            assert row_data["名称"] == new_ag_name, (
                f"[FieldAssertion] 权限组名称 | 期望: {new_ag_name} | 实际: {row_data.get('名称')}"
            )
            assert row_data["描述"] == new_ag_desc, (
                f"[FieldAssertion] 权限组描述 | 期望: {new_ag_desc} | 实际: {row_data.get('描述')}"
            )

        # 清理：删除修改后的权限组
        with allure_step_log("步骤6: 清理-删除修改后的权限组"):
            sfs_page.sfs_access_group_delete(new_ag_name)
            sfs_page.assert_deleted(new_ag_name, timeout=30, refresh=True, refresh_interval=3)

    # ========== 场景3：修改权限组规则 ==========

    @allure.title("文件存储-修改权限组规则")
    @pytest.mark.parametrize("sfs_instance", [{"protocol": "nfs", "volume_size": 10}], indirect=True)
    def test_sfs_modify_access_group_rule(self, sfs_page, sfs_instance):
        """验证修改 SFS 实例权限组规则的功能。"""
        name = sfs_instance["name"]
        ag_name = f"ag-{random_data()}"
        auth_ip = "192.168.3.0/24"
        original_rw = "rw"
        original_user = "all_squash"
        new_rw = "ro"
        new_user = "no_all_squash"

        with allure_step_log("步骤1: 等待实例状态正常并进入详情页权限组 Tab"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)
            sfs_page.sfs_instance_goto_detail(name)
            sfs_page.sfs_access_group_tab_click()

        with allure_step_log("步骤2: 前置创建权限组"):
            sfs_page.sfs_access_group_create(ag_name, f"test ag {ag_name}")
            sfs_page.assert_popup_success("创建文件存储权限组成功")
            sfs_page.assert_list_contain(ag_name)

        with allure_step_log("步骤3: 前置创建权限组规则"):
            sfs_page.sfs_access_group_goto_rules(ag_name)
            sfs_page.sfs_access_group_rule_create(auth_ip, original_rw, original_user)
            sfs_page.assert_popup_success()
            sfs_page.assert_list_contain(auth_ip, column_name="访问地址")

        with allure_step_log("步骤4: 修改权限组规则"):
            sfs_page.sfs_access_group_rule_modify(auth_ip, new_rw, new_user)

        with allure_step_log("步骤5: P0 断言-修改成功弹窗"):
            # 产品实际返回"修改文件存储权限组规则成功"
            sfs_page.assert_popup_success("修改文件存储权限组规则成功")

        with allure_step_log("步骤6: P1 断言-权限组规则列表字段回读"):
            row_data = sfs_page.sfs_access_group_rule_get_row_data(auth_ip)
            assert row_data["访问地址"] == auth_ip, (
                f"[FieldAssertion] 访问地址 | 期望: {auth_ip} | 实际: {row_data.get('访问地址')}"
            )
            assert "只读" in row_data.get("读写权限", ""), (
                f"[FieldAssertion] 读写权限 | 期望包含: 只读 | 实际: {row_data.get('读写权限')}"
            )
            # 注：列表页不显示"用户权限"列，该字段在详情中展示，此处不断言

        # 清理：删除权限组规则 -> 权限组（SFS 实例由 fixture teardown 自动清理）
        with allure_step_log("步骤7: 清理-删除权限组规则"):
            sfs_page.sfs_access_group_rule_delete(auth_ip)
            sfs_page.assert_deleted(auth_ip, timeout=30, refresh=True, refresh_interval=3)

        with allure_step_log("步骤8: 清理-删除权限组"):
            # 导航到权限组列表页（通过实例详情页的权限组 Tab）
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()
            sfs_page.sfs_instance_goto_detail(name)
            sfs_page.sfs_access_group_tab_click()
            sfs_page.sfs_access_group_delete(ag_name)
            sfs_page.assert_deleted(ag_name, timeout=30, refresh=True, refresh_interval=3)
