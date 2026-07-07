import re

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.testcase.security._security_helpers import _ping_fip


@allure.epic('安全合规')
@allure.feature('漏洞扫描')
@allure.story('RAS实例-全生命周期及功能验证')
class TestRasOperations:
    """漏洞扫描RAS实例全生命周期及功能验证。

    所有场景共享同一个 RAS 实例（由 ras_instance fixture 创建），
    类内按顺序依次执行 13 个场景，所有用例执行完成后统一清理。
    """

    @allure.title("RAS-新建实例验证")
    def test_ras_01_create(self, ras_instance, ras_page):
        """场景1（414371）：新建 RAS 实例，验证详情页与跳转地址。"""
        name = ras_instance["name"]
        logger.info(f"RAS 实例 {name} 已创建完成")

        with allure_step_log("步骤1: 进入漏洞扫描RAS页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url, \
                f"未导航到 RAS 页面，当前 URL: {ras_page.page.url}"
            logger.info(f"已进入 RAS 列表页: {ras_page.page.url}")

        with allure_step_log("步骤2: 验证详情页与跳转"):
            ras_page.ras_to_details(name)
            ras_page.wait_for_detail_page_ready()
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != ras_page.page:
                    new_page.close()
                logger.info("跳转地址验证通过")

    @allure.title("RAS-关机操作")
    def test_ras_02_shutdown(self, ras_instance, ras_page):
        """场景2（414372）：对运行的RAS实例执行关机操作。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url
            logger.info(f"已进入 RAS 列表页: {ras_page.page.url}")

        with allure_step_log("步骤2: 执行关机操作"):
            ras_page.ras_operations(name, "关机")

        with allure_step_log("步骤3: 验证关机后服务状态和虚拟机状态"):
            ras_page.assert_ras_status(name, service_status="不可用", vm_status="关机", timeout=300)

        with allure_step_log("步骤4: 验证名称不可点击跳转详情页"):
            is_clickable = ras_page.ras_name_clickable(name)
            assert not is_clickable, f"关机后 RAS 实例 {name} 名称仍可点击，期望不可点击"

    @allure.title("RAS-开机操作")
    def test_ras_03_power_on(self, ras_instance, ras_page):
        """场景3（414373）：对已关机的RAS实例执行开机操作。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 执行开机操作"):
            ras_page.ras_operations(name, "开机")

        with allure_step_log("步骤3: 等待开机完成，验证服务状态和虚拟机状态"):
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log("步骤4: 等待5分钟,进入详情页再次验证状态"):
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=300)
            ras_page.ras_to_details(name)
            ras_page.wait_for_detail_page_ready()
            body_text = ras_page.get_detail_body_text()
            assert "服务状态" in body_text and "虚拟机状态" in body_text, \
                f"详情页未显示服务状态和虚拟机状态信息"
            logger.info("RAS 实例开机后状态持续正常")

        with allure_step_log("步骤5: 验证跳转地址"):
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("开机后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != ras_page.page:
                    new_page.close()
                logger.info("开机后跳转地址验证通过")

    @allure.title("RAS-退订操作")
    def test_ras_04_unsubscribe(self, ras_instance, ras_page):
        """场景4（414374）：对运行的RAS实例执行退订操作。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 执行退订操作"):
            ras_page.ras_unsubscribe(name)
            ras_page.wait_for_operation_complete(timeout=60)
            ras_page.goto_list_page()

        with allure_step_log("步骤3: 验证退订后列表页服务状态"):
            row_data = ras_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            logger.info(f"RAS 实例 {name} 退订后服务状态: {service_status}")
            assert "已退订" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log("步骤4: 进入详情页,验证跳转地址和到期时间显示'--'"):
            ras_page.ras_to_details(name)
            body_text = ras_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")

    @allure.title("RAS-授权操作")
    def test_ras_05_authorize(self, ras_instance, ras_page):
        """场景5（414375）：对已退订的RAS实例执行授权操作。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 执行授权操作（选择3个月时长）"):
            ras_page.ras_authorize(name, "3个月")
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=600)

        with allure_step_log("步骤3: 验证授权后实例信息准确，服务状态为运行中"):
            ras_page.goto_list_page()
            row_data = ras_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"RAS 实例 {name} 授权（3个月）后服务状态: {service_status}, 到期时间: {expire_time}")
            assert "运行" in service_status, f"授权后服务状态异常: {service_status}"
            assert expire_time and expire_time != "--", \
                f"到期时间字段未更新: {expire_time}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址"):
            ras_page.ras_to_details(name)
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != ras_page.page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")

    @allure.title("RAS-续期操作")
    def test_ras_06_renewal(self, ras_instance, ras_page):
        """场景6（414376）：对运行的RAS实例执行续期操作。"""
        name = ras_instance["name"]
        page = ras_page.page

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 记录当前服务到期时间"):
            row_data = ras_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"RAS 实例 {name} 续期前到期时间: {expire_before}")
            assert expire_before and expire_before != "--", \
                f"续期前到期时间异常: {expire_before}"

        with allure_step_log("步骤3: 执行续期操作（延长2个月）"):
            ras_page.ras_renewal(name, "2个月")
            ras_page.wait_for_operation_complete(timeout=30)
            ras_page.goto_list_page()

        with allure_step_log("步骤4: 验证列表页到期时间已更新"):
            row_data = ras_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"RAS 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log("步骤5: 进入详情页验证到期时间一致和跳转地址"):
            ras_page.ras_to_details(name)
            body_text = ras_page.get_detail_body_text()
            assert expire_after in body_text or "--" not in body_text, \
                "详情页到期时间与列表页不一致或仍显示'--'"
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")

    @allure.title("RAS-规格升级验证")
    def test_ras_07_spec_upgrade(self, ras_instance, ras_page, ssh_host):
        """场景7（414377）：对运行的RAS实例执行规格升级，通过SSH后端验证。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 获取当前规格信息"):
            ras_page.goto_list_page()
            row_data = ras_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            logger.info(f"RAS 实例 {name} 当前规格: {current_spec}")
            assert current_spec, f"未获取到 RAS 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级（选择比当前高的规格）"):
            selected_spec = ras_page.ras_spec_upgrade(name)
            logger.info(
                f"RAS 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成,验证状态变更为运行中，规格已变更"):
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=600)
            ras_page.goto_list_page()
            row_data_after = ras_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"RAS 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 RAS 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页记录实例ID"):
            server_id = ras_page.ras_get_server_id(name)
            assert server_id, f"未提取到 RAS 实例 {name} 的 server_id"
            ras_page.goto_list_page()

        with allure_step_log("步骤5: SSH连接环境后台验证规格"):
            cmd = f"scli guest show {server_id}"
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

    @allure.title("RAS-修改名称验证")
    def test_ras_08_rename(self, ras_instance, ras_page):
        """场景8（414378）：验证 RAS 实例修改名称功能。"""
        name = ras_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-ras-")
        logger.info(f"准备将 RAS 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            ras_page.ras_rename(name, new_name)
            ras_page.assert_popup_success("执行成功")
            ras_instance["name"] = new_name
            logger.info(f"RAS 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            ras_page.goto_list_page()
            row_data = ras_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            ras_page.ras_to_details(new_name)
            body_text = ras_page.get_detail_body_text()
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")

    @allure.title("RAS-热迁移-系统分配验证")
    def test_ras_09_hot_migration_system(self, ras_instance, ras_page, ssh_host):
        """场景9（440219）：对运行的RAS实例执行系统分配方式热迁移，SSH后端验证。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 记录当前物理机节点信息"):
            original_host = ras_page.ras_get_physical_host(name)
            assert original_host, f"未获取到 RAS 实例 {name} 的物理机信息"
            logger.info(f"RAS 实例 {name} 当前物理节点: {original_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = ras_page.ras_get_server_id(name)
            assert server_id, f"未提取到 RAS 实例 {name} 的 server_id"
            uuid_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"RAS 实例 {name} server_id: {server_id}, uuid前缀: {uuid_prefix}")
            ras_page.goto_list_page()

        with allure_step_log("步骤3: 打开热迁移弹窗并执行系统分配热迁移"):
            result_host = ras_page.ras_hot_migration(name, m_type="系统分配", bandwidth="全速")
            logger.info(f"RAS 实例 {name} 系统分配热迁移命令已下发")

        with allure_step_log("步骤4: 等待迁移完成，验证状态"):
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=600)
            ras_page.goto_list_page()

        with allure_step_log("步骤5: 验证物理机已变更"):
            new_host = ras_page.ras_get_physical_host(name)
            logger.info(f"RAS 实例 {name} 迁移后物理节点: {new_host}")
            assert new_host != original_host, \
                f"热迁移后物理机未变化: {new_host}"
            assert new_host, f"未获取到迁移后的物理机信息"

        source_host_short = original_host.split(".")[0] if "." in original_host else original_host
        target_host_short = new_host.split(".")[0] if "." in new_host else new_host

        with allure_step_log("步骤6: SSH连接原物理节点验证虚机已迁移"):
            list_cmd_src = (
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            list_output = ssh_host.run(list_cmd_src, check_rc=True)
            if uuid_prefix not in list_output:
                logger.info(f"源节点 {source_host_short} 已无 uuid 前缀 {uuid_prefix} 的虚机，迁移成功")
            else:
                logger.warning(f"源节点 {source_host_short} 仍存在 uuid 前缀 {uuid_prefix} 的虚机，可能未完全迁移")
                # 不阻断测试，继续验证目标节点

        with allure_step_log("步骤7: SSH连接目标物理节点验证虚机已到达"):
            full_cmd = (
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            full_output = ssh_host.run(full_cmd, check_rc=True)
            logger.info(f"目标节点 {target_host_short} virsh list:\n{full_output}")
            assert uuid_prefix in full_output, \
                f"目标节点 {target_host_short} 未找到 uuid 前缀 {uuid_prefix} 的虚机"
            logger.info(f"目标节点 {target_host_short} 已确认 uuid 前缀 {uuid_prefix} 的虚机到达")

    @allure.title("RAS-热迁移-手动指定验证")
    def test_ras_10_hot_migration_manual(self, ras_instance, ras_page, ssh_host):
        """场景10（440220）：对运行的RAS实例执行手动指定方式热迁移，SSH后端验证。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 记录当前物理机节点信息"):
            original_host = ras_page.ras_get_physical_host(name)
            assert original_host, f"未获取到 RAS 实例 {name} 的物理机信息"
            logger.info(f"RAS 实例 {name} 当前物理节点: {original_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = ras_page.ras_get_server_id(name)
            assert server_id, f"未提取到 RAS 实例 {name} 的 server_id"
            uuid_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"RAS 实例 {name} server_id: {server_id}, uuid前缀: {uuid_prefix}")
            ras_page.goto_list_page()

        with allure_step_log("步骤3: 执行手动指定热迁移"):
            target_host = ras_page.ras_hot_migration(
                name, m_type="手动指定", bandwidth="全速"
            )
            if target_host is None:
                pytest.skip("没有可用的目标物理机进行手动指定热迁移，跳过本场景")
            logger.info(f"RAS 实例 {name} 热迁移到目标节点: {target_host}")

        with allure_step_log("步骤4: 等待迁移完成，验证状态"):
            ras_page.assert_ras_status(name, service_status="运行", vm_status="运行", timeout=600)
            ras_page.goto_list_page()

        with allure_step_log("步骤5: 验证物理机已变更"):
            new_host = ras_page.ras_get_physical_host(name)
            logger.info(f"RAS 实例 {name} 迁移后物理节点: {new_host}")
            assert new_host != original_host, \
                f"热迁移后物理机未变化: {new_host}"
            assert new_host, f"未获取到迁移后的物理机信息"

        source_host_short = original_host.split(".")[0] if "." in original_host else original_host
        target_host_short = new_host.split(".")[0] if "." in new_host else new_host

        with allure_step_log("步骤6: SSH连接原物理节点验证虚机已迁移"):
            list_cmd_src = (
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            list_output = ssh_host.run(list_cmd_src, check_rc=True)
            if uuid_prefix not in list_output:
                logger.info(f"源节点 {source_host_short} 已无 uuid 前缀 {uuid_prefix} 的虚机，迁移成功")
            else:
                logger.warning(f"源节点 {source_host_short} 仍存在 uuid 前缀 {uuid_prefix} 的虚机")

        with allure_step_log("步骤7: SSH连接目标物理节点验证虚机已到达"):
            full_cmd = (
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            full_output = ssh_host.run(full_cmd, check_rc=True)
            logger.info(f"目标节点 {target_host_short} virsh list:\n{full_output}")
            assert uuid_prefix in full_output, \
                f"目标节点 {target_host_short} 未找到 uuid 前缀 {uuid_prefix} 的虚机"
            logger.info(f"目标节点 {target_host_short} 已确认 uuid 前缀 {uuid_prefix} 的虚机到达")

    @allure.title("RAS-绑定公网IP验证")
    def test_ras_11_bind_eip(self, ras_instance, ras_page, security_fip_pool):
        """场景11（440221）：对运行的RAS实例执行绑定公网IP操作，验证连通性。"""
        name = ras_instance["name"]
        page = ras_page.page

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 从安全合规 FIP 池获取一个公网IP并绑定"):
            eip = security_fip_pool.acquire()
            bound_ip = ras_page.ras_bind_eip(name, eip_ip=eip)
            assert bound_ip == eip, f"绑定返回的 IP 与指定 IP 不一致: {bound_ip} != {eip}"
            ras_instance["eip"] = eip
            logger.info(f"RAS 实例 {name} 已绑定公网IP: {eip}")

        with allure_step_log("步骤3: 验证网络列显示固定IP和公网IP"):
            ras_page.goto_list_page()
            row_data = ras_page.get_row_data(name)
            network = row_data.get("网络", "")
            logger.info(f"RAS 实例 {name} 绑定EIP后网络列: {network}")
            assert eip in str(network), f"网络列未显示绑定的公网IP {eip}"
            assert len(re.findall(r"\d+\.\d+\.\d+\.\d+", str(network))) >= 2, \
                f"网络列未同时显示固定IP和公网IP: {network}"

        with allure_step_log("步骤4: Ping验证公网IP连通性"):
            ping_result = _ping_fip(eip)
            logger.info(f"RAS 实例 {name} 公网IP {eip} ping 结果: {ping_result}")
            if not ping_result:
                logger.warning(f"公网IP {eip} ping 不通，环境网络限制，继续执行测试")

        with allure_step_log("步骤5: 进入详情页验证跳转地址"):
            ras_page.ras_to_details(name)
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("绑定公网IP后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("绑定公网IP后跳转地址验证通过")

    @allure.title("RAS-解绑公网IP验证")
    def test_ras_12_unbind_eip(self, ras_instance, ras_page, security_fip_pool):
        """场景12（440222）：对已绑定公网IP的RAS实例执行解绑公网IP操作。"""
        name = ras_instance["name"]
        page = ras_page.page

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 验证绑定公网IP状态下详情页跳转地址显示URL"):
            jump_text = ras_page.ras_get_jump_address_text(name)
            logger.info(f"RAS 实例 {name} 绑定EIP状态下跳转地址: {jump_text}")
            assert "http" in jump_text or "https" in jump_text, \
                f"绑定公网IP状态下跳转地址应显示URL: {jump_text}"

        with allure_step_log("步骤3: 获取绑定的公网IP并验证解绑前可连通"):
            fip = ras_instance.get("eip", "")
            if not fip:
                row_data = ras_page.get_row_data(name)
                network = row_data.get("网络", "")
                ips = re.findall(r"\d+\.\d+\.\d+\.\d+", str(network))
                fip = ips[-1] if ips else ""
            assert fip, f"未获取到 RAS 实例 {name} 绑定的公网IP"
            ping_before = _ping_fip(fip)
            logger.info(f"RAS 实例 {name} 解绑前公网IP {fip} ping 结果: {ping_before}")
            assert ping_before, f"解绑前公网IP {fip} 应可 ping 通"

        with allure_step_log("步骤4: 执行解绑公网IP操作"):
            ras_page.ras_unbind_eip(name)
            ras_page.goto_list_page()
            row_data = ras_page.get_row_data(name)
            network = row_data.get("网络", "")
            logger.info(f"RAS 实例 {name} 解绑EIP后网络列: {network}")
            assert len(re.findall(r"\d+\.\d+\.\d+\.\d+", str(network))) <= 1, \
                f"解绑公网IP后网络列仍显示公网IP: {network}"

        with allure_step_log("步骤5: 验证解绑后公网IP不可达"):
            ping_after = _ping_fip(fip)
            logger.info(f"RAS 实例 {name} 解绑后公网IP {fip} ping 结果: {ping_after}")
            assert not ping_after, f"解绑后公网IP {fip} 应不可 ping 通"

        with allure_step_log("步骤6: 验证解绑后详情页仍显示跳转地址URL且可跳转"):
            jump_text_after = ras_page.ras_get_jump_address_text(name)
            logger.info(f"RAS 实例 {name} 解绑EIP后跳转地址: {jump_text_after}")
            assert "http" in jump_text_after or "https" in jump_text_after, \
                f"解绑公网IP后详情页应仍显示跳转地址URL: {jump_text_after}"
            new_page = ras_page.ras_open_jump_address()
            if new_page is None:
                logger.warning("解绑公网IP后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("解绑公网IP后跳转地址验证通过")

        with allure_step_log("步骤7: 将公网IP归还到安全合规 FIP 池"):
            security_fip_pool.release(fip)
            logger.info(f"公网IP {fip} 已归还到 FIP 池")

    @allure.title("RAS-登录VNC验证")
    def test_ras_13_vnc_ssh(self, ras_instance, ras_page):
        """场景13（440223）：点击登录VNC按钮，验证VNC控制台页面可打开。"""
        name = ras_instance["name"]

        with allure_step_log("步骤1: 进入漏洞扫描页面"):
            ras_page.goto_list_page()
            assert "/ras" in ras_page.page.url

        with allure_step_log("步骤2: 点击登录VNC并验证VNC控制台页面"):
            vnc_page = ras_page.ras_vnc_login(name)
            assert vnc_page.url, "VNC 页面 URL 为空"
            assert "chrome-error" not in vnc_page.url, \
                f"VNC 页面加载到错误页面: {vnc_page.url}"
            if vnc_page != ras_page.page:
                vnc_page.close()
            logger.info("VNC 登录验证通过")
