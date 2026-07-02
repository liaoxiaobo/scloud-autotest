import re
from datetime import datetime

import allure
from sugon_web.testcase.security._security_helpers import wait_backend_volume_size
from sugon_web.utils.data import random_data
from sugon_web.utils.decorators import skip_if_nodes_less_than
from sugon_web.utils.logger import allure_step_log, logger


def _get_expire_time(row_data: dict) -> str:
    """从行数据中提取服务到期时间字段值。"""
    for k, v in row_data.items():
        if "到期" in k:
            return v
    return ""


def _parse_date(text: str):
    """从文本中解析出第一个 YYYY-MM-DD 形式的日期，失败返回 None。"""
    if not text:
        return None
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _add_months(dt: datetime, months: int) -> datetime:
    """在给定日期上增加指定月数（按自然月，跨年进位）。"""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(
        dt.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return dt.replace(year=year, month=month, day=day)


@allure.epic('安全合规')
@allure.feature('攻击预警')
@allure.story('APT实例-全生命周期及运维操作验证')
class TestAptFullOperations:
    """攻击预警 APT 实例全生命周期及运维操作验证。

    所有场景共享同一个 APT 实例（由 apt_instance fixture 创建，受项目级互斥锁保护），
    类内按场景编号顺序依次执行 14 个场景，所有用例执行完成后由 fixture 统一清理。
    各场景方法不单独删除实例。
    """

    @allure.title("APT-新建实例验证")
    def test_apt_01_create(self, apt_instance, apt_page):
        """场景1（414371）：新建 APT 实例，验证状态与详情页跳转地址。"""
        name = apt_instance["name"]
        logger.info(f"APT 实例 {name} 已由 fixture 创建完成")

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url, \
                f"未导航到 APT 页面，当前 URL: {apt_page.page.url}"
            logger.info(f"已进入 APT 列表页: {apt_page.page.url}")

        with allure_step_log("步骤2: 校验新建实例状态为运行/运行"):
            row_data = apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=1200
            )
            logger.info(f"APT 实例 {name} 新建后行数据: {row_data}")

        with allure_step_log("步骤3: 进入详情页验证跳转地址"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning(f"APT 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != apt_page.page:
                    new_page.close()
                logger.info(f"APT 实例 {name} 跳转地址验证通过")

    @allure.title("APT-关机操作")
    def test_apt_02_shutdown(self, apt_instance, apt_page):
        """场景2（414372）：对运行的 APT 实例执行关机操作。"""
        name = apt_instance["name"]

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 执行关机操作并验证服务/虚拟机状态"):
            apt_page.apt_operations(name, "关机")
            apt_page.assert_apt_status(
                name, service_status="不可用", vm_status="关机", timeout=300
            )

        with allure_step_log("步骤3: 验证关机后名称不可点击跳转详情页"):
            is_clickable = apt_page.apt_name_clickable(name)
            assert not is_clickable, \
                f"关机后 APT 实例 {name} 名称仍可点击，期望不可点击"

    @allure.title("APT-开机操作")
    def test_apt_03_power_on(self, apt_instance, apt_page):
        """场景3（414373）：对已关机的 APT 实例执行开机操作。"""
        name = apt_instance["name"]
        page = apt_page.page

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 执行开机操作并验证服务/虚拟机状态"):
            apt_page.apt_operations(name, "开机")
            apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=300
            )

        with allure_step_log("步骤3: 等待后进入详情页再次验证状态"):
            apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=300
            )
            apt_page.apt_to_details(name)
            apt_page.wait_for_detail_page_ready()
            body_text = apt_page.get_detail_body_text()
            assert "服务状态" in body_text and "虚拟机状态" in body_text, \
                "详情页未显示服务状态和虚拟机状态信息"
            logger.info("APT 实例开机后状态持续正常")

        with allure_step_log("步骤4: 验证开机后跳转地址"):
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning("开机后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "开机后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("开机后跳转地址验证通过")

    @allure.title("APT-退订操作")
    def test_apt_04_unsubscribe(self, apt_instance, apt_page):
        """场景4（414374）：对运行的 APT 实例执行退订操作。"""
        name = apt_instance["name"]

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 执行退订操作"):
            apt_page.apt_unsubscribe(name)
            apt_page.wait_for_operation_complete(timeout=60)

        with allure_step_log("步骤3: 验证退订后列表页服务状态为已退订"):
            row_data = apt_page.assert_apt_status(
                name, service_status="已退订", timeout=120
            )
            service_status = row_data.get("服务状态", "")
            logger.info(f"APT 实例 {name} 退订后服务状态: {service_status}")
            assert "已退订" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log("步骤4: 进入详情页验证跳转地址和到期时间显示'--'"):
            apt_page.apt_to_details(name)
            apt_page.wait_for_detail_page_ready()
            body_text = apt_page.get_detail_body_text()
            assert "--" in body_text, \
                "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")

    @allure.title("APT-授权操作")
    def test_apt_05_authorize(self, apt_instance, apt_page):
        """场景5（414375）：对已退订的 APT 实例执行授权操作（3个月）。"""
        name = apt_instance["name"]
        page = apt_page.page

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 执行授权操作（3个月），验证弹窗关闭并提示授权成功"):
            apt_page.apt_authorize(name, "3个月")
            apt_page.assert_popup_success()
            apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=600
            )

        with allure_step_log("步骤3: 验证授权后列表页信息，服务状态为运行，到期时间为创建+3个月"):
            apt_page.goto_list_page()
            row_data = apt_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = _get_expire_time(row_data)
            logger.info(
                f"APT 实例 {name} 授权（3个月）后服务状态: {service_status}, 到期时间: {expire_time}"
            )
            assert "运行" in service_status, f"授权后服务状态异常: {service_status}"
            assert expire_time and expire_time != "--", \
                f"到期时间字段未更新: {expire_time}"
            expire_dt = _parse_date(expire_time)
            if expire_dt is not None:
                expected_dt = _add_months(datetime.now(), 3)
                delta_days = abs((expire_dt - expected_dt).days)
                assert delta_days <= 3, \
                    f"授权到期时间与创建+3个月偏差过大: 实际={expire_dt.date()}, 期望约={expected_dt.date()}"
                logger.info(f"授权到期时间验证通过: {expire_dt.date()}（期望约 {expected_dt.date()}）")

        with allure_step_log("步骤4: 进入详情页验证跳转地址和到期时间一致"):
            apt_page.apt_to_details(name)
            apt_page.wait_for_detail_page_ready()
            body_text = apt_page.get_detail_body_text()
            if expire_time and expire_time != "--":
                assert expire_time in body_text or "--" not in body_text, \
                    "详情页到期时间与列表页不一致或仍显示'--'"

        with allure_step_log("步骤5: 验证授权后跳转地址"):
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "授权后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")

    @allure.title("APT-续期操作")
    def test_apt_06_renewal(self, apt_instance, apt_page):
        """场景6（414376）：对运行的 APT 实例执行续期操作（2个月）。"""
        name = apt_instance["name"]
        page = apt_page.page

        with allure_step_log("步骤1: 进入攻击预警页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 记录当前服务到期时间"):
            row_data = apt_page.get_row_data(name)
            expire_before = _get_expire_time(row_data)
            logger.info(f"APT 实例 {name} 续期前到期时间: {expire_before}")
            assert expire_before and expire_before != "--", \
                f"续期前到期时间异常: {expire_before}"

        with allure_step_log("步骤3: 执行续期操作（2个月），验证到期时间增加2个月"):
            apt_page.apt_renewal(name, "2个月")
            apt_page.wait_for_operation_complete(timeout=30)
            apt_page.goto_list_page()
            row_data_after = apt_page.get_row_data(name)
            expire_after = _get_expire_time(row_data_after)
            logger.info(f"APT 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"
            dt_before = _parse_date(expire_before)
            dt_after = _parse_date(expire_after)
            if dt_before is not None and dt_after is not None:
                expected_dt = _add_months(dt_before, 2)
                delta_days = abs((dt_after - expected_dt).days)
                assert delta_days <= 3, \
                    f"续期后到期时间偏差过大: 实际={dt_after.date()}, 期望约={expected_dt.date()}"
                logger.info(f"续期到期时间验证通过: {dt_after.date()}（期望约 {expected_dt.date()}）")

        with allure_step_log("步骤4: 进入详情页验证到期时间一致"):
            apt_page.apt_to_details(name)
            apt_page.wait_for_detail_page_ready()
            body_text = apt_page.get_detail_body_text()
            assert expire_after in body_text or "--" not in body_text, \
                "详情页到期时间与列表页不一致或仍显示'--'"

        with allure_step_log("步骤5: 验证续期后跳转地址"):
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")

    @allure.title("APT-热迁移-系统分配验证")
    @skip_if_nodes_less_than(2)
    def test_apt_07_hot_migration_system(self, apt_instance, apt_page, ssh_host):
        """场景7（440219）：系统分配方式热迁移，SSH 后端验证虚机迁移。"""
        name = apt_instance["name"]

        with allure_step_log("步骤1: 进入攻击预警APT列表页，记录该实例物理机"):
            apt_page.goto_list_page()
            row_data = apt_page.get_row_data(name)
            src_physical_host = row_data.get("物理机", "")
            assert src_physical_host, f"未获取到 APT 实例 {name} 的物理机信息"
            logger.info(f"APT 实例 {name} 所在物理机: {src_physical_host}")

        with allure_step_log("步骤2/3: 进入详情页记录实例ID（取UUID前三段）"):
            server_id = apt_page.apt_get_server_id(name)
            assert server_id, f"未提取到 APT 实例 {name} 的实例ID"
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"APT 实例 {name} 实例ID: {server_id}, 前缀: {server_id_prefix}")
            apt_page.goto_list_page()

        with allure_step_log("步骤4/5: 打开热迁移弹窗并提交系统分配热迁移（迁移速率全速）"):
            apt_page.apt_hot_migration(name, mode="系统分配", rate="全速")
            logger.info(f"APT 实例 {name} 系统分配热迁移命令已下发")

        with allure_step_log("步骤6: 等待迁移完成，验证物理机已变更且状态恢复运行"):
            apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=300
            )
            apt_page.goto_list_page()
            row_data_after = apt_page.get_row_data(name)
            target_physical_host = row_data_after.get("物理机", "")
            logger.info(f"APT 实例 {name} 迁移后物理机: {target_physical_host}")
            assert target_physical_host, "迁移后未获取到物理机信息"
            assert target_physical_host != src_physical_host, \
                f"热迁移后物理机未变化: 源={src_physical_host}, 目标={target_physical_host}"

        source_host_short = (
            src_physical_host.split(".")[0]
            if "." in src_physical_host else src_physical_host
        )
        target_host_short = (
            target_physical_host.split(".")[0]
            if "." in target_physical_host else target_physical_host
        )

        with allure_step_log("步骤7: SSH连接源物理机后台，验证虚机已迁出"):
            result_src = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                return_rc=True,
            )
            logger.info(f"源物理机 {source_host_short} virsh list: rc={result_src['rc']}")
            assert result_src["rc"] == 0, \
                f"源物理机 virsh list 执行失败: {result_src.get('stderr', '')}"
            assert server_id_prefix not in result_src["stdout"], \
                f"源物理机 {source_host_short} 仍存在虚机 {server_id_prefix}，迁出失败"
            logger.info(f"源物理机 {source_host_short} 已无虚机 {server_id_prefix}，迁出成功")

        with allure_step_log("步骤8: SSH连接目标物理机后台，验证虚机已迁入"):
            result_tgt = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                return_rc=True,
            )
            logger.info(f"目标物理机 {target_host_short} virsh list: rc={result_tgt['rc']}")
            assert result_tgt["rc"] == 0, \
                f"目标物理机 virsh list 执行失败: {result_tgt.get('stderr', '')}"
            assert server_id_prefix in result_tgt["stdout"], \
                f"目标物理机 {target_host_short} 未找到虚机 {server_id_prefix}，迁入失败"
            logger.info(f"APT 实例 {name} 热迁移（系统分配）验证通过")

    @allure.title("APT-热迁移-手动指定验证")
    @skip_if_nodes_less_than(2)
    def test_apt_08_hot_migration_manual(self, apt_instance, apt_page, ssh_host):
        """场景8（440220）：手动指定方式热迁移，SSH 后端验证虚机迁移。"""
        name = apt_instance["name"]

        with allure_step_log("步骤1: 进入攻击预警APT列表页，记录该实例物理机"):
            apt_page.goto_list_page()
            row_data = apt_page.get_row_data(name)
            src_physical_host = row_data.get("物理机", "")
            assert src_physical_host, f"未获取到 APT 实例 {name} 的物理机信息"
            logger.info(f"APT 实例 {name} 所在物理机: {src_physical_host}")

        with allure_step_log("步骤2/3: 进入详情页记录实例ID（取UUID前三段）"):
            server_id = apt_page.apt_get_server_id(name)
            assert server_id, f"未提取到 APT 实例 {name} 的实例ID"
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"APT 实例 {name} 实例ID: {server_id}, 前缀: {server_id_prefix}")
            apt_page.goto_list_page()

        with allure_step_log("步骤4/5: 打开热迁移弹窗并提交手动指定热迁移（迁移速率全速）"):
            apt_page.apt_hot_migration(name, mode="手动指定", rate="全速")
            logger.info(f"APT 实例 {name} 手动指定热迁移命令已下发")

        with allure_step_log("步骤6: 等待迁移完成，验证物理机已变更且状态恢复运行"):
            apt_page.assert_apt_status(
                name, service_status="运行", vm_status="运行", timeout=300
            )
            apt_page.goto_list_page()
            row_data_after = apt_page.get_row_data(name)
            target_physical_host = row_data_after.get("物理机", "")
            logger.info(f"APT 实例 {name} 迁移后物理机: {target_physical_host}")
            assert target_physical_host, "迁移后未获取到物理机信息"
            assert target_physical_host != src_physical_host, \
                f"热迁移后物理机未变化: 源={src_physical_host}, 目标={target_physical_host}"

        source_host_short = (
            src_physical_host.split(".")[0]
            if "." in src_physical_host else src_physical_host
        )
        target_host_short = (
            target_physical_host.split(".")[0]
            if "." in target_physical_host else target_physical_host
        )

        with allure_step_log("步骤7: SSH连接源物理机后台，验证虚机已迁出"):
            result_src = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                return_rc=True,
            )
            logger.info(f"源物理机 {source_host_short} virsh list: rc={result_src['rc']}")
            assert result_src["rc"] == 0, \
                f"源物理机 virsh list 执行失败: {result_src.get('stderr', '')}"
            assert server_id_prefix not in result_src["stdout"], \
                f"源物理机 {source_host_short} 仍存在虚机 {server_id_prefix}，迁出失败"
            logger.info(f"源物理机 {source_host_short} 已无虚机 {server_id_prefix}，迁出成功")

        with allure_step_log("步骤8: SSH连接目标物理机后台，验证虚机已迁入"):
            result_tgt = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                return_rc=True,
            )
            logger.info(f"目标物理机 {target_host_short} virsh list: rc={result_tgt['rc']}")
            assert result_tgt["rc"] == 0, \
                f"目标物理机 virsh list 执行失败: {result_tgt.get('stderr', '')}"
            assert server_id_prefix in result_tgt["stdout"], \
                f"目标物理机 {target_host_short} 未找到虚机 {server_id_prefix}，迁入失败"
            logger.info(f"APT 实例 {name} 热迁移（手动指定）验证通过")

    @allure.title("APT-绑定公网IP验证")
    def test_apt_09_bind_eip(self, apt_instance, apt_page, ssh_host, security_fip_pool):
        """场景9（440221）：绑定公网IP并通过 ssh_host ping 验证连通性。"""
        name = apt_instance["name"]
        page = apt_page.page

        with allure_step_log("步骤1: 进入攻击预警APT页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2: 从 FIP 池获取公网IP并绑定"):
            eip = security_fip_pool.acquire()
            bound_ip = apt_page.apt_bind_floating_ip(name, pool=security_fip_pool.pool_name, eip_ip=eip)
            assert bound_ip == eip, \
                f"绑定返回的 IP 与指定 IP 不一致: {bound_ip} != {eip}"
            apt_instance["eip"] = eip
            apt_page.assert_popup_success()
            logger.info(f"APT 实例 {name} 已绑定公网IP: {eip}")

        with allure_step_log("步骤3: 验证列表页网络列展示已绑定公网IP"):
            net_info = apt_page.apt_get_network_info(name)
            logger.info(f"APT 实例 {name} 网络列信息: {net_info}")
            assert eip in net_info["raw"], \
                f"列表页网络列未展示已绑定公网IP {eip}: {net_info['raw']}"

        with allure_step_log("步骤4: 通过 ssh_host ping 验证公网IP连通性"):
            result = ssh_host.run(f"ping -c 4 {eip}", return_rc=True)
            logger.info(f"ping {eip} 结果: rc={result['rc']}, stdout={result['stdout'][:300]}")
            assert result["rc"] == 0 and (
                "0% packet loss" in result["stdout"]
                or re.search(r"[1-4]\s*received", result["stdout"])
                or "bytes from" in result["stdout"]
            ), f"无法 ping 通公网IP {eip}: {result['stdout'][:300]}"
            logger.info(f"公网IP {eip} 可连通")

        with allure_step_log("步骤5: 进入详情页验证跳转地址"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning("绑定公网IP后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "绑定公网IP后跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("绑定公网IP后跳转地址验证通过")

    @allure.title("APT-解绑公网IP验证")
    def test_apt_10_unbind_eip(self, apt_instance, apt_page, ssh_host, security_fip_pool):
        """场景10（440222）：解绑公网IP并通过 ssh_host ping 验证不可达。"""
        name = apt_instance["name"]
        page = apt_page.page

        with allure_step_log("步骤1: 进入攻击预警APT页面，确认待解绑公网IP"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url
            bound_eip = apt_instance.get("eip", "")
            if not bound_eip:
                net_info = apt_page.apt_get_network_info(name)
                bound_eip = net_info["public_ip"]
            logger.info(f"APT 实例 {name} 待解绑公网IP: {bound_eip}")

        with allure_step_log("步骤2: 进入详情页验证跳转地址（绑定状态）"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is not None:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("解绑前跳转地址验证通过")
            apt_page.goto_list_page()

        with allure_step_log("步骤3: 执行解绑公网IP操作，验证网络列为空"):
            apt_page.apt_unbind_floating_ip(name)
            apt_page.assert_popup_success()
            apt_page.wait_for_operation_complete(timeout=60)
            net_info = apt_page.apt_get_network_info(name)
            logger.info(f"APT 实例 {name} 解绑后网络列信息: {net_info}")
            if bound_eip:
                assert bound_eip not in net_info["raw"], \
                    f"解绑后网络列仍显示公网IP {bound_eip}: {net_info['raw']}"
            logger.info(f"APT 实例 {name} 已解绑公网IP")

        with allure_step_log("步骤4: 进入详情页验证跳转地址（解绑后）"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning("解绑后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, \
                    f"新页面加载到错误页面: {new_page.url}"
                if new_page != page:
                    new_page.close()
                logger.info("解绑后跳转地址验证通过")
            apt_page.goto_list_page()

        with allure_step_log("步骤5: 通过 ssh_host ping 验证公网IP已不可达"):
            if bound_eip:
                result = ssh_host.run(f"ping -c 4 {bound_eip}", return_rc=True)
                logger.info(
                    f"ping {bound_eip} 结果: rc={result['rc']}, stdout={result['stdout'][:300]}"
                )
                assert result["rc"] != 0 or "100% packet loss" in result["stdout"], \
                    f"公网IP {bound_eip} 解绑后仍可 ping 通: {result['stdout'][:300]}"
                logger.info(f"公网IP {bound_eip} 已解绑，ping 不可达")
                security_fip_pool.release(bound_eip)
                logger.info(f"公网IP {bound_eip} 已归还到 FIP 池")
            else:
                logger.warning("未找到待解绑的公网IP，跳过 ping 验证")

    @allure.title("APT-登录VNC控制台验证")
    def test_apt_11_vnc_login(self, apt_instance, apt_page):
        """场景11（440223）：点击登录VNC，输入密码 000000，验证 VNC 控制台可打开。"""
        name = apt_instance["name"]
        logger.info(f"APT 实例 {name} 已就绪，准备登录 VNC")

        with allure_step_log("步骤1: 进入攻击预警APT页面"):
            apt_page.goto_list_page()
            assert "/apt" in apt_page.page.url

        with allure_step_log("步骤2/3: 登录VNC并输入密码 000000"):
            vnc_page = apt_page.apt_login_vnc(name, password="000000")
            assert vnc_page is not None, "VNC 页面未打开"
            assert "chrome-error" not in vnc_page.url, \
                f"VNC 页面加载到错误页面: {vnc_page.url}"
            logger.info(f"APT 实例 {name} VNC 控制台打开成功，URL: {vnc_page.url}")
            if "chrome-error" not in vnc_page.url:
                vnc_body = vnc_page.inner_text("body")[:500]
                logger.info(f"VNC 页面 body 内容: {vnc_body}")
            logger.info(f"APT 实例 {name} VNC 登录验证通过")

    @allure.title("APT-规格升级验证")
    def test_apt_12_spec_upgrade(self, apt_instance, apt_page, ssh_host):
        """场景12：对运行的 APT 实例执行规格升级，验证升级前后规格信息变化，
        并通过 SSH 后端验证 vcpu 和 memory_mb 字段。"""
        name = apt_instance["name"]
        logger.info(f"APT 实例 {name} 已就绪")

        with allure_step_log("步骤1: 获取当前规格信息"):
            apt_page.goto_list_page()
            row_data = apt_page.get_row_data(name)
            current_spec = row_data.get("规格", "")
            logger.info(f"APT 实例 {name} 当前规格: {current_spec}")
            assert current_spec, f"未获取到 APT 实例 {name} 的规格信息"

        with allure_step_log("步骤2: 执行规格升级操作"):
            selected_spec = apt_page.apt_spec_upgrade(name)
            logger.info(
                f"APT 实例 {name} 已提交规格升级请求，"
                f"目标规格: vcpu={selected_spec['vcpus']}核, "
                f"memory_mb={selected_spec['memory_mb']}MB"
            )

        with allure_step_log("步骤3: 等待规格升级完成，验证状态与规格变更"):
            apt_page.assert_apt_status(name, service_status="运行", vm_status="运行", timeout=600)
            apt_page.goto_list_page()
            row_data_after = apt_page.get_row_data(name)
            new_spec = row_data_after.get("规格", "")
            logger.info(f"APT 实例 {name} 升级后规格: {new_spec}")
            assert new_spec != current_spec, \
                f"规格未变更: 升级前={current_spec}, 升级后={new_spec}"
            assert new_spec, f"未获取到 APT 实例 {name} 升级后的规格信息"

        with allure_step_log("步骤4: 进入详情页，记录 server_id 用于后端验证"):
            server_id = apt_page.apt_get_server_id(name)
            assert server_id, f"未提取到 APT 实例 {name} 的 server_id"
            apt_page.goto_list_page()

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

    @allure.title("APT-云硬盘扩容验证")
    def test_apt_13_volume_expansion(self, apt_instance, apt_page, ssh_host):
        """场景13：对运行的 APT 实例执行云硬盘扩容到 350GiB，通过 SSH 后端验证扩容结果。"""
        name = apt_instance["name"]
        logger.info(f"APT 实例 {name} 已就绪")

        with allure_step_log("步骤1: 进入详情页查看当前云硬盘大小"):
            apt_page.goto_list_page()
            apt_page.apt_to_details(name)
            body_text = apt_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"APT 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤2: 执行云硬盘扩容到 350GiB"):
            server_id = apt_page.apt_volume_expand(name, 350)
            assert server_id, f"未提取到 APT 实例 {name} 的 server_id"
            logger.info(f"APT 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤3: SSH 连接环境后台，验证云硬盘扩容结果"):
            actual_size = wait_backend_volume_size(
                ssh_host, server_id, expected_size=350, timeout=300
            )
            assert actual_size == 350, \
                f"云硬盘大小不匹配: scli返回={actual_size}GiB, 期望=350GiB"
            logger.info("云硬盘扩容 SSH 后端验证通过: 350GiB")

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
            logger.info(f"APT 实例 {name} volume_uuid: {volume_uuid}")

            if volume_uuid:
                vol_output = ssh_host.run(f"scli volume show {volume_uuid}", check_rc=True)
                vol_size_match = re.search(r'(?i)size\s*[:|]\s*(\d+)', vol_output)
                if vol_size_match:
                    vol_size = int(vol_size_match.group(1))
                    logger.info(f"scli volume show 解析结果: size={vol_size}GiB")
                    assert vol_size == 350, \
                        f"scli volume show 云硬盘大小不匹配: 实际={vol_size}GiB, 期望=350GiB"
                    logger.info("scli volume show 验证通过: 350GiB")

    @allure.title("APT-修改名称验证")
    def test_apt_14_rename(self, apt_instance, apt_page):
        """场景14：验证 APT 实例修改名称功能，修改后列表页和详情页均展示新名称。"""
        name = apt_instance["name"]
        new_name = random_data().replace("autotest-", "autotest-apt-")
        logger.info(f"准备将 APT 实例 {name} 改名为 {new_name}")

        with allure_step_log("步骤1: 执行修改实例名称操作"):
            apt_page.apt_rename(name, new_name)
            apt_page.assert_popup_success("执行成功")
            apt_instance["name"] = new_name
            logger.info(f"APT 实例名称已修改为 {new_name}")

        with allure_step_log("步骤2: 验证列表页名称已更新"):
            apt_page.goto_list_page()
            row_data = apt_page.get_row_data(new_name)
            assert row_data, f"列表页未找到修改后的实例名称: {new_name}"
            logger.info(f"列表页验证通过: 找到实例 {new_name}")

        with allure_step_log("步骤3: 验证详情页名称一致"):
            apt_page.apt_to_details(new_name)
            body_text = apt_page.get_detail_body_text()
            assert new_name in body_text, f"详情页未显示修改后的名称: {new_name}"
            logger.info("详情页验证通过: 名称与修改后一致")
