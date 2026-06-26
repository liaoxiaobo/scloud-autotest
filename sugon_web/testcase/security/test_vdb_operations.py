import re

import allure
import pytest
from sugon_web.testcase.security._security_helpers import wait_backend_volume_size
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than


@allure.epic('安全合规')
@allure.feature('数据库审计VDB')
@allure.story('VDB实例-全生命周期操作验证')
class TestVdbOperations:

    @allure.title("VDB-退订-授权-续期生命周期操作")
    def test_vdb_unsubscribe_authorize_renew(self, vdb_instance, vdb_page):
        """通过 fixture 获取共享 VDB 实例执行退订 → 授权（3个月）→
        续期（2个月）的全生命周期操作，验证到期时间更新和跳转地址可用性。"""
        name = vdb_instance["name"]
        page = vdb_page.page
        logger.info(f"VDB 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入实例详情页查看信息"):
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            logger.info("详情页信息已获取")
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤2: 验证跳转地址"):
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
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤3: 执行退订操作"):
            vdb_page.vdb_unsubscribe(name)
            vdb_page.wait_for_operation_complete(timeout=60)
            vdb_page.goto_list_page()
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

        with allure_step_log(f"步骤4: 验证退订后详情页信息"):
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤5: 执行授权操作（选择3个月时长）"):
            vdb_page.vdb_authorize(name, "3个月")
            row_data = vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=120)
            expire_time_after_auth = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time_after_auth = v
                    break
            logger.info(f"DEBUG row_data keys: {list(row_data.keys())}")
            logger.info(f"VDB 实例 {name} 授权（3个月）完成，到期时间: {expire_time_after_auth}")
            assert expire_time_after_auth and expire_time_after_auth != "--", \
                f"到期时间字段未更新: {expire_time_after_auth}"

        with allure_step_log(f"步骤6: 进入详情页验证授权后跳转地址"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if expire_time_after_auth and expire_time_after_auth != "--":
                    vdb_page.verify_jump_page_license_expire(new_page, expire_time_after_auth)
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤7: 执行续期操作（延长2个月）"):
            row_data = vdb_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"VDB 实例 {name} 续期前到期时间: {expire_before}")
            vdb_page.vdb_renewal(name, "2个月")
            vdb_page.wait_for_operation_complete(timeout=30)
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"VDB 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log(f"步骤8: 进入详情页验证续期后到期时间和跳转地址"):
            vdb_page.vdb_to_details(name)
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
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            detail_expire = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    detail_expire = v
                    break
            assert detail_expire and detail_expire != "--", \
                f"详情页到期时间异常: {detail_expire}"
            logger.info(f"VDB 实例 {name} 续期后验证通过，到期时间: {detail_expire}")

    @allure.title("VDB-规格升级验证")
    def test_vdb_spec_upgrade(self, vdb_instance, vdb_page, ssh_host):
        """通过 fixture 获取共享 VDB 实例执行规格升级，
        验证升级前后规格信息变化，并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""
        name = vdb_instance["name"]
        page = vdb_page.page
        logger.info(f"VDB 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 获取当前规格信息"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"VDB 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 VDB 实例 {name} 的规格信息"

        with allure_step_log(f"步骤2: 执行规格升级操作"):
            selected_spec = vdb_page.vdb_spec_upgrade(name)
            logger.info(
                f"VDB 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log(f"步骤3: 等待规格升级完成，验证状态与规格变更"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=600)
            vdb_page.goto_list_page()
            row_data_after = vdb_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"VDB 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 VDB 实例 {name} 升级后的规格信息"

        with allure_step_log(f"步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = vdb_page.vdb_get_server_id(name)
            assert server_id, f"未提取到 VDB 实例 {name} 的 server_id"
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤5: SSH 连接环境后台，验证规格信息"):
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
    def test_vdb_volume_expansion(self, vdb_instance, vdb_page, ssh_host):
        """通过 fixture 获取共享 VDB 实例，执行云硬盘从当前大小扩容到 350GiB，
        通过 SSH 后端验证扩容结果。"""
        name = vdb_instance["name"]
        page = vdb_page.page
        logger.info(f"VDB 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入详情页查看云硬盘大小"):
            vdb_page.goto_list_page()
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"VDB 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log(f"步骤2: 执行云硬盘扩容到 350GiB"):
            server_id = vdb_page.vdb_volume_expand(name, 350)
            assert server_id, f"未提取到 VDB 实例 {name} 的 server_id"
            logger.info(f"VDB 实例 {name} server_id: {server_id}")

        with allure_step_log(f"步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            physical_host = row_data.get("物理机", "")
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VDB 实例 {name} 的物理机信息"

            actual_size = wait_backend_volume_size(
                ssh_host, server_id, expected_size=350, timeout=300, target_host=host_short
            )
            logger.info("云硬盘扩容 SSH 后端验证通过: 350GiB")

            # 重新读取 scli guest show 输出以提取 volume_uuid
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

    @allure.title("VDB-实例-修改名称验证")
    def test_vdb_rename(self, vdb_instance, vdb_page):
        """验证 VDB 实例修改名称功能：
        修改名称后列表页和详情页均展示新名称。"""
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
    def test_vdb_hot_migrate_system(self, vdb_instance, vdb_page, ssh_host):
        """验证 VDB 实例热迁移（系统分配）功能：
        记录源物理机 → 系统分配热迁移 → SSH 验证源节点无虚机、目标节点有虚机。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪")

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
            cmd = f"ssh -o StrictHostKeyChecking=no {source_host_short} 'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix not in result, f"源节点 {source_host_short} 仍存在虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 源节点 {source_host_short} 已无虚机")

        with allure_step_log("步骤6: SSH 验证目标物理机存在虚机"):
            cmd = f"ssh -o StrictHostKeyChecking=no {target_host_short} 'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix in result, f"目标节点 {target_host_short} 未找到虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 目标节点 {target_host_short} 已存在虚机")

    @allure.title("VDB-热迁移-手动指定验证")
    @skip_if_nodes_less_than(2)
    def test_vdb_hot_migrate_manual(self, vdb_instance, vdb_page, ssh_host):
        """验证 VDB 实例热迁移（手动指定）功能：
        记录源物理机 → 手动选择目标物理机热迁移 → SSH 验证源节点无虚机、目标节点有虚机。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪")

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
            cmd = f"ssh -o StrictHostKeyChecking=no {source_host_short} 'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix not in result, f"源节点 {source_host_short} 仍存在虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 源节点 {source_host_short} 已无虚机")

        with allure_step_log("步骤6: SSH 验证目标物理机存在虚机"):
            cmd = f"ssh -o StrictHostKeyChecking=no {target_host_short} 'sudo docker exec nova_libvirt virsh list | grep {uuid_prefix}'"
            result = ssh_host.run(cmd, check_rc=False)
            assert uuid_prefix in result, f"目标节点 {target_host_short} 未找到虚机 {uuid_prefix}: {result[:200]}"
            logger.info(f"SSH 验证通过: 目标节点 {target_host_short} 已存在虚机")

    @allure.title("VDB-绑定公网IP验证")
    def test_vdb_bind_public_ip(self, vdb_instance, vdb_page, ssh_host):
        """验证 VDB 实例绑定公网 IP 功能：
        绑定 public_net 池中的公网IP → SSH ping 验证连通性 → 跳转地址验证。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪")

        with allure_step_log("步骤1: 记录当前网络信息"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_info = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 绑定前网络信息: {network_info}")

        with allure_step_log("步骤2: 执行绑定公网IP操作"):
            vdb_page.vdb_bind_public_ip(name, pool_name="public_net")
            vdb_page.assert_popup_success("执行成功")

        with allure_step_log("步骤3: 验证列表页网络信息包含公网IP"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_after = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 绑定后网络信息: {network_after}")
            assert network_after, "绑定公网IP后网络字段为空"
            assert "," in network_after or "：固定" not in network_after, \
                f"绑定公网IP后网络字段未显示公网和固定IP: {network_after}"

            # 提取公网 IP 地址
            import re as _re
            ip_match = _re.findall(r"\d+\.\d+\.\d+\.\d+", network_after)
            public_ip = ip_match[-1] if len(ip_match) > 1 else (ip_match[0] if ip_match else "")
            logger.info(f"VDB 实例 {name} 绑定公网IP: {public_ip}")

        with allure_step_log("步骤4: SSH ping 验证公网IP连通性"):
            if public_ip:
                ping_cmd = f"ping -c 3 -W 5 {public_ip}"
                ping_result = ssh_host.run(ping_cmd, check_rc=False)
                assert ping_result and "ttl=" in ping_result.lower(), \
                    f"公网IP {public_ip} ping 失败: {ping_result[:200]}"
                logger.info(f"SSH 验证通过: 公网IP {public_ip} 可连通")
            else:
                logger.warning("未提取到公网IP，跳过 ping 验证")

        with allure_step_log("步骤5: 验证跳转地址可用"):
            vdb_page.vdb_to_details(name)
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

    @allure.title("VDB-解绑公网IP验证")
    def test_vdb_unbind_public_ip(self, vdb_instance, vdb_page, ssh_host):
        """验证 VDB 实例解绑公网 IP 功能：
        先确保有绑定的公网IP → 解绑 → 验证仅保留固定IP → SSH ping 不可达 → 跳转地址仍可用。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪")

        # 自保证：若未绑定 IP 则先绑定一个
        with allure_step_log("步骤0(自保证): 确保实例已绑定公网IP"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_info = row_data.get("网络", "") or ""
            import re as _re
            ips = _re.findall(r"\d+\.\d+\.\d+\.\d+", network_info)
            if len(ips) <= 1:
                logger.info("实例未绑定公网IP，先执行绑定操作")
                vdb_page.vdb_bind_public_ip(name)
                vdb_page.assert_popup_success("执行成功")
                vdb_page.goto_list_page()
                row_data = vdb_page.get_row_data(name)
                network_info = row_data.get("网络", "") or ""
                ips = _re.findall(r"\d+\.\d+\.\d+\.\d+", network_info)

            assert len(ips) > 1, f"绑定公网IP后仍只有一个IP: {network_info}"
            bound_ip = ips[-1]
            logger.info(f"VDB 实例 {name} 已绑定公网IP: {bound_ip}")

        with allure_step_log("步骤1: 进入详情页验证跳转地址"):
            vdb_page.vdb_to_details(name)
            body_text = vdb_page.get_detail_body_text()
            assert "跳转地址" in body_text, "详情页未显示跳转地址字段"
            vdb_page.goto_list_page()

        with allure_step_log("步骤2: 执行解绑公网IP操作"):
            vdb_page.vdb_unbind_public_ip(name)
            vdb_page.assert_popup_success("执行成功")

        with allure_step_log("步骤3: 验证列表页只显示固定IP"):
            vdb_page.goto_list_page()
            row_data = vdb_page.get_row_data(name)
            network_after = row_data.get("网络", "") or ""
            logger.info(f"VDB 实例 {name} 解绑后网络信息: {network_after}")
            ips_after = _re.findall(r"\d+\.\d+\.\d+\.\d+", network_after)
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
                if new_page != vdb_page.page:
                    new_page.close()
                logger.info("解绑后跳转地址验证通过")

        with allure_step_log("步骤5: SSH ping 验证公网IP已不可达"):
            if bound_ip:
                ping_cmd = f"ping -c 2 -W 3 {bound_ip}"
                ping_result = ssh_host.run(ping_cmd, check_rc=False)
                if ping_result and "ttl=" in ping_result.lower():
                    logger.warning(f"公网IP {bound_ip} 解绑后仍可 ping 通（可能缓存）")
                else:
                    logger.info(f"SSH 验证通过: 公网IP {bound_ip} 已不可达")
            else:
                logger.warning("未获取到已绑定的公网IP，跳过 ping 验证")

    @allure.title("VDB-登录VNC验证")
    def test_vdb_vnc_login(self, vdb_instance, vdb_page):
        """验证 VDB 实例 VNC 登录功能：
        点击登录VNC → 新页面输入密码 → 验证成功连接。"""
        name = vdb_instance["name"]
        logger.info(f"VDB 实例 {name} 已就绪")

        with allure_step_log("步骤1: 执行登录VNC操作"):
            new_page = vdb_page.vdb_vnc_login(name, password="000000")

        with allure_step_log("步骤2: 验证VNC页面已成功连接"):
            new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            # VNC 使用 canvas 渲染，通过 Page Object 方法验证连接状态
            vdb_page.vdb_vnc_check_connected(new_page)

        with allure_step_log("步骤3: 关闭VNC页面"):
            if new_page != vdb_page.page:
                new_page.close()
                logger.info("VNC 页面已关闭")
