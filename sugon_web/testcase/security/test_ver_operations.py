import re
import time

import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import only_stor


@allure.epic('安全合规')
@allure.feature('日志审计VER')
@allure.story('VER实例-全生命周期操作验证')
class TestVerOperations:

    @allure.title("VER-新建实例-全生命周期验证")
    @only_stor("xbd")
    def test_ver_create_lifecycle_shutdown_boot_jump(self, ver_instance, ver_page):
        """通过 fixture 获取共享 VER 实例，覆盖跳转验证、关机/启动、再验证全流程。"""
        name = ver_instance["name"]
        page = ver_page.page
        logger.info(f"VER 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入日志审计列表页并验证跳转地址"):
            ver_page.goto_list_page()
            ver_page.ver_to_details(name)
            page.wait_for_timeout(30000)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning(f"VER 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                # ver_open_jump_address 已通过页面内容验证，此处仅确认非错误页面
                if new_page != page:
                    new_page.close()
                logger.info(f"VER 实例 {name} 跳转地址验证通过")
            ver_page.goto_list_page()

        with allure_step_log(f"步骤2: VER 实例 {name} 关机"):
            ver_page.ver_operations(name, "关机")
            ver_page.assert_ver_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = ver_page.ver_name_clickable(name)
            assert not is_clickable, f"关机后 VER 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤3: VER 实例 {name} 启动"):
            ver_page.goto_list_page()
            ver_page.ver_operations(name, "开机")
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤4: 开机后等待并再次验证实例 {name} 状态"):
            time.sleep(60)
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=120)
            logger.info(f"开机后等待 2 分钟让 VER 服务就绪...")
            time.sleep(120)

        with allure_step_log(f"步骤5: 再次验证实例 {name} 跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning(f"VER 实例 {name} 再次跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                # ver_open_jump_address 已通过页面内容验证，此处仅确认非错误页面
                if new_page != page:
                    new_page.close()
                logger.info(f"VER 实例 {name} 再次跳转地址验证通过")
            ver_page.goto_list_page()

        logger.info(f"场景一完成，实例 {name} 保留供后续场景复用")

    @allure.title("VER-退订-授权-续期生命周期操作")
    @only_stor("xbd")
    def test_ver_unsubscribe_authorize_renew(self, ver_instance, ver_page):
        """通过 fixture 获取共享 VER 实例执行退订 → 授权（3个月）→
        续期（2个月）的全生命周期操作，验证到期时间更新和跳转地址可用性。"""
        name = ver_instance["name"]
        page = ver_page.page
        logger.info(f"VER 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入实例详情页查看信息"):
            ver_page.ver_to_details(name)
            body_text = ver_page.page.inner_text("body")
            logger.info("详情页信息已获取")
            ver_page.goto_list_page()

        with allure_step_log(f"步骤2: 验证跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                # ver_open_jump_address 已通过页面内容验证，此处仅确认非错误页面
                if new_page != page:
                    new_page.close()
                logger.info("跳转地址验证通过")
            ver_page.goto_list_page()

        with allure_step_log(f"步骤3: 执行退订操作"):
            ver_page.ver_unsubscribe(name)
            ver_page.wait_for_operation_complete(timeout=60)
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"VER 实例 {name} 退订后状态: 服务={service_status}, 到期时间={expire_time}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log(f"步骤4: 验证退订后详情页信息"):
            ver_page.ver_to_details(name)
            body_text = ver_page.page.inner_text("body")
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")
            ver_page.goto_list_page()

        with allure_step_log(f"步骤5: 执行授权操作（选择3个月时长）"):
            ver_page.ver_authorize(name, "3个月")
            row_data = ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=120)
            expire_time_after_auth = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time_after_auth = v
                    break
            logger.info(f"DEBUG row_data keys: {list(row_data.keys())}")
            logger.info(f"VER 实例 {name} 授权（3个月）完成，到期时间: {expire_time_after_auth}")
            assert expire_time_after_auth and expire_time_after_auth != "--", \
                f"到期时间字段未更新: {expire_time_after_auth}"

        with allure_step_log(f"步骤6: 进入详情页验证授权后跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                # ver_open_jump_address 已通过页面内容验证，此处仅确认非错误页面
                if expire_time_after_auth and expire_time_after_auth != "--":
                    ver_page.verify_jump_page_license_expire(new_page, expire_time_after_auth)
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")
            ver_page.goto_list_page()

        with allure_step_log(f"步骤7: 执行续期操作（延长2个月）"):
            row_data = ver_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"VER 实例 {name} 续期前到期时间: {expire_before}")
            ver_page.ver_renewal(name, "2个月")
            ver_page.wait_for_operation_complete(timeout=30)
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"VER 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log(f"步骤8: 进入详情页验证续期后到期时间和跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                if expire_after and expire_after != "--":
                    ver_page.verify_jump_page_license_expire(new_page, expire_after)
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            detail_expire = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    detail_expire = v
                    break
            assert detail_expire and detail_expire != "--", \
                f"详情页到期时间异常: {detail_expire}"
            logger.info(f"VER 实例 {name} 续期后验证通过，到期时间: {detail_expire}")

        logger.info(f"场景二完成，实例 {name} 保留供后续场景复用")

    @allure.title("VER-规格升级验证")
    @only_stor("xbd")
    def test_ver_spec_upgrade(self, ver_instance, ver_page, ssh_host):
        """通过 fixture 获取共享 VER 实例执行规格升级，
        验证升级前后规格信息变化，并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""
        name = ver_instance["name"]
        page = ver_page.page
        logger.info(f"VER 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 获取当前规格信息"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            physical_host = row_data.get("物理机", "")
            logger.info(f"VER 实例 {name} 当前规格: {current_spec}, 物理节点: {physical_host}")
            assert current_spec, f"未获取到 VER 实例 {name} 的规格信息"

        with allure_step_log(f"步骤2: 执行规格升级操作"):
            selected_spec = ver_page.ver_spec_upgrade(name)
            logger.info(
                f"VER 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log(f"步骤3: 等待规格升级完成，验证状态与规格变更"):
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=600)
            ver_page.goto_list_page()
            row_data_after = ver_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"VER 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 VER 实例 {name} 升级后的规格信息"

        with allure_step_log(f"步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = ver_page.ver_get_server_id(name)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            ver_page.goto_list_page()

        with allure_step_log(f"步骤5: SSH 连接环境后台，验证规格信息"):
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

        logger.info(f"规格升级完成，实例 {name} 由 fixture 自动清理")

    @allure.title("VER-云硬盘扩容验证")
    @only_stor("xbd")
    def test_ver_volume_expansion(self, ver_instance, ver_page, ssh_host):
        """通过 fixture 获取共享 VER 实例，执行云硬盘从 300GiB 扩容到 350GiB，
        通过 SSH 后端验证扩容结果。"""
        name = ver_instance["name"]
        page = ver_page.page
        logger.info(f"VER 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 进入日志审计页面并查看云硬盘大小"):
            ver_page.goto_list_page()
            ver_page.ver_to_details(name)
            body_text = ver_page.page.inner_text("body")
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"VER 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log(f"步骤2: 执行云硬盘扩容（300GiB → 350GiB）"):
            server_id = ver_page.ver_volume_expand(name, 350)
            assert server_id, f"未提取到 VER 实例 {name} 的 server_id"
            logger.info(f"VER 实例 {name} server_id: {server_id}")

        with allure_step_log(f"步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            ver_page.goto_list_page()
            row_data = ver_page.get_row_data(name)
            physical_host = row_data.get("物理机", "")
            host_short = physical_host.split(".")[0] if physical_host else ""
            assert host_short, f"未获取到 VER 实例 {name} 的物理机信息"

            cmd = f"ssh -o StrictHostKeyChecking=no {host_short} 'scli guest show {server_id}'"
            output = ssh_host.run(cmd, check_rc=True)
            logger.info(f"SSH 执行 {cmd} 输出:\n{output}")

            size_match = re.search(r'"size"\s*:\s*(\d+)', output)
            assert size_match is not None, \
                f"scli guest show 输出中未找到 volume size, 输出前500字符: {output[:500]}"
            actual_size = int(size_match.group(1))
            logger.info(f"scli guest show 解析结果: size={actual_size}GiB")

            assert actual_size == 350, \
                f"云硬盘大小不匹配: scli返回={actual_size}GiB, 期望=350GiB"
            logger.info("云硬盘扩容 SSH 后端验证通过: 350GiB")

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

        logger.info(f"云硬盘扩容完成，实例 {name} 由 fixture 自动清理")

    @allure.title("VER-实例-修改名称验证")
    @only_stor("xbd")
    def test_ver_rename(self, ver_instance, ver_page):
        """验证 VER 实例修改名称功能：
        修改名称后列表页和详情页均展示新名称。"""
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
            body_text = ver_page.page.inner_text("body")
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")
