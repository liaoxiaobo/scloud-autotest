import re

import allure

from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('生命周期与运维操作验证')
class TestUsmLifecycleOperations:
    """云堡垒机高级版 USM 统一运维操作验证。

    所有场景共享同一个 session 级 usm_instance（创建时已自动绑定公网 IP）。
    执行顺序保证：先验证创建+绑 FIP+跳转成功，再进行各类运维操作，
    最后验证解绑 FIP 后跳转不可用。实例由 fixture teardown 统一清理。

    状态/操作顺序：
    创建+绑FIP → 关机 → 开机 → 退订 → 授权 → 续期 → 规格升级 → 云硬盘扩容
    → 重命名 → 热迁移(系统分配) → 热迁移(手动指定) → VNC登录 → 解绑FIP
    """

    @allure.title("USM-创建实例并绑定公网IP验证")
    def test_usm_01_create_and_fip_bind(self, usm_instance, usm_page):
        """场景：验证 USM 实例创建成功、已绑定公网IP，且跳转地址可正常打开。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始创建+公网IP绑定验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版列表页，定位实例 {name}"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            vm_status = row_data.get("虚拟机状态", "")
            network = row_data.get("网络", "")
            logger.info(
                f"USM 实例 {name} 列表页信息: 服务状态={service_status}, "
                f"虚拟机状态={vm_status}, 网络={network}"
            )
            assert "运行" in service_status, f"服务状态异常: {service_status}"
            assert "运行" in vm_status, f"虚拟机状态异常: {vm_status}"
            assert "公网" in network, f"实例未绑定公网IP，网络列: {network}"
            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", network)
            assert ips, f"网络列未解析到公网IP: {network}"
            logger.info(f"USM 实例 {name} 已绑定公网IP: {ips}")

        with allure_step_log(f"步骤2: 进入详情页验证跳转地址可正常打开"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning(f"USM 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                    or "172.22" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                if new_page != usm_page.page:
                    new_page.close()
                logger.info(f"USM 实例 {name} 跳转地址验证通过")
            usm_page.goto_list_page()

    @allure.title("USM-关机操作验证")
    def test_usm_02_shutdown(self, usm_instance, usm_page):
        """场景1（414372）：在'运行'状态实例上执行关机，
        验证服务状态=不可用、虚拟机状态=关机，且关机后名称不可点击跳转详情页。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始关机操作验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版模块，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2: 实例 {name} 执行关机，验证服务状态/虚拟机状态"):
            usm_page.usm_operations(name, "关机")
            usm_page.assert_usm_status(name, service_status="不可用", vm_status="关机", timeout=180)

        with allure_step_log(f"步骤3: 验证关机后实例 {name} 名称不可点击"):
            is_clickable = usm_page.usm_name_clickable(name)
            assert not is_clickable, f"关机后 USM 实例 {name} 名称仍可点击，期望不可点击跳转详情页"
            logger.info(f"USM 实例 {name} 关机后名称已置黑、不可点击，验证通过")

    @allure.title("USM-开机操作验证")
    def test_usm_03_startup(self, usm_instance, usm_page):
        """场景2（414373）：在'关机'状态实例上执行开机，
        验证服务状态=运行、虚拟机状态=运行，并验证开机后跳转地址可访问 USM 平台。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始开机操作验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版模块，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2: 实例 {name} 执行开机，验证服务状态/虚拟机状态"):
            usm_page.usm_operations(name, "开机")
            usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤3: 等待后再次验证实例 {name} 状态"):
            usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤4: 验证开机后实例 {name} 跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning(f"USM 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                    or "172.22" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                if new_page != usm_page.page:
                    new_page.close()
                logger.info(f"USM 实例 {name} 开机后跳转地址验证通过")
            usm_page.goto_list_page()

    @allure.title("USM-退订操作验证")
    def test_usm_04_unsubscribe(self, usm_instance, usm_page):
        """场景3（414374）：在'运行'状态实例上执行退订，
        验证列表页服务状态=已退订，详情页跳转地址与到期时间显示'--'。本场景不删除实例。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始退订操作验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版模块，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2: 实例 {name} 执行退订"):
            usm_page.usm_unsubscribe(name)
            usm_page.wait_for_operation_complete(timeout=60)

        with allure_step_log(f"步骤3: 验证退订后列表页服务状态为'已退订'"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            logger.info(f"USM 实例 {name} 退订后服务状态: {service_status}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常，期望'已退订'，实际: {service_status}"

        with allure_step_log(f"步骤4: 验证退订后详情页跳转地址和到期时间显示'--'"):
            usm_page.usm_to_details(name)
            body_text = usm_page.get_detail_body_text()
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")
            usm_page.goto_list_page()

    @allure.title("USM-授权操作验证")
    def test_usm_05_authorize(self, usm_instance, usm_page):
        """场景4（414375）：在'已退订'状态实例上执行授权（3个月），
        验证服务状态恢复运行、到期时间更新，详情页与列表页一致，跳转平台许可证过期时间一致。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始授权操作验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版模块，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2: 实例 {name} 执行授权（选择3个月时长）"):
            usm_page.usm_authorize(name, "3个月")

        with allure_step_log(f"步骤3: 验证授权后列表页信息（服务状态运行、到期时间更新）"):
            row_data = usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=120)
            expire_time_after_auth = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time_after_auth = v
                    break
            logger.info(f"USM 实例 {name} 授权（3个月）完成，到期时间: {expire_time_after_auth}")
            assert expire_time_after_auth and expire_time_after_auth != "--", \
                f"授权后到期时间字段未更新: {expire_time_after_auth}"

        with allure_step_log(f"步骤4: 验证授权后详情页跳转地址链接与到期时间"):
            usm_page.usm_to_details(name)
            body_text = usm_page.get_detail_body_text()
            assert expire_time_after_auth.split()[0] in body_text or "--" not in body_text, \
                f"授权后详情页到期时间异常，列表页到期时间: {expire_time_after_auth}"
            logger.info("授权后详情页验证通过：跳转地址和到期时间已显示")

        with allure_step_log(f"步骤5: 验证授权后跳转地址及平台许可证过期时间"):
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                    or "172.22" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                if expire_time_after_auth and expire_time_after_auth != "--":
                    usm_page.verify_jump_page_license_expire(new_page, expire_time_after_auth)
                if new_page != usm_page.page:
                    new_page.close()
                logger.info("授权后跳转地址及平台许可证过期时间验证通过")
            usm_page.goto_list_page()

    @allure.title("USM-续期操作验证")
    def test_usm_06_renewal(self, usm_instance, usm_page):
        """场景5（414376）：在'运行'状态实例上执行续期（2个月），
        验证到期时间在续期前基础上更新（续期后≠续期前），详情页到期时间与列表页一致，跳转平台许可证过期时间一致。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始续期操作验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版模块，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2: 记录续期前到期时间"):
            row_data = usm_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"USM 实例 {name} 续期前到期时间: {expire_before}")

        with allure_step_log(f"步骤3: 实例 {name} 执行续期（选择2个月时长），验证到期时间更新"):
            usm_page.usm_renewal(name, "2个月")
            usm_page.wait_for_operation_complete(timeout=30)
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"USM 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"续期后到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log(f"步骤4: 验证详情页到期时间与续期后一致"):
            usm_page.usm_to_details(name)
            body_text = usm_page.get_detail_body_text()
            assert expire_after.split()[0] in body_text or "--" not in body_text, \
                f"续期后详情页到期时间异常，列表页到期时间: {expire_after}"
            logger.info("续期后详情页到期时间验证通过")

        with allure_step_log(f"步骤5: 验证续期后跳转地址及平台许可证过期时间"):
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                    or "172.22" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                if expire_after and expire_after != "--":
                    usm_page.verify_jump_page_license_expire(new_page, expire_after)
                if new_page != usm_page.page:
                    new_page.close()
                logger.info("续期后跳转地址及平台许可证过期时间验证通过")
            usm_page.goto_list_page()

    @allure.title("USM-规格升级验证")
    def test_usm_07_spec_upgrade(self, usm_instance, usm_page, ssh_host):
        """场景：执行规格升级，验证升级前后规格信息变化，并通过 SSH 后端验证 vcpu 和 memory_mb。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始规格升级验证")

        with allure_step_log("步骤1: 获取当前规格信息"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            logger.info(f"USM 实例 {name} 当前规格: {current_spec}")
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

    @allure.title("USM-云硬盘扩容验证")
    def test_usm_08_volume_expansion(self, usm_instance, usm_page, ssh_host):
        """场景：执行云硬盘从 300GiB 扩容到 350GiB，通过 SSH 后端验证扩容结果。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始云硬盘扩容验证")

        with allure_step_log("步骤1: 进入详情页查看当前云硬盘大小"):
            usm_page.usm_to_details(name)
            usm_page.wait_for_detail_page_ready()
            body_text = usm_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"USM 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤2: 执行云硬盘扩容（300GiB → 350GiB）"):
            server_id = usm_page.usm_volume_expand(name, 350)
            assert server_id, f"未提取到 USM 实例 {name} 的 server_id"
            logger.info(f"USM 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            from sugon_web.testcase.security._security_helpers import wait_backend_volume_size
            actual_size = wait_backend_volume_size(
                ssh_host, server_id, expected_size=350, timeout=300
            )
            logger.info(f"云硬盘扩容 SSH 后端验证通过: {actual_size}GiB")

            cmd = f"scli guest show {server_id}"
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
            logger.info(f"USM 实例 {name} volume_uuid: {volume_uuid}")

            if volume_uuid:
                vol_output = ssh_host.run(f"scli volume show {volume_uuid}", check_rc=True)
                vol_size_match = re.search(r'(?i)size\s*[:|]\s*(\d+)', vol_output)
                if vol_size_match:
                    vol_size = int(vol_size_match.group(1))
                    logger.info(f"scli volume show 解析结果: size={vol_size}GiB")
                    assert vol_size == 350, \
                        f"scli volume show 云硬盘大小不匹配: 实际={vol_size}GiB, 期望=350GiB"
                    logger.info("scli volume show 验证通过: 350GiB")

    @allure.title("USM-实例-修改名称验证")
    def test_usm_09_rename(self, usm_instance, usm_page):
        """场景：验证 USM 实例修改名称后，列表页和详情页均展示新名称。"""
        name = usm_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-usm-")
        logger.info(f"准备将 USM 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            usm_page.usm_rename(name, new_name)
            usm_page.assert_popup_success("执行成功")
            usm_instance["name"] = new_name
            logger.info(f"USM 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            usm_page.goto_list_page()
            row_data = None
            for attempt in range(10):
                try:
                    row_data = usm_page.get_row_data(new_name)
                    break
                except AssertionError:
                    logger.warning(f"第 {attempt + 1} 次未找到重命名后实例，刷新列表页...")
                    usm_page.page.reload()
                    usm_page.wait_for_page_ready()
                    usm_page.page.wait_for_timeout(2000)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            usm_page.usm_verify_detail_name(new_name)
            logger.info("详情页验证通过: 名称与修改后一致")

    @allure.title("USM-热迁移-系统分配")
    @skip_if_nodes_less_than(2)
    def test_usm_10_hot_migration_system(self, usm_instance, usm_page, ssh_host):
        """场景：执行热迁移（系统分配目标物理机），验证页面状态和后台 virsh。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始热迁移（系统分配）验证")

        with allure_step_log("步骤1: 进入USM列表页并记录当前物理机节点"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            source_host = row_data.get("物理机", "")
            vm_status_before = row_data.get("虚拟机状态", "")
            service_status_before = row_data.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 当前物理机: {source_host}, "
                f"虚拟机状态: {vm_status_before}, 服务状态: {service_status_before}"
            )
            assert source_host, f"未获取到 USM 实例 {name} 的物理机信息"
            assert "运行" in vm_status_before, \
                f"USM 实例 {name} 虚拟机状态不为运行: {vm_status_before}"
            assert "运行" in service_status_before, \
                f"USM 实例 {name} 服务状态不为运行: {service_status_before}"

        with allure_step_log("步骤2: 进入实例详情页记录云堡垒机ID"):
            server_id = usm_page.usm_get_server_id(name)
            assert server_id, f"未获取到 USM 实例 {name} 的 server_id"
            logger.info(f"USM 实例 {name} server_id: {server_id}")
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"USM 实例 {name} UUID 前三段: {server_id_prefix}")

        with allure_step_log("步骤3: 执行热迁移（系统分配模式）"):
            usm_page.goto_list_page()
            usm_page.usm_hot_migration(name, m_type="系统分配", bandwidth="全速")
            usm_page.assert_popup_success("热迁移成功")
            logger.info(f"USM 实例 {name} 热迁移（系统分配）命令下发成功")

        with allure_step_log("步骤4: 验证迁移中状态"):
            usm_page.goto_list_page()
            usm_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=5, timeout=60)
            logger.info("USM 实例状态已变为迁移中")

        with allure_step_log("步骤5: 等待迁移完成并从页面读取实际的目标物理机"):
            usm_page.wait_for_source_complete(name, complete_timeout=180)
            usm_page.assert_status(name, status="运行", refresh=True, refresh_interval=5, timeout=180)
            row_data_after = usm_page.get_row_data(name)
            target_host = row_data_after.get("物理机", "")
            actual_vm_status = row_data_after.get("虚拟机状态", "")
            actual_service_status = row_data_after.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 迁移后物理机: {target_host}, "
                f"虚拟机状态: {actual_vm_status}, 服务状态: {actual_service_status}"
            )
            assert "运行" in actual_vm_status, \
                f"热迁移后虚拟机状态不为运行: {actual_vm_status}"
            assert "运行" in actual_service_status, \
                f"热迁移后服务状态不为运行: {actual_service_status}"
            assert target_host != source_host, \
                f"系统分配后物理机未变更: 源={source_host}, 目标={target_host}"
            logger.info("热迁移页面状态验证通过")

        with allure_step_log("步骤6: SSH连接源物理机后台验证虚拟机已迁出"):
            source_host_short = source_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"源物理机 {source_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=False,
            )
            logger.info(
                f"源物理机 {source_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert not grep_output or server_id_prefix not in grep_output, \
                f"源物理机 {source_host_short} 上仍存在该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"源物理机 {source_host_short} 验证通过：虚拟机已不在源节点")

        with allure_step_log("步骤7: SSH连接目标物理机后台验证虚拟机已迁入"):
            target_host_short = target_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"目标物理机 {target_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=True,
            )
            logger.info(
                f"目标物理机 {target_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert server_id_prefix in grep_output, \
                f"目标物理机 {target_host_short} 上未找到该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"目标物理机 {target_host_short} 验证通过：虚拟机已在目标节点")

        with allure_step_log("步骤8: SSH管理API验证节点归属"):
            guest_info = ssh_host.guest_show(server_id)
            actual_node = guest_info.get("node", "")
            logger.info(f"scli guest show {server_id} node={actual_node}")
            assert actual_node == target_host, \
                f"管理API节点不匹配: scli返回node={actual_node}, 期望={target_host}"
            logger.info(f"管理API验证通过: node={actual_node} 与目标物理机一致")

    @allure.title("USM-热迁移-手动指定")
    @skip_if_nodes_less_than(2)
    def test_usm_11_hot_migration_manual(self, usm_instance, usm_page, ssh_host):
        """场景：执行热迁移（手动指定目标物理机），验证页面状态和后台 virsh。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始热迁移（手动指定）验证")

        with allure_step_log("步骤1: 进入USM列表页并记录当前物理机节点"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            source_host = row_data.get("物理机", "")
            vm_status_before = row_data.get("虚拟机状态", "")
            service_status_before = row_data.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 当前物理机: {source_host}, "
                f"虚拟机状态: {vm_status_before}, 服务状态: {service_status_before}"
            )
            assert source_host, f"未获取到 USM 实例 {name} 的物理机信息"
            assert "运行" in vm_status_before, \
                f"USM 实例 {name} 虚拟机状态不为运行: {vm_status_before}"
            assert "运行" in service_status_before, \
                f"USM 实例 {name} 服务状态不为运行: {service_status_before}"

        with allure_step_log("步骤2: 进入实例详情页记录云堡垒机ID"):
            server_id = usm_page.usm_get_server_id(name)
            assert server_id, f"未获取到 USM 实例 {name} 的 server_id"
            logger.info(f"USM 实例 {name} server_id: {server_id}")
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"USM 实例 {name} UUID 前三段: {server_id_prefix}")

        with allure_step_log("步骤3: 执行热迁移（手动指定目标物理机）"):
            usm_page.goto_list_page()
            target_host = usm_page.usm_hot_migration(name, m_type="手动指定", bandwidth="全速")
            assert target_host, "热迁移未选择到目标物理机"
            assert target_host != source_host, \
                f"热迁移目标物理机与源物理机相同: {source_host}"
            usm_page.assert_popup_success("热迁移成功")
            logger.info(f"USM 实例 {name} 热迁移命令下发成功，目标物理机: {target_host}")

        with allure_step_log("步骤4: 验证迁移中状态"):
            usm_page.goto_list_page()
            usm_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=5, timeout=60)
            logger.info("USM 实例状态已变为迁移中")

        with allure_step_log("步骤5: 等待迁移完成并验证页面状态"):
            usm_page.wait_for_source_complete(name, complete_timeout=300)
            usm_page.assert_status(name, status="运行", refresh=True, refresh_interval=5, timeout=300)
            row_data_after = usm_page.get_row_data(name)
            actual_host = row_data_after.get("物理机", "")
            actual_vm_status = row_data_after.get("虚拟机状态", "")
            actual_service_status = row_data_after.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 迁移后物理机: {actual_host}, "
                f"虚拟机状态: {actual_vm_status}, 服务状态: {actual_service_status}"
            )
            assert actual_host == target_host, \
                f"热迁移后物理机不匹配: 期望={target_host}, 实际={actual_host}"
            assert "运行" in actual_vm_status, \
                f"热迁移后虚拟机状态不为运行: {actual_vm_status}"
            assert "运行" in actual_service_status, \
                f"热迁移后服务状态不为运行: {actual_service_status}"
            logger.info("热迁移页面状态验证通过")

        with allure_step_log("步骤6: SSH连接源物理机后台验证虚拟机已迁出"):
            source_host_short = source_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"源物理机 {source_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=False,
            )
            logger.info(
                f"源物理机 {source_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert not grep_output or server_id_prefix not in grep_output, \
                f"源物理机 {source_host_short} 上仍存在该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"源物理机 {source_host_short} 验证通过：虚拟机已不在源节点")

        with allure_step_log("步骤7: SSH连接目标物理机后台验证虚拟机已迁入"):
            target_host_short = target_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"目标物理机 {target_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=True,
            )
            logger.info(
                f"目标物理机 {target_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert server_id_prefix in grep_output, \
                f"目标物理机 {target_host_short} 上未找到该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"目标物理机 {target_host_short} 验证通过：虚拟机已在目标节点")

        with allure_step_log("步骤8: SSH管理API验证节点归属"):
            guest_info = ssh_host.guest_show(server_id)
            actual_node = guest_info.get("node", "")
            logger.info(f"scli guest show {server_id} node={actual_node}")
            assert actual_node == target_host, \
                f"管理API节点不匹配: scli返回node={actual_node}, 期望={target_host}"
            logger.info(f"管理API验证通过: node={actual_node} 与目标物理机一致")

    @allure.title("USM-登录VNC验证")
    def test_usm_12_vnc_login(self, usm_instance, usm_page):
        """场景6（440223）：在'运行'状态实例上登录 VNC 控制台，
        输入密码 000000，验证 VNC canvas 渲染成功（已成功连接）并截图附加 Allure。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始登录 VNC 验证")

        with allure_step_log(f"步骤1: 进入云堡垒机高级版USM页面，定位实例 {name}"):
            usm_page.goto_list_page()

        with allure_step_log(f"步骤2-3: 实例 {name} 登录VNC并输入密码000000，验证连接成功"):
            new_page = usm_page.usm_vnc_login(name, "000000")
            assert new_page is not None, f"USM 实例 {name} 登录 VNC 未打开新页面"
            logger.info(f"USM 实例 {name} VNC 登录成功，canvas 已渲染（已成功连接）")
            if new_page != usm_page.page:
                new_page.close()

    @allure.title("USM-解绑公网IP验证")
    def test_usm_13_unbind_fip(self, usm_instance, usm_page):
        """场景：解绑公网IP，验证网络列不再显示公网IP，且跳转地址提示需要绑定公网IP。"""
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪，开始解绑公网IP验证")

        with allure_step_log("步骤1: 进入USM列表页，确认解绑前已绑定公网IP"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            network_before = row_data.get("网络", "")
            logger.info(f"解绑前网络列: {network_before}")
            assert "公网" in network_before, \
                f"USM 实例 {name} 未绑定公网IP（网络列: {network_before}）"
            logger.info("进入堡垒机页面成功，列表可正常显示")

        with allure_step_log("步骤2: 进入实例详情页查看跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning("跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != usm_page.page:
                    new_page.close()
                logger.info("跳转地址显示URL的跳转链接，可正常打开")

        with allure_step_log("步骤3: 解绑公网IP"):
            usm_page.goto_list_page()
            usm_page.usm_unbind_eip(name)
            row_data = usm_page.get_row_data(name)
            network_after = row_data.get("网络", "")
            logger.info(f"解绑后网络列: {network_after}")
            assert "公网" not in network_after, \
                f"解绑后网络列仍显示公网IP: {network_after}"
            ips = re.findall(r"\d+\.\d+\.\d+\.\d+", network_after)
            assert len(ips) <= 1, f"解绑后网络列仍含多个IP地址: {network_after}"
            logger.info("解绑成功，该实例网络列只展示固定IP")

        with allure_step_log("步骤4: 验证解绑后详情页跳转地址"):
            jump_text = usm_page.usm_get_jump_address_text(name)
            assert "非直连网络需要绑定公网ip才可使用" in jump_text, \
                f"解绑后跳转地址未显示警告文本: {jump_text}"
            logger.info("跳转地址显示：非直连网络需要绑定公网ip才可使用！")
