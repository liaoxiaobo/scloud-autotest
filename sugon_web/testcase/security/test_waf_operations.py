from sugon_web.testcase.security._security_helpers import wait_backend_volume_size
import re

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('安全合规')
@allure.feature('WEB应用防火墙')
@allure.story('WAF实例-生命周期与运维操作验证')
class TestWafOperations:
    """WEB应用防火墙实例生命周期与运维操作验证。

    所有场景共享同一个 WAF 实例（由 waf_instance fixture 创建），
    类内按顺序依次执行 5 个场景，所有用例执行完成后统一清理。
    """

    @allure.title("WAF-新建实例生命周期验证")
    def test_waf_create_lifecycle(self, waf_instance, waf_page):
        """场景1：新建 WEB应用防火墙WAF 实例，覆盖关机/启动/跳转地址验证全流程。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已创建完成")

        with allure_step_log(f"步骤1: 验证详情页跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning(f"WAF 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != waf_page.page:
                    new_page.close()
                logger.info(f"WAF 实例 {name} 跳转地址验证通过")
            waf_page.goto_list_page()

        with allure_step_log(f"步骤2: WAF实例 {name} 关机"):
            waf_page.waf_operations(name, "关机")
            waf_page.assert_waf_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = waf_page.waf_name_clickable(name)
            assert not is_clickable, f"关机后 WAF 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤3: WAF实例 {name} 开机"):
            waf_page.waf_operations(name, "开机")
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤4: 开机后再次验证实例 {name} 状态"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤5: 再次验证实例 {name} 跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning(f"WAF 实例 {name} 再次跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != waf_page.page:
                    new_page.close()
                logger.info(f"WAF 实例 {name} 再次跳转地址验证通过")
            waf_page.goto_list_page()

    @allure.title("WAF-退订-授权-续期生命周期操作")
    def test_waf_unsubscribe_authorize_renew(self, waf_instance, waf_page):
        """场景2：通过共享 WAF 实例执行退订 -> 授权（3个月）-> 续期（2个月）的全生命周期操作。"""
        name = waf_instance["name"]
        page = waf_page.page
        logger.info(f"WAF 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入实例详情页查看信息"):
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            logger.info("详情页信息已获取")
            waf_page.goto_list_page()

        with allure_step_log(f"步骤2: 验证跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("跳转地址验证通过")
            waf_page.goto_list_page()

        with allure_step_log(f"步骤3: 执行退订操作"):
            waf_page.waf_unsubscribe(name)
            waf_page.wait_for_operation_complete(timeout=60)
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"WAF 实例 {name} 退订后状态: 服务={service_status}, 到期时间={expire_time}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log(f"步骤4: 验证退订后详情页信息"):
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")
            waf_page.goto_list_page()

        with allure_step_log(f"步骤5: 执行授权操作（选择3个月时长）"):
            waf_page.waf_authorize(name, "3个月")
            waf_page.wait_for_operation_complete(timeout=60)
            row_data = waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)
            expire_time_after_auth = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time_after_auth = v
                    break
            logger.info(f"DEBUG row_data keys: {list(row_data.keys())}")
            logger.info(f"WAF 实例 {name} 授权（3个月）完成，到期时间: {expire_time_after_auth}")
            assert expire_time_after_auth and expire_time_after_auth != "--", \
                f"到期时间字段未更新: {expire_time_after_auth}"

        with allure_step_log(f"步骤6: 进入详情页验证授权后跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")
            waf_page.goto_list_page()

        with allure_step_log(f"步骤7: 执行续期操作（延长2个月）"):
            row_data = waf_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"WAF 实例 {name} 续期前到期时间: {expire_before}")
            waf_page.waf_renewal(name, "2个月")
            waf_page.wait_for_operation_complete(timeout=30)
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"WAF 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log(f"步骤8: 进入详情页验证续期后到期时间和跳转地址"):
            waf_page.waf_to_details(name)
            new_page = waf_page.waf_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            detail_expire = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    detail_expire = v
                    break
            assert detail_expire and detail_expire != "--", \
                f"详情页到期时间异常: {detail_expire}"
            logger.info(f"WAF 实例 {name} 续期后验证通过，到期时间: {detail_expire}")

    @allure.title("WAF-规格升级验证")
    def test_waf_spec_upgrade(self, waf_instance, waf_page, ssh_host):
        """场景3：通过共享 WAF 实例执行规格升级，验证升级前后规格信息变化，
        并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 获取当前规格信息"):
            waf_page.goto_list_page()
            row_data = waf_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"WAF 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 WAF 实例 {name} 的规格信息"

        with allure_step_log(f"步骤2: 执行规格升级操作"):
            selected_spec = waf_page.waf_spec_upgrade(name)
            logger.info(
                f"WAF 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log(f"步骤3: 等待规格升级完成，验证状态与规格变更"):
            waf_page.assert_waf_status(name, service_status="运行", vm_status="运行", timeout=600)
            waf_page.goto_list_page()
            row_data_after = waf_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"WAF 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 WAF 实例 {name} 升级后的规格信息"

        with allure_step_log(f"步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = waf_page.waf_get_server_id(name)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            waf_page.goto_list_page()

        with allure_step_log(f"步骤5: SSH 连接环境后台，验证规格信息"):
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
    def test_waf_volume_expansion(self, waf_instance, waf_page, ssh_host):
        """场景4：通过共享 WAF 实例，执行云硬盘扩容到 350GiB，
        通过 SSH 后端验证扩容结果。"""
        name = waf_instance["name"]
        logger.info(f"WAF 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入详情页查看云硬盘大小"):
            waf_page.goto_list_page()
            waf_page.waf_to_details(name)
            body_text = waf_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"WAF 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log(f"步骤2: 执行云硬盘扩容到 350GiB"):
            server_id = waf_page.waf_volume_expand(name, 350)
            assert server_id, f"未提取到 WAF 实例 {name} 的 server_id"
            logger.info(f"WAF 实例 {name} server_id: {server_id}")

        with allure_step_log(f"步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
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
    def test_waf_rename(self, waf_instance, waf_page):
        """场景5：验证 WAF 实例修改名称功能：
        修改名称后列表页和详情页均展示新名称。"""
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
