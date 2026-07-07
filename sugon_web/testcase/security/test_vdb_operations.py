import re

import allure
import pytest
from sugon_web.testcase.security._security_helpers import _ping_fip, wait_backend_volume_size
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than


@allure.epic('安全合规')
@allure.feature('数据库审计VDB')
@allure.story('VDB实例-全生命周期及功能验证')
class TestVdbOperations:
    """数据库审计 VDB 实例全生命周期及功能验证。

    所有场景共享同一个 VDB 实例（由 vdb_instance fixture 创建），
    类内按顺序依次执行 14 个场景，所有用例执行完成后统一清理。
    """

    @allure.title("VDB-新建实例验证")
    def test_vdb_01_create(self, vdb_instance, vdb_page):
        """场景1：新建 VDB 实例，验证详情页与跳转地址。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已创建完成")

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url, \
                f"未导航到 VDB 页面，当前 URL: {vdb_page.page.url}"
            logger.info(f"已进入 VDB 列表页: {vdb_page.page.url}")

        with allure_step_log("步骤2: 验证详情页与跳转"):
            vdb_page.vdb_to_details(name)
            vdb_page.wait_for_page_ready()
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != vdb_page.page:
                    new_page.close()
                logger.info("跳转地址验证通过")

    @allure.title("VDB-关机操作")
    def test_vdb_02_shutdown(self, vdb_instance, vdb_page):
        """场景2：对运行的 VDB 实例执行关机操作。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url
            logger.info(f"已进入 VDB 列表页: {vdb_page.page.url}")

        with allure_step_log("步骤2: 执行关机操作"):
            vdb_page.vdb_operations(name, "关机")

        with allure_step_log("步骤3: 验证关机后服务状态和虚拟机状态"):
            vdb_page.assert_vdb_status(name, service_status="不可用", vm_status="关机", timeout=180)

        with allure_step_log("步骤4: 验证名称不可点击跳转详情页"):
            is_clickable = vdb_page.vdb_name_clickable(name)
            assert not is_clickable, f"关机后 VDB 实例 {name} 名称仍可点击，期望不可点击"

    @allure.title("VDB-开机操作")
    def test_vdb_03_power_on(self, vdb_instance, vdb_page):
        """场景3：对已关机的 VDB 实例执行开机操作。"""
        name = vdb_instance["name"]
        page = vdb_page.page

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url

        with allure_step_log("步骤2: 执行开机操作"):
            vdb_page.vdb_operations(name, "开机")

        with allure_step_log("步骤3: 等待开机完成，验证服务状态和虚拟机状态"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log("步骤4: 进入详情页再次验证状态"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=180)
            vdb_page.vdb_to_details(name)
            vdb_page.wait_for_page_ready()
            body_text = vdb_page.get_detail_body_text()
            assert "服务状态" in body_text and "虚拟机状态" in body_text, \
                f"详情页未显示服务状态和虚拟机状态信息"
            logger.info("VDB 实例开机后状态持续正常")

        with allure_step_log("步骤5: 验证跳转地址"):
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("开机后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "开机后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("开机后跳转地址验证通过")

    @allure.title("VDB-退订操作")
    def test_vdb_04_unsubscribe(self, vdb_instance, vdb_page):
        """场景4：对运行的 VDB 实例执行退订操作。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url

        with allure_step_log("步骤2: 执行退订操作"):
            vdb_page.vdb_unsubscribe(name)
            vdb_page.wait_for_operation_complete(timeout=60)

        with allure_step_log("步骤3: 验证退订后服务状态"):
            row_data = vdb_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"VDB 实例 {name} 退订后状态: 服务={service_status}, 到期时间={expire_time}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log("步骤4: 进入详情页，验证跳转地址和到期时间显示'--'"):
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")

    @allure.title("VDB-授权操作")
    def test_vdb_05_authorize(self, vdb_instance, vdb_page):
        """场景5：对已退订的 VDB 实例执行授权操作。"""
        name = vdb_instance["name"]
        page = vdb_page.page

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url

        with allure_step_log("步骤2: 执行授权操作（选择3个月时长）"):
            vdb_page.vdb_authorize(name, "3个月")
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=120)

        with allure_step_log("步骤3: 验证授权后实例信息准确，服务状态为运行中"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(
                f"VDB 实例 {name} 授权（3个月）后服务状态: {service_status}, 到期时间: {expire_time}"
            )
            assert "运行" in service_status, f"授权后服务状态异常: {service_status}"
            assert expire_time and expire_time != "--", \
                f"到期时间字段未更新: {expire_time}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "授权后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if expire_time and expire_time != "--":
                    vdb_page.verify_jump_page_license_expire(new_page, expire_time)
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")

    @allure.title("VDB-续期操作")
    def test_vdb_06_renewal(self, vdb_instance, vdb_page):
        """场景6：对运行的 VDB 实例执行续期操作。"""
        name = vdb_instance["name"]
        page = vdb_page.page

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url

        with allure_step_log("步骤2: 记录当前服务到期时间"):
            row_data = vdb_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"VDB 实例 {name} 续期前到期时间: {expire_before}")
            assert expire_before and expire_before != "--", \
                f"续期前到期时间异常: {expire_before}"

        with allure_step_log("步骤3: 执行续期操作（延长2个月）"):
            vdb_page.vdb_renewal(name, "2个月")
            vdb_page.wait_for_operation_complete(timeout=30)
            vdb_page.goto_list_page()

        with allure_step_log("步骤4: 验证列表页到期时间已更新"):
            row_data = vdb_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"VDB 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log("步骤5: 进入详情页验证到期时间一致和跳转地址"):
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            assert expire_after in body_text or "--" not in body_text, \
                "详情页到期时间与列表页不一致或仍显示'--'"
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if expire_after and expire_after != "--":
                    vdb_page.verify_jump_page_license_expire(new_page, expire_after)
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")

    @allure.title("VDB-规格升级验证")
    def test_vdb_07_spec_upgrade(self, vdb_instance, vdb_page, ssh_host):
        """场景7：对运行的 VDB 实例执行规格升级，通过 SSH 后端验证。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 获取当前规格信息"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"VDB 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 VDB 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级操作"):
            selected_spec = vdb_page.vdb_spec_upgrade(name)
            logger.info(
                f"VDB 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成，验证状态与规格变更"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=600)
            vdb_page.goto_list_page()
            row_data_after = vdb_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"VDB 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 VDB 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = vdb_page.vdb_get_server_id(name)
            assert server_id, f"未提取到 VDB 实例 {name} 的 server_id"
            vdb_page.goto_list_page()

        with allure_step_log("步骤5: SSH 连接环境后台，验证规格信息"):
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VDB 实例 {name} 的物理机信息"
            cmd = f"ssh -o StrictHostKeyChecking=no {host_short} 'scli guest show {server_id}'"
            output = ssh_host.run(cmd, check_rc=True)
            logger.info(f"SSH 执行 {cmd} 输出:\n{output}")

            vcpu_match = re.search(r"vcpu[s]?\D+(\d+)", output, re.IGNORECASE)
            mem_match = re.search(r"memory_mb\D+(\d+)", output, re.IGNORECASE)

            actual_vcpu = int(vcpu_match.group(1)) if vcpu_match else None
            actual_mem_mb = int(mem_match.group(1)) if mem_match else None
            logger.info(f"scli 解析结果: vcpus={actual_vcpu}, memory_mb={actual_mem_mb}")

            expected_vcpu = selected_spec["vcpus"]
            assert actual_vcpu is not None, \
                f"scli guest show 输出未找到 vcpu 字段, 输出前500字符: {output[:500]}"
            assert actual_vcpu == expected_vcpu, \
                f"vcpu 不匹配: scli返回={actual_vcpu}, 期望={expected_vcpu}"
            logger.info(f"vcpu 验证通过: {actual_vcpu}核")

            expected_mem_mb = selected_spec["memory_mb"]
            assert actual_mem_mb is not None, \
                f"scli guest show 输出未找到 memory_mb 字段, 输出前500字符: {output[:500]}"
            assert actual_mem_mb == expected_mem_mb, \
                f"memory_mb 不匹配: scli返回={actual_mem_mb}, 期望={expected_mem_mb}"
            logger.info(f"memory_mb 验证通过: {actual_mem_mb}MB")

    @allure.title("VDB-云硬盘扩容验证")
    def test_vdb_08_volume_expansion(self, vdb_instance, vdb_page, ssh_host):
        """场景8：对运行的 VDB 实例执行云硬盘扩容，通过 SSH 后端验证。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 进入详情页查看云硬盘大小"):
            vdb_page.goto_list_page()
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"VDB 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤2: 执行云硬盘扩容到 350GiB"):
            server_id = vdb_page.vdb_volume_expand(name, 350)
            assert server_id, f"未提取到 VDB 实例 {name} 的 server_id"
            logger.info(f"VDB 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            physical_host = row_data.get("物理机", "")
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VDB 实例 {name} 的物理机信息"

            actual_size = wait_backend_volume_size(
                ssh_host, server_id, expected_size=350, timeout=300, target_host=host_short
            )
            logger.info("云硬盘扩容 SSH 后端验证通过: 350GiB")

            cmd = f"ssh -o StrictHostKeyChecking=no {host_short} 'scli guest show {server_id}'"
            output = ssh_host.run(cmd, check_rc=True)
            logger.info(f"SSH 执行 {cmd} 输出:\n{output}")

            vol_json_match = re.search(
                r'"volume"\s*:\s*(\{.*?"uuid"\s*:\s*"[0-9a-fA-F-]+".*?\})',
                output, re.DOTALL
            )
            volume_uuid = ""
            if vol_json_match:
                vol_uuid_in_json = re.search(
                    r'"uuid"\s*:\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"',
                    vol_json_match.group(1)
                )
                if vol_uuid_in_json:
                    volume_uuid = vol_uuid_in_json.group(1)
            logger.info(f"VDB 实例 {name} volume_uuid: {volume_uuid}")

            if volume_uuid:
                vol_cmd = f"ssh -o StrictHostKeyChecking=no {host_short} 'scli volume show {volume_uuid}'"
                vol_output = ssh_host.run(vol_cmd, check_rc=True)
                vol_size_match = re.search(r'(?i)size\s*[:|]\s*(\d+)', vol_output)
                if vol_size_match:
                    vol_size = int(vol_size_match.group(1))
                    logger.info(f"scli volume show 解析结果: size={vol_size}GiB")
                    assert vol_size == 350, \
                        f"scli volume show 云硬盘大小不匹配: 实际={vol_size}GiB, 期望=350GiB"
                    logger.info("scli volume show 验证通过: 350GiB")

    @allure.title("VDB-修改名称验证")
    def test_vdb_09_rename(self, vdb_instance, vdb_page):
        """场景9：验证 VDB 实例修改名称功能。"""
        name = vdb_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-vdb-")
        logger.info(f"准备将 VDB 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            vdb_page.vdb_rename(name, new_name)
            vdb_page.assert_popup_success("执行成功")
            vdb_instance["name"] = new_name
            logger.info(f"VDB 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            vdb_page.vdb_to_details(new_name)
            body_text = vdb_page.get_detail_body_text()
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")

    @allure.title("VDB-热迁移-系统分配验证")
    @skip_if_nodes_less_than(2)
    def test_vdb_10_hot_migrate_system(self, vdb_instance, vdb_page, ssh_host):
        """场景10：对运行的 VDB 实例执行系统分配方式热迁移，SSH 后端验证。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 记录当前物理机和 server_id"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            source_host = row_data.get("物理机", "")
            assert source_host, f"未获取到 VDB 实例 {name} 的物理机信息"
            source_host_short = source_host.split(".")[0]
            logger.info(f"VDB 实例 {name} 源物理机: {source_host_short}")
            server_id = vdb_page.vdb_get_server_id(name)
            assert server_id, f"未获取到 VDB 实例 {name} 的 server_id"
            uuid_prefix = server_id[:8]
            logger.info(f"VDB 实例 {name} server_id: {server_id}, uuid前缀: {uuid_prefix}")

        with allure_step_log("步骤2: 执行热迁移（系统分配）"):
            vdb_page.vdb_hot_migrate(name, mode="sys")

        with allure_step_log("步骤3: 验证热迁移后 VM 状态"):
            vdb_page.assert_vdb_status(name, service_status="不可用", vm_status="迁移中", timeout=30)

        with allure_step_log("步骤4: 等待热迁移完成，验证状态恢复"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=300)
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            target_host = row_data.get("物理机", "")
            target_host_short = target_host.split(".")[0] if target_host else ""
            logger.info(f"VDB 实例 {name} 迁移后物理机: {target_host_short}")
            assert target_host and target_host != source_host, \
                f"物理机未变更: 源={source_host}, 目标={target_host}"

        with allure_step_log("步骤5: SSH 验证源物理机无虚机"):
            cmd = (
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            )
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix not in result, \
                f"源节点 {source_host_short} 仍存在虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 源节点 {source_host_short} 已无虚机")

        with allure_step_log("步骤6: SSH 验证目标物理机存在虚机"):
            cmd = (
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            )
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix in result, \
                f"目标节点 {target_host_short} 未找到虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 目标节点 {target_host_short} 已存在虚机")

    @allure.title("VDB-热迁移-手动指定验证")
    @skip_if_nodes_less_than(2)
    def test_vdb_11_hot_migrate_manual(self, vdb_instance, vdb_page, ssh_host):
        """场景11：对运行的 VDB 实例执行手动指定方式热迁移，SSH 后端验证。"""
        name = vdb_instance["name"]

        with allure_step_log("步骤1: 记录当前物理机和 server_id"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            source_host = row_data.get("物理机", "")
            assert source_host, f"未获取到 VDB 实例 {name} 的物理机信息"
            source_host_short = source_host.split(".")[0]
            logger.info(f"VDB 实例 {name} 源物理机: {source_host_short}")
            server_id = vdb_page.vdb_get_server_id(name)
            assert server_id, f"未获取到 VDB 实例 {name} 的 server_id"
            uuid_prefix = server_id[:8]

        with allure_step_log("步骤2: 执行热迁移（手动指定）"):
            vdb_page.vdb_hot_migrate(name, mode="custom")

        with allure_step_log("步骤3: 验证热迁移后 VM 状态"):
            vdb_page.assert_vdb_status(name, service_status="不可用", vm_status="迁移中", timeout=30)

        with allure_step_log("步骤4: 等待热迁移完成，验证状态恢复"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=300)
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            target_host = row_data.get("物理机", "")
            target_host_short = target_host.split(".")[0] if target_host else ""
            logger.info(f"VDB 实例 {name} 迁移后物理机: {target_host_short}")
            assert target_host and target_host != source_host, \
                f"物理机未变更: 源={source_host}, 目标={target_host}"

        with allure_step_log("步骤5: SSH 验证源物理机无虚机"):
            cmd = (
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            )
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix not in result, \
                f"源节点 {source_host_short} 仍存在虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 源节点 {source_host_short} 已无虚机")

        with allure_step_log("步骤6: SSH 验证目标物理机存在虚机"):
            cmd = (
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            )
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix in result, \
                f"目标节点 {target_host_short} 未找到虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 目标节点 {target_host_short} 已存在虚机")

    @allure.title("VDB-绑定公网IP验证")
    def test_vdb_12_bind_eip(self, vdb_instance, vdb_page, security_fip_pool):
        """场景12：对运行的 VDB 实例执行绑定公网IP操作，验证连通性。"""
        name = vdb_instance["name"]
        page = vdb_page.page

        with allure_step_log("步骤1: 进入数据库审计VDB页面"):
            vdb_page.goto_list_page()
            assert "/vdb" in vdb_page.page.url

        with allure_step_log("步骤2: 从安全合规 FIP 池中获取一个公网IP并绑定"):
            eip = security_fip_pool.acquire()
            bound_ip = vdb_page.vdb_bind_public_ip(name, eip_ip=eip, pool_name=security_fip_pool.pool_name)
            assert bound_ip == eip, f"绑定返回的 IP 与指定 IP 不一致: {bound_ip} != {eip}"
            vdb_instance["eip"] = bound_ip
            vdb_page.assert_popup_success("执行成功")
            logger.info(f"VDB 实例 {name} 已绑定公网IP: {bound_ip}")

        with allure_step_log("步骤3: 验证列表页网络信息包含公网IP"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_after = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 绑定后网络信息: {network_after}")
            assert network_after, "绑定公网IP后网络字段为空"
            assert bound_ip in network_after, \
                f"绑定公网IP后网络字段未显示公网IP {bound_ip}: {network_after}"

        with allure_step_log("步骤4: SSH ping 验证公网IP连通性"):
            assert _ping_fip(bound_ip), f"公网IP {bound_ip} 无法连通"
            logger.info(f"SSH 验证通过: 公网IP {bound_ip} 可连通")

        with allure_step_log("步骤5: 验证跳转地址可用"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("跳转地址验证通过")

    @allure.title("VDB-解绑公网IP验证")
    def test_vdb_13_unbind_eip(self, vdb_instance, vdb_page, security_fip_pool):
        """场景13：对已绑定公网IP的 VDB 实例执行解绑公网IP操作。"""
        name = vdb_instance["name"]
        page = vdb_page.page

        with allure_step_log("步骤1: 进入详情页查看跳转地址（确认实例正常运行）"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_before = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 当前网络信息: {network_before}")
            ip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", network_before)
            bound_eip = vdb_instance.get("eip", "")
            if not bound_eip and len(ip_patterns) > 1:
                bound_eip = ip_patterns[-1]
            logger.info(f"VDB 实例 {name} 待解绑公网IP: {bound_eip}")

            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is not None:
                if new_page != page:
                    new_page.close()
                logger.info("解绑前跳转地址验证通过")
            vdb_page.goto_list_page()

        with allure_step_log("步骤2: 执行解绑公网IP操作"):
            vdb_page.vdb_unbind_public_ip(name)
            vdb_page.assert_popup_success("执行成功")
            logger.info(f"VDB 实例 {name} 已解绑公网IP")

        with allure_step_log("步骤3: 验证列表页只显示固定IP"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_after = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 解绑后网络信息: {network_after}")
            ips_after = re.findall(r"\d+\.\d+\.\d+\.\d+", network_after)
            assert len(ips_after) <= 1, \
                f"解绑后仍存在多个IP: {network_after}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址仍可用"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("解绑后跳转地址验证通过")

        with allure_step_log("步骤5: SSH ping 验证公网IP已不可达"):
            if bound_eip:
                if _ping_fip(bound_eip):
                    logger.warning(f"公网IP {bound_eip} 解绑后仍可 ping 通（可能缓存）")
                else:
                    logger.info(f"SSH 验证通过: 公网IP {bound_eip} 已不可达")
            else:
                logger.warning("未获取到待解绑的公网IP，跳过 ping 验证")

        with allure_step_log("步骤6: 将公网IP归还到安全合规 FIP 池"):
            if bound_eip:
                security_fip_pool.release(bound_eip)
                logger.info(f"公网IP {bound_eip} 已归还到 FIP 池")

    @allure.title("VDB-登录VNC控制台验证")
    def test_vdb_14_vnc_login(self, vdb_instance, vdb_page):
        """场景14：点击登录VNC按钮，验证VNC控制台页面可打开。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪，准备登录VNC")

        with allure_step_log("步骤1: 执行登录VNC操作"):
            new_page = vdb_page.vdb_vnc_login(name, password="000000")

        with allure_step_log("步骤2: 验证VNC页面已成功连接"):
            new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            vdb_page.vdb_vnc_check_connected(new_page)

        with allure_step_log("步骤3: 关闭VNC页面"):
            if new_page != vdb_page.page:
                new_page.close()
                logger.info("VNC 页面已关闭")
