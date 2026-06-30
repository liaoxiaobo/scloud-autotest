import re
import time

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than
from sugon_web.testcase.security._security_helpers import wait_backend_volume_size


@allure.epic('安全合规')
@allure.feature('日志审计VER')
@allure.story('VER实例-全生命周期及功能验证')
class TestVerOperations:
    """日志审计 VER 实例全生命周期及功能验证。

    所有场景共享同一个 VER 实例（由 ver_instance fixture 创建），
    类内按顺序依次执行 14 个场景，所有用例执行完成后统一清理。
    """

    @allure.title("VER-新建实例验证")
    def test_ver_01_create(self, ver_instance, ver_page):
        """场景1：新建 VER 实例，验证详情页与跳转地址。"""
        name = ver_instance["name"]
        logger.info(f"VER 实例 {name} 已创建完成")

        with allure_step_log("步骤1: 进入日志审计VER页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url, \
                f"未导航到 VER 页面，当前 URL: {ver_page.page.url}"
            logger.info(f"已进入 VER 列表页: {ver_page.page.url}")

        with allure_step_log("步骤2: 验证详情页与跳转"):
            ver_page.ver_to_details(name)
            ver_page.wait_for_page_ready()
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != ver_page.page:
                    new_page.close()
                logger.info("跳转地址验证通过")

    @allure.title("VER-关机操作")
    def test_ver_02_shutdown(self, ver_instance, ver_page):
        """场景2：对运行的 VER 实例执行关机操作。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url
            logger.info(f"已进入 VER 列表页: {ver_page.page.url}")

        with allure_step_log("步骤2: 执行关机操作"):
            ver_page.ver_operations(name, "关机")

        with allure_step_log("步骤3: 验证关机后服务状态和虚拟机状态"):
            ver_page.assert_ver_status(name, service_status="不可用", vm_status="关机", timeout=300)

        with allure_step_log("步骤4: 验证名称不可点击跳转详情页"):
            is_clickable = ver_page.ver_name_clickable(name)
            assert not is_clickable, f"关机后 VER 实例 {name} 名称仍可点击，期望不可点击"

    @allure.title("VER-开机操作")
    def test_ver_03_power_on(self, ver_instance, ver_page):
        """场景3：对已关机的 VER 实例执行开机操作。"""
        name = ver_instance["name"]
        page = ver_page.page

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url

        with allure_step_log("步骤2: 执行开机操作"):
            ver_page.ver_operations(name, "开机")

        with allure_step_log("步骤3: 等待开机完成，验证服务状态和虚拟机状态"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log("步骤4: 进入详情页再次验证状态"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)
            ver_page.ver_to_details(name)
            ver_page.wait_for_page_ready()
            body_text = ver_page.get_detail_body_text()
            assert "服务状态" in body_text and "虚拟机状态" in body_text, \
                f"详情页未显示服务状态和虚拟机状态信息"
            logger.info("VER 实例开机后状态持续正常")

        with allure_step_log("步骤5: 验证跳转地址"):
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("开机后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "开机后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("开机后跳转地址验证通过")

    @allure.title("VER-退订操作")
    def test_ver_04_unsubscribe(self, ver_instance, ver_page):
        """场景4：对运行的 VER 实例执行退订操作。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url

        with allure_step_log("步骤2: 执行退订操作"):
            ver_page.ver_unsubscribe(name)
            ver_page.wait_for_operation_complete(timeout=60)

        with allure_step_log("步骤3: 验证退订后服务状态"):
            row_data = ver_page.assert_ver_status(name, service_status="已退订", timeout=120)
            service_status = row_data.get("服务状态", "")
            logger.info(f"VER 实例 {name} 退订后服务状态: {service_status}")
            assert "已退订" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log("步骤4: 进入详情页，验证跳转地址和到期时间显示'--'"):
            ver_page.ver_to_details(name)
            body_text = ver_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")

    @allure.title("VER-授权操作")
    def test_ver_05_authorize(self, ver_instance, ver_page):
        """场景5：对已退订的 VER 实例执行授权操作。"""
        name = ver_instance["name"]
        page = ver_page.page

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url

        with allure_step_log("步骤2: 执行授权操作（选择3个月时长）"):
            ver_page.ver_authorize(name, "3个月")
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=600)

        with allure_step_log("步骤3: 验证授权后实例信息准确，服务状态为运行中"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"VER 实例 {name} 授权（3个月）后服务状态: {service_status}, 到期时间: {expire_time}")
            assert "运行" in service_status, f"授权后服务状态异常: {service_status}"
            assert expire_time and expire_time != "--", \
                f"到期时间字段未更新: {expire_time}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "授权后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")

    @allure.title("VER-续期操作")
    def test_ver_06_renewal(self, ver_instance, ver_page):
        """场景6：对运行的 VER 实例执行续期操作。"""
        name = ver_instance["name"]
        page = ver_page.page

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url

        with allure_step_log("步骤2: 记录当前服务到期时间"):
            row_data = ver_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"VER 实例 {name} 续期前到期时间: {expire_before}")
            assert expire_before and expire_before != "--", \
                f"续期前到期时间异常: {expire_before}"

        with allure_step_log("步骤3: 执行续期操作（延长2个月）"):
            ver_page.ver_renewal(name, "2个月")
            ver_page.wait_for_operation_complete(timeout=30)
            ver_page.goto_list_page()

        with allure_step_log("步骤4: 验证列表页到期时间已更新"):
            row_data = ver_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"VER 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log("步骤5: 进入详情页验证到期时间一致和跳转地址"):
            ver_page.ver_to_details(name)
            body_text = ver_page.get_detail_body_text()
            assert expire_after in body_text or "--" not in body_text, \
                "详情页到期时间与列表页不一致或仍显示'--'"
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")

    @allure.title("VER-规格升级验证")
    def test_ver_07_spec_upgrade(self, ver_instance, ver_page, ssh_host):
        """场景7：对运行的 VER 实例执行规格升级，通过 SSH 后端验证。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 获取当前规格信息"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"VER 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 VER 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级（选择比当前高的规格）"):
            selected_spec = ver_page.ver_spec_upgrade(name)
            logger.info(
                f"VER 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成，验证状态变更为运行中，规格已变更"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=600)
            ver_page.goto_list_page()
            row_data_after = ver_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"VER 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 VER 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页记录实例ID"):
            server_id = ver_page.ver_get_server_id(name)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            ver_page.goto_list_page()

        with allure_step_log("步骤5: SSH 连接环境后台验证规格"):
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VER 实例 {name} 的物理机信息"
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

    @allure.title("VER-云硬盘扩容验证")
    def test_ver_08_volume_expansion(self, ver_instance, ver_page, ssh_host):
        """场景8：对运行的 VER 实例执行云硬盘扩容，通过 SSH 后端验证。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 进入日志审计页面并查看云硬盘大小"):
            ver_page.goto_list_page()
            ver_page.ver_to_details(name)
            body_text = ver_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"VER 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤2: 执行云硬盘扩容（300GiB → 350GiB）"):
            server_id = ver_page.ver_volume_expand(name, 350)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            logger.info(f"VER 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            physical_host = row_data.get("物理机", "")
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VER 实例 {name} 的物理机信息"

            actual_size = wait_backend_volume_size(
                ssh_host, server_id, expected_size=350, timeout=300, target_host=host_short
            )
            assert actual_size == 350, \
                f"云硬盘大小不匹配: scli返回={actual_size}GiB, 期望=350GiB"
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
            logger.info(f"VER 实例 {name} volume_uuid: {volume_uuid}")

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

    @allure.title("VER-修改名称验证")
    def test_ver_09_rename(self, ver_instance, ver_page):
        """场景9：验证 VER 实例修改名称功能。"""
        name = ver_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-ver-")
        logger.info(f"准备将 VER 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            ver_page.ver_rename(name, new_name)
            ver_page.assert_popup_success("执行成功")
            ver_instance["name"] = new_name
            logger.info(f"VER 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            ver_page.ver_to_details(new_name)
            body_text = ver_page.get_detail_body_text()
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")

    @allure.title("VER-热迁移-系统分配验证")
    @skip_if_nodes_less_than(2)
    def test_ver_10_hot_migration_system(self, ver_instance, ver_page, ssh_host):
        """场景10：对运行的 VER 实例执行系统分配方式热迁移，SSH 后端验证。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 进入日志审计VER列表页，记录该实例物理机和实例ID"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            src_physical_host = row_data.get("物理机", "")
            assert src_physical_host, f"未获取到 VER 实例 {name} 的物理机信息"
            logger.info(f"VER 实例 {name} 所在物理机: {src_physical_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = ver_page.ver_get_server_id(name)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"VER 实例 {name} server_id: {server_id}, 前缀: {server_id_prefix}")
            ver_page.goto_list_page()

        with allure_step_log("步骤3: 执行热迁移（系统分配-全速）"):
            ver_page.ver_hot_migrate(name, migration_type="系统分配", speed="全速")
            logger.info(f"VER 实例 {name} 系统分配热迁移命令已下发")

        with allure_step_log("步骤4: 等待迁移完成，验证页面状态"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)
            ver_page.goto_list_page()
            row_data_after = ver_page.get_row_data(name)
            target_physical_host = row_data_after.get("物理机", "")
            logger.info(f"VER 实例 {name} 迁移后物理机: {target_physical_host}")
            assert target_physical_host, f"迁移后未获取到物理机信息"
            assert target_physical_host != src_physical_host, \
                f"热迁移后物理机未变化: 源={src_physical_host}, 目标={target_physical_host}"

        source_host_short = src_physical_host.split(".")[0] if "." in src_physical_host else src_physical_host
        target_host_short = target_physical_host.split(".")[0] if "." in target_physical_host else target_physical_host

        with allure_step_log("步骤5: SSH连接源物理机验证虚机已迁出"):
            result_list = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} 'docker exec -i nova_libvirt virsh list'",
                return_rc=True
            )
            logger.info(f"源物理机 {source_host_short} virsh list: rc={result_list['rc']}")
            assert result_list["rc"] == 0, f"virsh list 在源物理机执行失败: {result_list.get('stderr', '')}"

            result_grep = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                return_rc=True
            )
            logger.info(f"源物理机 virsh grep 结果: rc={result_grep['rc']}, stdout={result_grep['stdout']}")
            assert result_grep["rc"] != 0 or server_id_prefix not in result_grep["stdout"], \
                f"源物理机 {source_host_short} 仍存在虚机 {server_id_prefix}，迁出失败"

        with allure_step_log("步骤6: SSH连接目标物理机验证虚机已迁入"):
            result_tgt = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} 'docker exec -i nova_libvirt virsh list'",
                return_rc=True
            )
            logger.info(f"目标物理机 {target_host_short} virsh list: rc={result_tgt['rc']}")
            assert result_tgt["rc"] == 0, f"virsh list 在目标物理机执行失败: {result_tgt.get('stderr', '')}"

            result_tgt_grep = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                return_rc=True
            )
            logger.info(f"目标物理机 virsh grep 结果: rc={result_tgt_grep['rc']}, stdout={result_tgt_grep['stdout']}")
            assert result_tgt_grep["rc"] == 0 or server_id_prefix in result_tgt_grep["stdout"], \
                f"目标物理机 {target_host_short} 未找到虚机 {server_id_prefix}，迁入失败"
            logger.info(f"VER 实例 {name} 热迁移（系统分配）验证通过")

    @allure.title("VER-热迁移-手动指定验证")
    @skip_if_nodes_less_than(2)
    def test_ver_11_hot_migration_manual(self, ver_instance, ver_page, ssh_host):
        """场景11：对运行的 VER 实例执行手动指定方式热迁移，SSH 后端验证。"""
        name = ver_instance["name"]

        with allure_step_log("步骤1: 进入日志审计VER列表页，记录该实例物理机和实例ID"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            src_physical_host = row_data.get("物理机", "")
            assert src_physical_host, f"未获取到 VER 实例 {name} 的物理机信息"
            logger.info(f"VER 实例 {name} 所在物理机: {src_physical_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = ver_page.ver_get_server_id(name)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"VER 实例 {name} server_id: {server_id}, 前缀: {server_id_prefix}")
            ver_page.goto_list_page()

        with allure_step_log("步骤3: 执行手动指定热迁移"):
            try:
                ver_page.ver_hot_migrate(name, migration_type="手动指定", speed="全速")
            except Exception as e:
                if "未找到可用的目标物理机" in str(e):
                    pytest.skip("没有可用的目标物理机进行手动指定热迁移，跳过本场景")
                raise
            logger.info(f"VER 实例 {name} 手动指定热迁移命令已下发")

        with allure_step_log("步骤4: 等待迁移完成，验证页面状态"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)
            ver_page.goto_list_page()
            row_data_after = ver_page.get_row_data(name)
            target_physical_host = row_data_after.get("物理机", "")
            logger.info(f"VER 实例 {name} 迁移后物理机: {target_physical_host}")
            assert target_physical_host, f"迁移后未获取到物理机信息"
            assert target_physical_host != src_physical_host, \
                f"热迁移后物理机未变化: 源={src_physical_host}, 目标={target_physical_host}"

        source_host_short = src_physical_host.split(".")[0] if "." in src_physical_host else src_physical_host
        target_host_short = target_physical_host.split(".")[0] if "." in target_physical_host else target_physical_host

        with allure_step_log("步骤5: SSH连接源物理机验证虚机已迁出"):
            result_list = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} 'docker exec -i nova_libvirt virsh list'",
                return_rc=True
            )
            assert result_list["rc"] == 0, f"virsh list 在源物理机执行失败"

            result_grep = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                return_rc=True
            )
            assert result_grep["rc"] != 0 or server_id_prefix not in result_grep["stdout"], \
                f"源物理机 {source_host_short} 仍存在虚机 {server_id_prefix}，迁出失败"

        with allure_step_log("步骤6: SSH连接目标物理机验证虚机已迁入"):
            result_tgt = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} 'docker exec -i nova_libvirt virsh list'",
                return_rc=True
            )
            assert result_tgt["rc"] == 0, f"virsh list 在目标物理机执行失败"

            result_tgt_grep = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                return_rc=True
            )
            assert result_tgt_grep["rc"] == 0 or server_id_prefix in result_tgt_grep["stdout"], \
                f"目标物理机 {target_host_short} 未找到虚机 {server_id_prefix}，迁入失败"
            logger.info(f"VER 实例 {name} 热迁移（手动指定）验证通过")

    @allure.title("VER-绑定公网IP验证")
    def test_ver_12_bind_eip(self, ver_instance, ver_page, ssh_host):
        """场景12：对运行的 VER 实例执行绑定公网IP操作，验证连通性。"""
        name = ver_instance["name"]
        page = ver_page.page

        with allure_step_log("步骤1: 进入日志审计页面"):
            ver_page.goto_list_page()
            assert "/ver" in ver_page.page.url

        with allure_step_log("步骤2: 执行绑定公网IP操作"):
            eip = ver_page.ver_bind_eip(name, pool_keyword="public_net")
            assert eip, f"VER 实例 {name} 绑定公网IP失败，未返回 IP 地址"
            logger.info(f"VER 实例 {name} 已绑定公网IP: {eip}")

        with allure_step_log("步骤3: SSH ping 验证公网IP连通性"):
            result = ssh_host.run(f"ping -c 4 {eip}", return_rc=True)
            logger.info(f"ping {eip} 结果: rc={result['rc']}, stdout={result['stdout'][:200]}")
            assert result["rc"] == 0, f"无法 ping 通公网IP {eip}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("绑定公网IP后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "绑定公网IP后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("绑定公网IP后跳转地址验证通过")
            ver_page.goto_list_page()

    @allure.title("VER-解绑公网IP验证")
    def test_ver_13_unbind_eip(self, ver_instance, ver_page, ssh_host):
        """场景13：对已绑定公网IP的 VER 实例执行解绑公网IP操作。"""
        name = ver_instance["name"]
        page = ver_page.page

        with allure_step_log("步骤1: 进入详情页查看跳转地址（确认实例正常运行）"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            network_before = row_data.get("网络", "")
            logger.info(f"VER 实例 {name} 当前网络信息: {network_before}")
            ip_patterns = re.findall(r"\d+\.\d+\.\d+\.\d+", network_before)
            bound_eip = ""
            if len(ip_patterns) > 1:
                bound_eip = ip_patterns[-1]
            logger.info(f"VER 实例 {name} 待解绑公网IP: {bound_eip}")

            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is not None:
                if new_page != page:
                    new_page.close()
                logger.info("解绑前跳转地址验证通过")
            ver_page.goto_list_page()

        with allure_step_log("步骤2: 执行解绑公网IP操作"):
            ver_page.ver_unbind_eip(name)
            logger.info(f"VER 实例 {name} 已解绑公网IP")

        with allure_step_log("步骤3: 验证解绑后跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("解绑后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "解绑后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("解绑后跳转地址验证通过")
            ver_page.goto_list_page()

        with allure_step_log("步骤4: SSH ping 验证公网IP已解绑"):
            if bound_eip:
                result = ssh_host.run(f"ping -c 4 {bound_eip}", return_rc=True)
                logger.info(f"ping {bound_eip} 结果: rc={result['rc']}")
                assert result["rc"] != 0, f"公网IP {bound_eip} 解绑后仍可 ping 通"
                logger.info(f"公网IP {bound_eip} 已解绑，ping 不可达")
            else:
                logger.warning("未找到待解绑的公网IP，跳过 ping 验证")

    @allure.title("VER-登录VNC控制台验证")
    def test_ver_14_vnc_login(self, ver_instance, ver_page):
        """场景14：点击登录VNC按钮，验证VNC控制台页面可打开。"""
        name = ver_instance["name"]
        logger.info(f"VER 实例 {name} 已就绪，准备登录VNC")

        with allure_step_log("步骤1: 打开VNC控制台"):
            vnc_page = ver_page.ver_vnc_login(name, vncpwd="000000")
            assert vnc_page is not None, "VNC 页面未打开"
            assert "chrome-error" not in vnc_page.url, f"VNC 页面加载到错误页面: {vnc_page.url}"
            logger.info(f"VER 实例 {name} VNC 控制台打开成功，URL: {vnc_page.url}")

        with allure_step_log("步骤2: 确认VNC页面内容"):
            if "chrome-error" not in vnc_page.url:
                vnc_body = vnc_page.inner_text("body")[:500]
                logger.info(f"VNC 页面 body 内容: {vnc_body}")
            logger.info(f"VER 实例 {name} VNC 登录验证通过")
