import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.framework.decorators import only_stor


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('xbd存储池-规格升级基本功能验证')
class TestUsmSpecUpgrade:

    @allure.title("USM-xbd存储池-规格升级验证")
    @only_stor("xbd")
    def test_usm_spec_upgrade(self, usm_instance, usm_page, ssh_host):
        """xbd 存储池环境下，通过 fixture 获取共享 USM 实例执行规格升级，
        验证升级前后规格信息变化，并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""

        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪")

        with allure_step_log("步骤1: 获取当前规格信息"):
            row_data = usm_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("服务器", "")
            logger.info(f"USM 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 USM 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级操作"):
            selected_spec = usm_page.usm_spec_upgrade(name)
            logger.info(
                f"USM 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成，验证状态与规格变更"):
            usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=600)
            # 回读列表页，确认规格已变更
            usm_page.goto_list_page()
            row_data_after = usm_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"USM 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 USM 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = usm_page.usm_get_server_id(name)
            assert server_id, f"未提取到 USM 实例 {name} 的 server_id"
            usm_page.goto_list_page()

        with allure_step_log("步骤5: SSH 连接环境后台，验证规格信息"):
            cmd = f"scli guest show {server_id}"
            output = ssh_host.run(cmd, check_rc=True)
            logger.info(f"SSH 执行 {cmd} 输出:\n{output}")

            # 从输出中解析 vcpu 和 memory_mb
            # scli guest show 输出为 Unicode 表格格式（含框线字符），用 \D+ 跳过非数字分隔符
            import re
            vcpu_match = re.search(r"vcpu[s]?\D+(\d+)", output, re.IGNORECASE)
            mem_match = re.search(r"memory_mb\D+(\d+)", output, re.IGNORECASE)

            actual_vcpu = int(vcpu_match.group(1)) if vcpu_match else None
            actual_mem_mb = int(mem_match.group(1)) if mem_match else None
            logger.info(f"scli 解析结果: vcpus={actual_vcpu}, memory_mb={actual_mem_mb}")

            # 验证 vcpu
            expected_vcpu = selected_spec["vcpus"]
            assert actual_vcpu is not None, \
                f"scli guest show 输出未找到 vcpu 字段, 输出前500字符: {output[:500]}"
            assert actual_vcpu == expected_vcpu, \
                f"vcpu 不匹配: scli返回={actual_vcpu}, 期望={expected_vcpu}"
            logger.info(f"vcpu 验证通过: {actual_vcpu}核")

            # 验证 memory_mb
            expected_mem_mb = selected_spec["memory_mb"]
            assert actual_mem_mb is not None, \
                f"scli guest show 输出未找到 memory_mb 字段, 输出前500字符: {output[:500]}"
            assert actual_mem_mb == expected_mem_mb, \
                f"memory_mb 不匹配: scli返回={actual_mem_mb}, 期望={expected_mem_mb}"
            logger.info(f"memory_mb 验证通过: {actual_mem_mb}MB")

        # fixture usm_instance 会在 session 结束时自动清理
        logger.info(f"规格升级完成，实例 {name} 由 fixture 自动清理")
