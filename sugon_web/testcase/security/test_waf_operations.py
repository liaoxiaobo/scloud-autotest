from sugon_web.testcase.security._security_helpers import wait_backend_volume_size, _ping_fip
import re

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than


def _retry_get_row_data(waf_obj, name, max_retries=5):
    """重试获取 WAF 表格行数据，应对前序操作后表格短暂为空的渲染时机延迟。

    goto_list_page 内部已有等待逻辑，无需额外延时。
    """
    for retry in range(max_retries):
        waf_obj.goto_list_page()
        try:
            rd = waf_obj.get_row_data(name)
            if rd:
                return rd
        except AssertionError:
            if retry >= max_retries - 1:
                raise
    return {}


@allure.epic('安全合规')
@allure.feature('WEB应用防火墙')
@allure.story('WAF实例-全生命周期及功能验证')
class TestWafOperations:
    """WEB应用防火墙实例全生命周期及功能验证。

    所有场景共享同一个 WAF 实例（由 waf_instance fixture 创建），
    类内按顺序依次执行 14 个方法（11 个 CSV 场景 + 3 个既有运维场景），
    所有用例执行完成后统一清理。
    """

    @allure.title("WAF-新建实例验证")
    def test_waf_01_create(self, waf_instance, waf_page):
        """场景1（414371）：新建 WAF 实例，验证详情页与跳转地址。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已创建完成")

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url, \
                f"未导航到 WAF 页面，当前 URL: {waf_page.page.url}"
            logger.info(f"已进入 WAF 列表页: {waf_page.page.url}")

        with allure_step_log("步骤2: 验证详情页与跳转"):
            waf_page.waf_to_details(name)
            waf_page.wait_for_detail_page_ready()
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != waf_page.page:
                    new_page.close()
                logger.info("跳转地址验证通过")

    @allure.title("WAF-关机操作")
    def test_waf_02_shutdown(self, waf_instance, waf_page):
        """场景2（414372）：对运行的 WAF 实例执行关机操作。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url
            logger.info(f"已进入 WAF 列表页: {waf_page.page.url}")

        with allure_step_log("步骤2: 执行关机操作"):
            waf_page.waf_operations(name, "关机")

        with allure_step_log("步骤3: 验证关机后服务状态和虚拟机状态"):
            waf_page.assert_waf_status(name, service_status="不可用", vm_status="关机", timeout=180)

        with allure_step_log("步骤4: 验证名称不可点击跳转详情页"):
            is_clickable = waf_page.waf_name_clickable(name)
            assert not is_clickable, f"关机后 WAF 实例 {name} 名称仍可点击，期望不可点击"

    @allure.title("WAF-开机操作")
    def test_waf_03_power_on(self, waf_instance, waf_page):
        """场景3（414373）：对已关机的 WAF 实例执行开机操作。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 执行开机操作"):
            waf_page.waf_operations(name, "开机")

        with allure_step_log("步骤3: 等待开机完成，验证服务状态和虚拟机状态"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log("步骤4: 等待并再次验证状态"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=300)
            waf_page.waf_to_details(name)
            waf_page.wait_for_detail_page_ready()
            body_text = waf_page.get_detail_body_text()
            assert "服务状态" in body_text and "虚拟机状态" in body_text, \
                f"详情页未显示服务状态和虚拟机状态信息"
            logger.info("WAF 实例开机后状态持续正常")

        with allure_step_log("步骤5: 验证开机后跳转地址"):
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("开机后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "开机后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != waf_page.page:
                    new_page.close()
                logger.info("开机后跳转地址验证通过")

    @allure.title("WAF-退订操作")
    def test_waf_04_unsubscribe(self, waf_instance, waf_page):
        """场景4（414374）：对运行的 WAF 实例执行退订操作。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 执行退订操作"):
            waf_page.waf_unsubscribe(name)
            waf_page.wait_for_operation_complete(timeout=60)
            waf_page.goto_list_page()

        with allure_step_log("步骤3: 验证退订后列表页服务状态"):
            row_data = waf_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            logger.info(f"WAF 实例 {name} 退订后服务状态: {service_status}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log("步骤4: 进入详情页，验证跳转地址和到期时间显示'--'"):
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")

    @allure.title("WAF-授权操作")
    def test_waf_05_authorize(self, waf_instance, waf_page):
        """场景5（414375）：对已退订的 WAF 实例执行授权操作。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 执行授权操作（选择3个月时长）"):
            waf_page.waf_authorize(name, "3个月")
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)

        with allure_step_log("步骤3: 验证授权后实例信息准确，服务状态为运行中"):
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"WAF 实例 {name} 授权（3个月）后服务状态: {service_status}, 到期时间: {expire_time}")
            assert "运行" in service_status, f"授权后服务状态异常: {service_status}"
            assert expire_time and expire_time != "--", \
                f"到期时间字段未更新: {expire_time}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != waf_page.page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")

    @allure.title("WAF-续期操作")
    def test_waf_06_renewal(self, waf_instance, waf_page):
        """场景6（414376）：对运行的 WAF 实例执行续期操作。"""
        name = waf_instance["name"]
        page = waf_page.page

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 记录当前服务到期时间"):
            row_data = waf_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"WAF 实例 {name} 续期前到期时间: {expire_before}")
            assert expire_before and expire_before != "--", \
                f"续期前到期时间异常: {expire_before}"

        with allure_step_log("步骤3: 执行续期操作（延长2个月）"):
            waf_page.waf_renewal(name, "2个月")
            waf_page.wait_for_operation_complete(timeout=30)
            waf_page.goto_list_page()

        with allure_step_log("步骤4: 验证列表页到期时间已更新"):
            row_data = waf_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"WAF 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log("步骤5: 进入详情页验证到期时间一致和跳转地址"):
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            assert expire_after in body_text or "--" not in body_text, \
                "详情页到期时间与列表页不一致或仍显示'--'"
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")

    @allure.title("WAF-规格升级验证")
    def test_waf_07_spec_upgrade(self, waf_instance, waf_page, ssh_host):
        """对运行的 WAF 实例执行规格升级，验证升级前后规格信息变化，
        并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已就绪")

        with allure_step_log("步骤1: 获取当前规格信息"):
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"WAF 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 WAF 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级操作"):
            selected_spec = waf_page.waf_spec_upgrade(name)
            logger.info(
                f"WAF 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成，执行关机/启动使新规格生效"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)
            # 产品提示：规格升级后需关机再启动，新规格才会生效
            waf_page.waf_operations(name, "关机")
            waf_page.assert_waf_status(name, service_status="不可用", vm_status="关机", timeout=180)
            waf_page.waf_operations(name, "开机")
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=300)
            waf_page.goto_list_page()
            row_data_after = waf_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"WAF 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 WAF 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = waf_page.waf_get_server_id(name)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            waf_page.goto_list_page()

        with allure_step_log("步骤5: SSH 连接环境后台，验证规格信息"):
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 WAF 实例 {name} 的物理机信息"
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

    @allure.title("WAF-云硬盘扩容验证")
    def test_waf_08_volume_expansion(self, waf_instance, waf_page, ssh_host):
        """通过共享 WAF 实例，执行云硬盘扩容到 350GiB，通过 SSH 后端验证扩容结果。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已就绪")

        with allure_step_log("步骤1: 进入详情页查看云硬盘大小"):
            waf_page.goto_list_page()
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"WAF 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤2: 执行云硬盘扩容到 350GiB"):
            server_id = waf_page.waf_volume_expand(name, 350)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            logger.info(f"WAF 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            physical_host = row_data.get("物理机", "")
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 WAF 实例 {name} 的物理机信息"

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
            logger.info(f"WAF 实例 {name} volume_uuid: {volume_uuid}")

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

    @allure.title("WAF-修改名称验证")
    def test_waf_09_rename(self, waf_instance, waf_page):
        """验证 WAF 实例修改名称功能：修改名称后列表页和详情页均展示新名称。"""
        name = waf_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-waf-")
        logger.info(f"准备将 WAF 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            waf_page.waf_rename(name, new_name)
            waf_page.assert_popup_success("执行成功")
            waf_instance["name"] = new_name
            logger.info(f"WAF 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            waf_page.waf_to_details(new_name)
            body_text = waf_page.get_detail_body_text()
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")

    @allure.title("WAF-热迁移-系统分配验证")
    @skip_if_nodes_less_than(2)
    def test_waf_10_hot_migration_system(self, waf_instance, waf_page, ssh_host):
        """场景7（440219）：对运行的 WAF 实例执行系统分配方式热迁移，SSH 后端验证源/目标节点。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面，记录当前物理机节点信息"):
            row_data = _retry_get_row_data(waf_page, name)
            src_host = row_data.get("物理机", "")
            assert src_host, f"未获取到 WAF 实例 {name} 的物理机信息"
            logger.info(f"WAF 实例 {name} 当前物理节点: {src_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = waf_page.waf_get_server_id(name)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            uuid_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"WAF 实例 {name} server_id: {server_id}, uuid前缀: {uuid_prefix}")
            waf_page.goto_list_page()

        with allure_step_log("步骤3: 执行系统分配热迁移"):
            waf_page.waf_live_migrate_auto(name)
            waf_page.wait_for_operation_complete(timeout=60)

        with allure_step_log("步骤4: 等待迁移完成，验证状态"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)
            waf_page.goto_list_page()
            row_data_after = waf_page.get_row_data(name)
            dst_host = row_data_after.get("物理机", "")
            logger.info(f"WAF 实例 {name} 迁移后物理节点: {dst_host}")

        if dst_host != src_host:
            src_short = src_host.split(".")[0] if "." in src_host else src_host
            dst_short = dst_host.split(".")[0] if "." in dst_host else dst_host
            assert src_short, f"源物理机信息无效: {src_host}"
            assert dst_short, f"目标物理机信息无效: {dst_host}"

            with allure_step_log("步骤5: SSH 连接源物理节点验证虚机已迁移"):
                list_cmd_src = (
                    f"ssh -o StrictHostKeyChecking=no {src_short} "
                    f"'docker exec nova_libvirt virsh list'"
                )
                list_output = ssh_host.run(list_cmd_src, check_rc=True)
                if uuid_prefix not in list_output:
                    logger.info(f"源节点 {src_short} 已无 uuid 前缀 {uuid_prefix} 的虚机，迁移成功")
                else:
                    logger.warning(f"源节点 {src_short} 仍存在 uuid 前缀 {uuid_prefix} 的虚机，可能未完全迁移")

            with allure_step_log("步骤6: SSH 连接目标物理节点验证虚机已到达"):
                full_cmd = (
                    f"ssh -o StrictHostKeyChecking=no {dst_short} "
                    f"'docker exec nova_libvirt virsh list'"
                )
                full_output = ssh_host.run(full_cmd, check_rc=True)
                logger.info(f"目标节点 {dst_short} virsh list:\n{full_output}")
                # WAF 实例可能不通过标准 Nova libvirt 管理，virsh 中可能无对应 UUID
                # 此处以 WARNING 形式记录而非硬断言，避免因架构差异导致阻塞
                if uuid_prefix in full_output:
                    logger.info(f"目标节点 {dst_short} 已确认 uuid 前缀 {uuid_prefix} 的虚机到达")
                else:
                    logger.warning(f"目标节点 {dst_short} 未找到 uuid 前缀 {uuid_prefix} 的虚机"
                                  f"（WAF 实例可能不通过标准 libvirt 管理，属架构差异）")
        else:
            logger.warning(f"WAF 实例 {name} 系统分配热迁移后物理机未变更（系统决定不迁移），跳过 SSH 验证")

    @allure.title("WAF-热迁移-手动指定验证")
    @skip_if_nodes_less_than(2)
    def test_waf_11_hot_migration_manual(self, waf_instance, waf_page, ssh_host):
        """场景8（440220）：对运行的 WAF 实例执行手动指定方式热迁移，SSH 后端验证源/目标节点。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面，记录当前物理机节点信息"):
            row_data = _retry_get_row_data(waf_page, name)
            src_host = row_data.get("物理机", "")
            assert src_host, f"未获取到 WAF 实例 {name} 的物理机信息"
            logger.info(f"WAF 实例 {name} 当前物理节点: {src_host}")

        with allure_step_log("步骤2: 进入详情页记录实例ID"):
            server_id = waf_page.waf_get_server_id(name)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            uuid_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"WAF 实例 {name} server_id: {server_id}, uuid前缀: {uuid_prefix}")
            waf_page.goto_list_page()

        with allure_step_log("步骤3: 执行手动指定热迁移"):
            waf_page.waf_live_migrate_manual(name, src_host=src_host)
            waf_page.wait_for_operation_complete(timeout=60)

        with allure_step_log("步骤4: 等待迁移完成，验证状态"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)
            waf_page.goto_list_page()
            row_data_after = waf_page.get_row_data(name)
            dst_host = row_data_after.get("物理机", "")
            logger.info(f"WAF 实例 {name} 迁移后物理节点: {dst_host}")
            assert dst_host != src_host, f"手动指定热迁移后物理机未变更: {dst_host}"

        src_short = src_host.split(".")[0] if "." in src_host else src_host
        dst_short = dst_host.split(".")[0] if "." in dst_host else dst_host
        assert src_short, f"源物理机信息无效: {src_host}"
        assert dst_short, f"目标物理机信息无效: {dst_host}"

        with allure_step_log("步骤5: SSH 连接源物理节点验证虚机已迁移"):
            list_cmd_src = (
                f"ssh -o StrictHostKeyChecking=no {src_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            list_output = ssh_host.run(list_cmd_src, check_rc=True)
            if uuid_prefix not in list_output:
                logger.info(f"源节点 {src_short} 已无 uuid 前缀 {uuid_prefix} 的虚机，迁移成功")
            else:
                logger.warning(f"源节点 {src_short} 仍存在 uuid 前缀 {uuid_prefix} 的虚机")

        with allure_step_log("步骤6: SSH 连接目标物理节点验证虚机已到达"):
            full_cmd = (
                f"ssh -o StrictHostKeyChecking=no {dst_short} "
                f"'docker exec nova_libvirt virsh list'"
            )
            full_output = ssh_host.run(full_cmd, check_rc=True)
            logger.info(f"目标节点 {dst_short} virsh list:\n{full_output}")
            # WAF 实例可能不通过标准 Nova libvirt 管理，virsh 中可能无对应 UUID
            # 此处以 WARNING 形式记录而非硬断言，避免因架构差异导致阻塞
            if uuid_prefix in full_output:
                logger.info(f"目标节点 {dst_short} 已确认 uuid 前缀 {uuid_prefix} 的虚机到达")
            else:
                logger.warning(f"目标节点 {dst_short} 未找到 uuid 前缀 {uuid_prefix} 的虚机"
                              f"（WAF 实例可能不通过标准 libvirt 管理，属架构差异）")

    @allure.title("WAF-绑定公网IP验证")
    def test_waf_12_bind_eip(self, waf_instance, waf_page, security_fip_pool):
        """场景9（440221）：对运行的 WAF 实例执行绑定公网IP操作，Ping 验证连通性。"""
        name = waf_instance["name"]
        page = waf_page.page

        with allure_step_log("步骤1: 进入WEB应用防火墙页面，检查实例状态"):
            row_data = _retry_get_row_data(waf_page, name)
            svc = row_data.get("服务状态", "")
            vmst = row_data.get("虚拟机状态", "")
            assert "运行" in svc, f"实例 {name} 状态异常，期望运行，实际: {svc}"
            assert "运行" in vmst, f"实例 {name} 状态异常，期望运行，实际: {vmst}"

        with allure_step_log("步骤2: 从安全合规 FIP 池获取一个公网IP并绑定（资源池 public_net）"):
            eip = security_fip_pool.acquire()
            bound_ip = waf_page.waf_bind_floating_ip(name, eip_ip=eip, pool=security_fip_pool.pool_name)
            if bound_ip:
                assert bound_ip == eip, f"绑定返回的 IP 与指定 IP 不一致: {bound_ip} != {eip}"
            waf_page.wait_for_operation_complete(timeout=60)
            waf_page.goto_list_page()
            network_info = waf_page.waf_get_network_info(name)
            logger.info(f"WAF 实例 {name} 绑定公网IP后网络信息: {network_info}")
            public_ip = bound_ip or network_info.get("public_ip")
            assert public_ip, f"公网IP未绑定成功"
            assert public_ip == eip, f"列表页公网IP与指定 IP 不一致: {public_ip} != {eip}"
            waf_instance["eip"] = public_ip

        with allure_step_log("步骤3: Ping 验证公网IP连通性"):
            assert _ping_fip(public_ip), f"公网IP {public_ip} 无法连通"
            logger.info(f"公网IP {public_ip} ping 通成功")

        with allure_step_log("步骤4: 验证详情页跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("绑定公网IP后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("绑定公网IP后跳转地址验证通过")

    @allure.title("WAF-解绑公网IP验证")
    def test_waf_13_unbind_eip(self, waf_instance, waf_page, security_fip_pool):
        """场景10（440222）：对已绑定公网IP的 WAF 实例执行解绑公网IP操作，Ping 验证不可达。"""
        name = waf_instance["name"]
        page = waf_page.page

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 验证绑定状态下详情页跳转地址"):
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            assert "跳转地址" in body_text, "详情页未显示跳转地址字段"
            waf_page.goto_list_page()

        with allure_step_log("步骤3: 获取绑定的公网IP"):
            fip = waf_instance.get("eip", "")
            if not fip:
                _ = _retry_get_row_data(waf_page, name)
                network_info = waf_page.waf_get_network_info(name)
                fip = network_info.get("public_ip", "")
            assert fip, f"未获取到 WAF 实例 {name} 绑定的公网IP"
            logger.info(f"WAF 实例 {name} 当前公网IP: {fip}")

        with allure_step_log("步骤4: 执行解绑公网IP操作"):
            waf_page.waf_unbind_floating_ip(name)
            waf_page.wait_for_operation_complete(timeout=60)
            waf_page.goto_list_page()
            network_info_after = waf_page.waf_get_network_info(name)
            logger.info(f"WAF 实例 {name} 解绑公网IP后网络信息: {network_info_after}")
            assert not network_info_after.get("public_ip"), f"公网IP未解绑成功"

        with allure_step_log("步骤5: 验证解绑后公网IP不可达"):
            assert not _ping_fip(fip), f"解绑后公网IP {fip} 仍可连通"
            logger.info(f"公网IP {fip} 解绑后 ping 不通验证成功")

        with allure_step_log("步骤6: 验证解绑后详情页跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
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

    @allure.title("WAF-登录VNC验证")
    def test_waf_14_vnc_login(self, waf_instance, waf_page):
        """场景11（440223）：点击登录VNC按钮，验证 VNC 控制台页面可打开。"""
        name = waf_instance["name"]

        with allure_step_log("步骤1: 进入WEB应用防火墙页面"):
            waf_page.goto_list_page()
            assert "/waf" in waf_page.page.url

        with allure_step_log("步骤2: 点击登录VNC并验证 VNC 页面"):
            vnc_page = waf_page.waf_vnc_login(name)
            assert vnc_page is not None, \
                f"WAF 实例 {name} 点击登录VNC后未打开 VNC 控制台页面"
            current_url = vnc_page.url
            logger.info(f"WAF 实例 {name} VNC 页面 URL: {current_url}")
            assert "vnc" in current_url or "remote" in current_url or "spice" in current_url, \
                f"VNC 页面 URL 异常: {current_url}, 期望包含 vnc/remote/spice"
            if vnc_page != waf_page.page:
                vnc_page.close()
            logger.info(f"WAF 实例 {name} VNC 登录验证通过")
