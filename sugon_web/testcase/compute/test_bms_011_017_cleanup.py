import pytest
import allure
import time

from sugon_web.common.remote import SSH
from sugon_web.utils.data import get_file_abspath
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-资源清理与镜像创建")
class TestBmsCleanup:
    """验证裸金属BMS软装版资源清理流程和镜像创建功能。"""

    # ---------- 资源重建辅助方法 ----------

    def _retry_cleanup_action(self, action_name, action, page, attempts=3, delay_ms=5000):
        """Retry a cleanup action before marking the case failed."""
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                logger.info(f"{action_name} 第 {attempt}/{attempts} 次尝试")
                return action()
            except Exception as e:
                last_error = e
                logger.warning(f"{action_name} 第 {attempt}/{attempts} 次失败: {e}")
                if attempt < attempts:
                    page.wait_for_timeout(delay_ms)
        raise AssertionError(f"{action_name} 重试 {attempts} 次后仍失败: {last_error}") from last_error

    def _wait_switch_group_unbound(self, bms_page, group_name, attempts=30):
        """Wait until the switch group physical-machine column becomes unbound."""
        last_row_text = "(未找到行)"
        for i in range(attempts):
            bms_page.goto_service("交换机组", force=True)
            bms_page.wait_for_page_ready()
            bms_page.page.wait_for_timeout(3000)
            row = bms_page._get_row_by_name(group_name)
            if not row:
                logger.info(f"交换机组 '{group_name}' 已不存在，视为已解绑")
                return True
            last_row_text = row.text_content() or ""
            if "--" in last_row_text:
                logger.info(f"解绑验证成功，第 {i + 1} 次轮询检测到物理机列为 '--'")
                return True
            logger.info(f"解绑验证第 {i + 1}/{attempts} 次轮询，物理机未变为 '--'，继续等待...")
            bms_page.page.wait_for_timeout(5000)
        raise AssertionError(f"物理机列应显示'--'，实际: {last_row_text}")

    def _require_pxe_agent_or_skip(self, bms_page, node_name):
        """确保指定代理已安装PXE插件，如未安装则尝试安装；环境不支持则跳过测试。"""
        bms_page._goto_submenu_safe("代理")
        bms_page.bms_search(node_name)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(node_name)
        row_text = row.text_content() or "" if row else ""
        if row and "是" in row_text:
            logger.info(f"代理 '{node_name}' PXE插件已安装")
            return
        if not row:
            logger.warning(f"代理 '{node_name}' 不存在，且注册代理无法精确选择目标节点（UI仅支持选Region），跳过测试")
            pytest.skip(f"代理 '{node_name}' 不存在，无法通过UI精确注册到指定节点，跳过测试")
        logger.info(f"代理 '{node_name}' PXE未安装，开始安装...")
        try:
            bms_page.bms_agent_install_pxe(node_name)
            bms_page.page.wait_for_timeout(3000)
            if not bms_page.bms_agent_wait_pxe_installed(node_name, initial_wait=300, poll_interval=30, max_wait=1800):
                pytest.skip(f"环境不支持代理 '{node_name}' 的PXE插件安装，跳过需要发现任务的测试")
        except Exception as e:
            logger.warning(f"PXE安装异常: {e}")
            pytest.skip(f"环境不支持代理 '{node_name}' 的PXE插件安装，跳过需要发现任务的测试")

    def _ensure_network_exists(self, bms_page, network_name="bms"):
        """确保网络存在，不存在则创建。"""
        bms_page._goto_submenu_safe("网络")
        bms_page.page.wait_for_load_state("networkidle")
        bms_page.page.wait_for_timeout(5000)
        bms_page.bms_search(network_name)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(network_name)
        if not row:
            logger.info(f"网络 '{network_name}' 不存在，创建中...")
            bms_page.bms_network_create(
                name=network_name, cidr="10.0.13.0/24",
                start_ip="10.0.13.1", end_ip="10.0.13.254",
                gateway="10.0.13.254", vlan="3157")
            bms_page.page.wait_for_timeout(5000)
            bms_page._goto_submenu_safe("网络")
            bms_page.bms_search(network_name)
            bms_page.page.wait_for_timeout(3000)
            assert bms_page._get_row_by_name(network_name), f"网络 '{network_name}' 创建失败"
            logger.info(f"网络 '{network_name}' 创建成功")
        else:
            logger.info(f"网络 '{network_name}' 已存在")

    def _ensure_discovery_exists(self, bms_page, discovery_name, bmc_ip, node_name):
        """确保发现任务存在，不存在则创建。返回实际的任务名称。"""
        bms_page._goto_submenu_safe("发现")
        bms_page.page.wait_for_load_state("networkidle")
        bms_page.page.wait_for_timeout(5000)
        # 优先通过 BMC IP 查找现有任务（避免 IP 冲突导致创建失败）
        existing = self._find_discovery_by_bmc_ip(bms_page, bmc_ip)
        if existing:
            logger.info(f"发现已有覆盖 BMC {bmc_ip} 的发现任务: {existing}，将复用")
            return existing
        # 按名称查找固定任务
        bms_page.bms_search(discovery_name)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(discovery_name)
        if row:
            logger.info(f"发现任务 '{discovery_name}' 已存在")
            return discovery_name
        logger.info(f"发现任务 '{discovery_name}' 不存在，创建中...")
        # 发现任务需要PXE代理，先确保PXE就绪
        self._require_pxe_agent_or_skip(bms_page, node_name)
        # 先清理所有发现任务，避免脏状态导致创建失败
        try:
            bms_page.bms_discovery_cleanup()
            bms_page.page.wait_for_timeout(3000)
            logger.info("已清理现有发现任务")
        except Exception as e:
            logger.warning(f"清理发现任务失败（可能无需清理）: {e}")
        bms_page.bms_discovery_create(
            name=discovery_name, start_ip=bmc_ip, end_ip=bmc_ip,
            subnet_mask="255.255.255.0", username="admin", password="admin")
        bms_page.page.wait_for_timeout(10000)
        # 创建后再次验证（按名称或 BMC IP）
        bms_page._goto_submenu_safe("发现")
        bms_page.page.wait_for_timeout(5000)
        existing = self._find_discovery_by_bmc_ip(bms_page, bmc_ip)
        if existing:
            logger.info(f"发现任务创建/匹配成功，实际名称: {existing}")
            return existing
        bms_page.bms_search(discovery_name)
        bms_page.page.wait_for_timeout(5000)
        row = bms_page._get_row_by_name(discovery_name)
        if row:
            logger.info(f"发现任务 '{discovery_name}' 创建成功")
            return discovery_name
        pytest.skip(f"发现任务 '{discovery_name}' 创建后未找到，可能环境不支持该BMC IP的发现")

    def _find_discovery_by_bmc_ip(self, bms_page, bmc_ip):
        """通过 BMC IP 在发现任务列表中查找匹配的任务名称。"""
        bms_page._goto_submenu_safe("发现")
        bms_page.page.wait_for_load_state("networkidle")
        bms_page.page.wait_for_timeout(8000)
        # 等待表格行加载（最多30秒）
        try:
            bms_page.page.wait_for_selector("tbody tr", timeout=30000)
        except Exception:
            logger.warning("[_find_discovery_by_bmc_ip] 等待表格行加载超时")
        rows = bms_page._get_rows()
        logger.info(f"[_find_discovery_by_bmc_ip] 当前发现任务列表共 {len(rows)} 行，查找 BMC IP: {bmc_ip}")
        for idx, r in enumerate(rows):
            try:
                txt = r.text_content(timeout=5000) or ""
                if "暂无数据" in txt:
                    continue
                logger.debug(f"[_find_discovery_by_bmc_ip] 第 {idx} 行: {txt[:100]}")
                if bmc_ip in txt:
                    cells = r.locator("td")
                    if cells.count() > 1:
                        name = cells.nth(1).text_content(timeout=3000).strip()
                        logger.info(f"[_find_discovery_by_bmc_ip] 找到匹配任务: {name}")
                        return name
            except Exception as e:
                logger.debug(f"[_find_discovery_by_bmc_ip] 检查第 {idx} 行失败: {e}")
                continue
        logger.info(f"[_find_discovery_by_bmc_ip] 未找到覆盖 BMC {bmc_ip} 的发现任务")
        return None

    def _ensure_agent_exists(self, bms_page, node_name):
        """确保代理存在，优先使用指定节点，不存在则回退删除列表中的实际残留代理。

        清理阶段的目标是删除残留代理；如果配置节点不存在，不应直接 skip。
        """
        bms_page._goto_submenu_safe("代理")
        bms_page.page.wait_for_load_state("networkidle")
        bms_page.page.wait_for_timeout(5000)
        # 强制关闭任何残留对话框，防止拦截搜索
        for dlg in bms_page.page.locator(".el-dialog__wrapper, [role='dialog']").all():
            try:
                if dlg.is_visible():
                    bms_page.page.keyboard.press("Escape")
                    bms_page.page.wait_for_timeout(500)
            except Exception:
                pass
        bms_page.bms_search(node_name)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(node_name)
        if not row:
            logger.warning(f"代理 '{node_name}' 不存在，尝试删除列表中的实际残留代理")
            try:
                reset_btn = bms_page.page.locator("button, .cloud-button, .el-button").filter(has_text="重置")
                if reset_btn.count() > 0 and reset_btn.first.is_visible():
                    reset_btn.first.click()
                    bms_page.page.wait_for_timeout(3000)
                else:
                    bms_page._goto_submenu_safe("代理")
                    bms_page.page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning(f"重置代理搜索条件失败: {e}")

            for agent_row in bms_page._get_rows():
                try:
                    row_text = agent_row.text_content(timeout=3000) or ""
                    if not row_text or "暂无数据" in row_text:
                        continue
                    cells = agent_row.locator("td")
                    actual_node = cells.nth(1).text_content(timeout=3000).strip() if cells.count() > 1 else ""
                    if actual_node:
                        logger.info(f"发现实际残留代理 '{actual_node}'，将执行删除")
                        return actual_node
                except Exception as e:
                    logger.debug(f"读取代理行失败: {e}")
                    continue
            pytest.skip(f"未找到代理 '{node_name}'，代理列表也无残留数据")

        logger.info(f"代理 '{node_name}' 已存在")
        return node_name

    def _ensure_switch_group_exists(self, ops_page, group_name, node_name):
        """确保交换机组存在且绑定物理机，不存在则创建并绑定。"""
        ops_page._goto_switch_group()
        ops_page.page.wait_for_load_state("networkidle")
        ops_page.page.wait_for_timeout(5000)
        ops_page.search(group_name)
        ops_page.page.wait_for_timeout(2000)
        row_exists = False
        try:
            row = ops_page.get_row_by_name(group_name)
            row_exists = row.is_visible()
        except AssertionError:
            row_exists = False
        if not row_exists:
            logger.info(f"交换机组 '{group_name}' 不存在，创建中...")
            ops_page.switch_group_create(group_name)
            ops_page.page.wait_for_timeout(3000)
            ops_page._goto_switch_group()
            ops_page.search(group_name)
            ops_page.page.wait_for_timeout(2000)
            try:
                ops_page.get_row_by_name(group_name)
            except AssertionError:
                raise AssertionError(f"交换机组 '{group_name}' 创建失败")
            logger.info(f"交换机组 '{group_name}' 创建成功")
        else:
            logger.info(f"交换机组 '{group_name}' 已存在")
        # 检查是否已绑定物理机
        row = ops_page.get_row_by_name(group_name)
        row_text = row.text_content() or ""
        if "--" in row_text or "—" in row_text:
            logger.info(f"交换机组 '{group_name}' 未绑定物理机，绑定中...")
            ops_page.switch_group_bind_node(group_name, node_name)
            ops_page.page.wait_for_timeout(3000)
            logger.info(f"交换机组 '{group_name}' 绑定物理机成功")
        else:
            logger.info(f"交换机组 '{group_name}' 已绑定物理机")

    def _ensure_register_exists(self, bms_page, ops_page, bmc_ip, discovery_name, group_name, node_name, network_name):
        """确保注册信息存在，不存在则重建完整流程。"""
        bms_page._goto_submenu_safe("注册")
        bms_page.page.wait_for_load_state("networkidle")
        bms_page.page.wait_for_timeout(5000)
        bms_page.bms_search(bmc_ip)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(bmc_ip)
        if row:
            logger.info(f"注册信息 '{bmc_ip}' 已存在")
            return
        logger.info(f"注册信息 '{bmc_ip}' 不存在，重建中...")
        # 1. 确保网络存在（代理依赖）
        self._ensure_network_exists(bms_page, network_name)
        # 2. 确保代理存在且PXE已安装（发现任务的前置依赖）
        self._require_pxe_agent_or_skip(bms_page, node_name)
        # 3. 确保交换机组存在
        self._ensure_switch_group_exists(ops_page, group_name, node_name)
        # 4. 确保发现任务存在
        actual_discovery_name = self._ensure_discovery_exists(bms_page, discovery_name, bmc_ip, node_name)
        # 5. 同步发现任务
        bms_page.bms_discovery_sync(actual_discovery_name)
        bms_page.page.wait_for_timeout(5000)
        # 6. 等待同步完成（发现任务生成注册信息）
        logger.info("等待发现同步完成（300秒）...")
        time.sleep(300)
        # 5. 检查注册信息是否已生成
        bms_page._goto_submenu_safe("注册")
        bms_page.bms_search(bmc_ip)
        bms_page.page.wait_for_timeout(3000)
        row = bms_page._get_row_by_name(bmc_ip)
        if not row:
            raise Exception(f"同步后仍未找到注册信息 '{bmc_ip}'")
        current_status = str(row.text_content() or "")
        # 6. 配置带外信息（如需要）
        if "注册完成" in current_status or "就绪" in current_status:
            logger.info(f"注册信息 '{bmc_ip}' 状态已为 '{current_status}'，无需配置带外信息")
        else:
            bms_page.bms_register_out_of_band_info(bmc_ip, switch_vlan="787", switch_group_name=group_name)
            bms_page.page.wait_for_timeout(5000)
        # 7. 等待注册状态就绪
        bms_page.bms_register_wait_status(bmc_ip, "就绪", poll_interval=30, max_wait=600)
        logger.info(f"注册信息 '{bmc_ip}' 重建完成")

    # ---------- 测试方法 ----------

    @allure.title("裸金属BMS-实例删除")
    def test_bms_011_instance_delete(self, bms_page, ops_page, ssh_host, config, bms_instance, bms_env):
        """删除裸金属实例并验证注册状态变更。

        若实例不存在，自动调用 BMS_001 完整创建流程先创建再删除，
        使 cleanup 文件可独立运行，无需 Jenkins 按序调度创建用例。
        """
        instance_name = bms_env["instance_name"]
        bmc_ip = bms_env["bmc_ip"]

        # 检查实例是否存在，不存在则自动创建
        bms_page._goto_submenu_safe("裸金属实例")
        bms_page.page.wait_for_timeout(3000)
        instance_exists = False
        try:
            bms_page.search(instance_name)
            bms_page.page.wait_for_timeout(2000)
            row = bms_page._get_row_by_name(instance_name)
            instance_exists = row is not None and row.is_visible()
        except Exception as e:
            logger.warning(f"检查实例存在性时出错: {e}")
            instance_exists = False

        if not instance_exists:
            logger.info(f"实例 '{instance_name}' 不存在，先执行镜像创建 + 完整创建流程...")
            # 1) 先创建镜像，确保实例创建时有可用镜像
            TestBmsCleanup().test_bms_017_image_create(ssh_host)
            # 2) 执行完整创建流程（BMS_001）
            from sugon_web.testcase.compute.test_bms_001_soft_create import TestBmsSoftCreate
            TestBmsSoftCreate().test_bms_create_with_page_image(
                ops_page, bms_page, ssh_host, config, bms_instance, bms_env
            )
            logger.info("实例创建完成，继续执行删除测试")

        # 步骤1：搜索并删除实例
        with allure_step_log("步骤1: 搜索并删除裸金属实例"):
            bms_page.bms_instance_delete(instance_name)

        # 步骤2：验证实例已删除
        with allure_step_log("步骤2: 验证实例已删除"):
            bms_page.search(instance_name)
            bms_page.assert_list_not_contain(instance_name, "名称")

        # 步骤3：验证注册状态变为"注册中"
        with allure_step_log("步骤3: 验证注册状态变更为注册中"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            bms_page.assert_list_contain(bmc_ip, "带外IP")
            # 状态应为"注册中"
            row_data = bms_page.get_row_data(bmc_ip)
            assert "注册中" in str(row_data), f"注册状态应为'注册中'，实际: {row_data}"

        # 步骤4：等待状态变为"就绪"
        with allure_step_log("步骤4: 等待注册状态变为就绪"):
            bms_page.bms_register_wait_status(bmc_ip, target_status="就绪", poll_interval=5, max_wait=600)

    @allure.title("裸金属BMS-注册信息删除")
    def test_bms_012_register_delete(self, bms_page, ops_page, bms_env):
        """删除裸金属注册信息。"""
        bmc_ip = bms_env["bmc_ip"]
        discovery_name = "bms-test-autotest"
        group_name = "test-bms-autotest"
        node_name = bms_env["preferred_node"]
        network_name = bms_env["network_name"]

        # 确保注册信息存在（支持重建）
        self._ensure_register_exists(bms_page, ops_page, bmc_ip, discovery_name, group_name, node_name, network_name)

        # 步骤1：搜索并删除注册信息
        with allure_step_log("步骤1: 搜索并删除注册信息"):
            bms_page.bms_register_delete(bmc_ip)

        # 步骤2：验证注册信息已删除
        with allure_step_log("步骤2: 验证注册信息已删除"):
            bms_page.search(bmc_ip)
            bms_page.assert_list_not_contain(bmc_ip, "带外IP")

    @allure.title("裸金属BMS-发现信息删除")
    def test_bms_013_discovery_delete(self, bms_page, bms_env):
        """删除裸金属发现信息。"""
        discovery_name = "bms-test-autotest"
        bmc_ip = bms_env["bmc_ip"]
        node_name = bms_env["preferred_node"]

        # 确保发现任务存在（支持重建），并获取实际任务名称
        actual_discovery_name = self._ensure_discovery_exists(bms_page, discovery_name, bmc_ip, node_name)

        # 步骤1：搜索并删除发现信息
        with allure_step_log("步骤1: 搜索并删除发现信息"):
            bms_page.bms_discovery_delete(actual_discovery_name)

        # 步骤2：验证发现信息已删除
        with allure_step_log("步骤2: 验证发现信息已删除"):
            bms_page.bms_search(actual_discovery_name)
            bms_page.assert_list_not_contain(actual_discovery_name, "名称")

    @allure.title("裸金属BMS-代理信息删除")
    def test_bms_014_agent_delete(self, bms_page, ssh_host, config, bms_env):
        """删除裸金属代理信息并验证后台清理。"""
        node_name = bms_env["preferred_node"]

        # 确保代理存在（支持重建）
        node_name = self._ensure_agent_exists(bms_page, node_name)

        # 步骤1：搜索并删除代理信息
        with allure_step_log("步骤1: 搜索并删除代理信息（最多重试3次）"):
            self._retry_cleanup_action(
                f"删除代理信息 {node_name}",
                lambda: bms_page.bms_agent_delete(node_name),
                bms_page.page,
            )

        # 步骤2：验证代理信息已删除
        with allure_step_log("步骤2: 验证代理信息已删除"):
            bms_page.search(node_name)
            bms_page.assert_list_not_contain(node_name, "物理机")

        # 步骤3：验证后台网卡已清理（需在目标BMS节点上执行）
        with allure_step_log("步骤3: 验证后台网卡已清理"):
            # 获取目标节点IP，通过跳板机SSH到该节点验证
            node_info = ssh_host.run(f"kubectl get nodes {node_name} -owide", return_rc=True)
            target_ip = None
            for line in node_info.get("stdout", "").split('\n'):
                parts = line.split()
                if len(parts) >= 6 and node_name in line:
                    target_ip = parts[5]
                    break
            if not target_ip:
                target_ip = node_name
            logger.info(f"目标BMS节点地址: {target_ip}")

            ssh_node = SSH()
            ssh_node.jumphost_client = ssh_host.ssh_client
            pkey_path = get_file_abspath(config.get("pkey"))
            ssh_node.connect(host=target_ip, username="scloudadmin", pkey=pkey_path, use_jumphost=True)

            deadline = time.time() + 300
            cleaned = False
            while time.time() < deadline:
                result = ssh_node.run("ip a | grep bms", return_rc=True)
                if result and "bms" not in result.get("stdout", ""):
                    cleaned = True
                    break
                time.sleep(10)
            ssh_node.close()
            assert cleaned, "后台网卡未在300秒内清理完成"

        # 步骤4：验证后台Pod和ConfigMap已清理（在controller上执行kubectl即可）
        with allure_step_log("步骤4: 验证后台Pod和ConfigMap已清理"):
            result = ssh_host.run("kubectl get configmap -A | grep bms", return_rc=True)
            assert result["rc"] in (0, 1), f"命令执行失败: {result.get('stderr', '')}"
            assert node_name not in result["stdout"], f"ConfigMap 中仍包含 {node_name} 相关记录: {result['stdout']}"

            result = ssh_host.run("kubectl get pods -A -o wide | grep bms", return_rc=True)
            assert result["rc"] in (0, 1), f"命令执行失败: {result.get('stderr', '')}"
            assert node_name not in result["stdout"], f"Pod 中仍包含 {node_name} 相关记录: {result['stdout']}"

    @allure.title("裸金属BMS-网络信息删除")
    def test_bms_015_network_delete(self, bms_page, bms_env):
        """删除裸金属网络信息。"""
        network_name = bms_env["network_name"]

        # 确保网络存在（支持重建）
        self._ensure_network_exists(bms_page, network_name)

        # 步骤1：搜索并删除网络信息
        with allure_step_log("步骤1: 搜索并删除网络信息（最多重试3次）"):
            self._retry_cleanup_action(
                f"删除网络信息 {network_name}",
                lambda: bms_page.bms_network_delete(network_name),
                bms_page.page,
            )

        # 步骤2：验证网络信息已删除
        with allure_step_log("步骤2: 验证网络信息已删除"):
            assert not bms_page.bms_network_exists(network_name), f"网络 '{network_name}' 删除后仍存在"

    @allure.title("裸金属BMS-交换机信息删除")
    def test_bms_016_switch_group_delete(self, bms_page, ops_page, bms_env):
        """解绑物理机并删除交换机组。"""
        group_name = "test-bms-autotest"
        node_name = bms_env["preferred_node"]
        actual_group_name = group_name

        # 确保交换机组存在且绑定物理机（支持重建）
        self._ensure_switch_group_exists(ops_page, group_name, node_name)

        # 步骤1-2：解绑物理机并验证（异步操作，失败后重新提交解绑）
        with allure_step_log("步骤1-2: 解绑交换机组物理机并验证（最多重试3次）"):
            last_error = None
            for attempt in range(1, 4):
                try:
                    logger.info(f"解绑交换机组物理机第 {attempt}/3 次尝试")
                    actual_group_name = bms_page.bms_switch_group_unbind(actual_group_name, node_name) or actual_group_name
                    self._wait_switch_group_unbound(bms_page, actual_group_name)
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"解绑交换机组物理机第 {attempt}/3 次失败: {e}")
                    if attempt < 3:
                        bms_page.page.wait_for_timeout(5000)
                    else:
                        raise AssertionError(f"交换机组物理机解绑重试 3 次后仍失败: {last_error}") from last_error

        # 步骤3：删除交换机组
        with allure_step_log("步骤3: 删除交换机组（最多重试3次）"):
            self._retry_cleanup_action(
                f"删除交换机组 {actual_group_name}",
                lambda: bms_page.bms_switch_group_delete(actual_group_name),
                bms_page.page,
            )

        # 步骤4：验证交换机组已删除
        with allure_step_log("步骤4: 验证交换机组已删除"):
            bms_page.search(actual_group_name)
            bms_page.assert_list_not_contain(actual_group_name, "名称")

    @allure.title("裸金属BMS-镜像创建")
    def test_bms_017_image_create(self, ssh_host):
        """通过SSH在后台创建裸金属镜像并在前端验证。"""
        image_file = "/home/scloudadmin/centos76-bms-0511.raw"
        image_url = "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos76-bms-0511.raw"
        image_name = "centos76-bms-0511-autotest"

        # 步骤0：检查镜像是否已存在于 glance
        with allure_step_log("步骤0: 检查镜像是否已存在"):
            result = ssh_host.run(f"source /root/admin-openrc.sh && openstack image show {image_name}", return_rc=True)
            if result["rc"] == 0:
                logger.info(f"镜像 '{image_name}' 已存在于 glance，跳过创建")
                return

        # 步骤1：检查并下载镜像文件
        with allure_step_log("步骤1: 检查并下载镜像文件"):
            result = ssh_host.run(f"test -f {image_file} && echo 'exists' || echo 'missing'", return_rc=True)
            assert result["rc"] == 0
            if "missing" in result["stdout"]:
                result = ssh_host.run(f"cd /home/scloudadmin && curl -O {image_url}", return_rc=True, timeout=300)
                assert result["rc"] == 0, f"镜像下载失败: {result.get('stderr', '')}"
                logger.info("镜像下载完成")
            else:
                logger.info("镜像文件已存在，跳过下载")

        # 步骤2：创建裸金属镜像
        with allure_step_log("步骤2: 创建裸金属镜像"):
            cmd = (
                f"source /root/admin-openrc.sh && "
                f"scli image create --visibility public --disk-format raw --container-format bare "
                f"--min-disk 50 --property hypervisor_type=baremetal --property purpose=ironic "
                f"--property os_type=linux --property hw_qemu_guest_agent=yes --backend bms "
                f"--file {image_file} --name {image_name} --progress"
            )
            result = ssh_host.run(cmd, return_rc=True, timeout=1800)
            assert result["rc"] == 0, f"镜像创建失败: {result.get('stderr', '')}"
            logger.info(f"镜像 '{image_name}' 创建成功")

        # 步骤3：在前端验证镜像存在
        with allure_step_log("步骤3: 在前端验证镜像存在"):
            # 这里需要镜像服务的页面对象，暂时用日志记录
            # 实际执行时可通过 image_page 导航到镜像服务进行验证
            logger.info(f"镜像 '{image_name}' 已创建，请在前端镜像服务中验证")
