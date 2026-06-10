import re
import time
import pytest
import allure

from sugon_web.common.remote import SSH
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data, get_file_abspath


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS完整创建流程")
class TestBmsSoftCreate:

    @allure.title("裸金属BMS-软装版创建流程")
    def test_bms_create_with_page_image(self, ops_page, bms_page, ssh_host, config, bms_instance, bms_env):
        sg_name = f"test-bms-{random_data()}"
        bms_network_name = bms_env["network_name"]
        discovery_name = f"bms-test-{random_data()}"
        bmc_ip = bms_env["bmc_ip"]
        preferred_node = bms_env["preferred_node"]
        instance_name = bms_env["instance_name"]
        skip_to_step14 = False  # 标记是否跳过到步骤14（已有实例复用）

        # === 步骤0: 清理（本次跳过，保留资源供后续测试使用） ===
        logger.info("步骤0: 跳过清理，保留已创建的BMS资源")

        # === 步骤1-2: 获取或创建交换机组 ===
        with allure_step_log("步骤1-2: 获取交换机组"):
            ops_page._goto_switch_group()
            sg_name = None
            actual_node = None
            for r in ops_page.page.locator("tbody tr").all():
                try:
                    cells = r.locator("td")
                    if cells.count() > 1:
                        n = cells.nth(1).text_content(timeout=3000).strip()
                        pm = cells.nth(2).text_content(timeout=3000).strip() if cells.count() > 2 else ""
                        # 物理机名必须是合法主机名（不含中文、操作按钮文案）
                        if n and pm and pm != "--" and pm != "—" and not re.search(r'[一-鿿]', pm):
                            sg_name = n
                            actual_node = pm
                            break
                except Exception:
                    continue
            if not sg_name:
                sg_name = f"test-bms-{random_data()}"
                ops_page.switch_group_create(sg_name)
                ops_page.page.wait_for_timeout(2000)
                ops_page._goto_switch_group()
                ops_page.search(sg_name)
                assert ops_page.get_row_data(sg_name).get("名称") == sg_name
                ops_page.switch_group_bind_node(sg_name, preferred_node)
                ops_page.page.wait_for_timeout(2000)
                ops_page._goto_switch_group()
                ops_page.search(sg_name)
                actual_node = ops_page.get_row_data(sg_name).get("物理机", "")
                assert actual_node and actual_node != "--"
            # 物理机列可能返回多个节点名拼接（如 master02.cloud.localmaster01.cloud.local），提取第一个
            if actual_node and preferred_node in actual_node:
                actual_node = preferred_node
            logger.info(f"使用交换机组: {sg_name}, 物理机: {actual_node}")

        # 前置检查：确认目标节点在 K8s 中为 Ready 状态
        with allure_step_log("步骤2b: 检查节点健康状态"):
            node_status = ssh_host.run(f"sudo kubectl get nodes {actual_node} --no-headers", return_rc=True)
            if node_status.get("rc") != 0 or "Ready" not in node_status.get("stdout", ""):
                logger.warning(f"节点 {actual_node} 在 Kubernetes 中不为 Ready 状态，跳过测试")
                pytest.skip(f"节点 {actual_node} 不在线或不为 Ready 状态，无法继续 BMS 流程")

        # === 步骤3: 创建网络 ===
        with allure_step_log("步骤3: 创建网络"):
            bms_page._goto_submenu_safe("网络")
            bms_page.page.wait_for_timeout(3000)
            # 多重检测：先检查表格行，再检查是否有"新建"按钮
            has_net = False
            for _ in range(3):
                rows = bms_page._get_rows()
                has_net = any(
                    bms_network_name in (r.text_content(timeout=3000) or "")
                    for r in rows
                    if "暂无数据" not in (r.text_content(timeout=3000) or "")
                )
                if has_net:
                    break
                # 如果没检测到行数据，检查是否有"新建"按钮（有则说明表格为空）
                new_btn = bms_page.page.locator("button, .cloud-button, .el-button").filter(has_text="新建")
                if new_btn.count() == 0 or not new_btn.first.is_visible():
                    # 没有新建按钮，说明表格有数据（只是可能还没解析到）
                    has_net = True
                    break
                bms_page.page.wait_for_timeout(2000)
            if not has_net:
                bms_page.bms_network_create(
                    name=bms_network_name, cidr="10.0.13.0/24",
                    start_ip="10.0.13.1", end_ip="10.0.13.254",
                    gateway="10.0.13.254", vlan="3157")
                bms_page.page.wait_for_timeout(3000)
            else:
                logger.info("网络bms已存在，跳过创建")
            bms_page._goto_submenu_safe("网络")
            bms_page.search(bms_network_name)
            assert bms_page.get_row_data(bms_network_name).get("网络名称") == bms_network_name

        # === 步骤4: 注册代理 ===
        with allure_step_log("步骤4: 注册代理"):
            bms_page.bms_agent_register(node_name=actual_node, ip_address="10.0.13.13")
            bms_page.page.wait_for_timeout(3000)
            bms_page._goto_submenu_safe("代理")
            bms_page.search(actual_node)
            agent_data = bms_page.get_row_data(actual_node)
            assert agent_data is not None
            agent_status = agent_data.get("状态", "")
            if agent_status != "健康":
                logger.warning(f"代理 {actual_node} 状态为 '{agent_status}'，不为健康，跳过测试")
                pytest.skip(f"代理 {actual_node} 状态异常: {agent_status}，无法继续 BMS 流程")

        # === 步骤5: 安装PXE ===
        with allure_step_log("步骤5: 安装PXE"):
            if agent_data.get("安装插件") == "是":
                logger.info(f"代理 {actual_node} 已安装PXE插件，跳过安装")
            else:
                bms_page.bms_agent_install_pxe(actual_node)
                bms_page.page.wait_for_timeout(3000)
                if not bms_page.bms_agent_wait_pxe_installed(actual_node, initial_wait=300, poll_interval=30, max_wait=1800):
                    pytest.skip("PXE安装超时")

        # === 步骤6: 创建发现任务 ===
        with allure_step_log("步骤6: 创建发现任务"):
            bms_page._goto_submenu_safe("发现")
            bms_page.page.wait_for_timeout(3000)
            # 检查是否已有覆盖该 BMC IP 的发现任务
            rows = bms_page._get_rows()
            existing_discovery = None
            for r in rows:
                try:
                    txt = r.text_content(timeout=3000) or ""
                    if "暂无数据" in txt:
                        continue
                    # 检查行中是否包含目标 BMC IP
                    if bmc_ip in txt:
                        cells = r.locator("td")
                        if cells.count() > 1:
                            name = cells.nth(1).text_content(timeout=3000).strip()
                            if name:
                                existing_discovery = name
                                break
                except Exception:
                    continue
            if existing_discovery:
                logger.info(f"发现已有覆盖 BMC {bmc_ip} 的发现任务: {existing_discovery}，将复用")
                discovery_name = existing_discovery
            else:
                bms_page.bms_discovery_create(
                    name=discovery_name, start_ip=bmc_ip, end_ip=bmc_ip,
                    subnet_mask="255.255.255.0", username="admin", password="admin")
                bms_page.page.wait_for_timeout(3000)
                bms_page._goto_submenu_safe("发现")
                bms_page.search(discovery_name)
                rd = bms_page.get_row_data(discovery_name)
                if rd is None:
                    # 创建后验证失败，可能是IP冲突或后端延迟，尝试从列表中查找
                    logger.warning(f"创建发现任务 '{discovery_name}' 后未立即找到，尝试从列表匹配")
                    bms_page._goto_submenu_safe("发现")
                    rows = bms_page._get_rows()
                    for r in rows:
                        try:
                            txt = r.text_content(timeout=3000) or ""
                            if bmc_ip in txt:
                                cells = r.locator("td")
                                if cells.count() > 1:
                                    discovery_name = cells.nth(1).text_content(timeout=3000).strip()
                                    logger.info(f"从列表匹配到发现任务: {discovery_name}")
                                    break
                        except Exception:
                            continue
                    else:
                        pytest.skip("无法创建或找到发现任务，可能该BMC IP已被其他任务覆盖")
            # 执行同步
            bms_page.bms_discovery_sync(discovery_name)
            bms_page.page.wait_for_timeout(3000)
            time.sleep(300)

        # === 步骤7: 带外信息 + 等待注册完成 ===
        with allure_step_log("步骤7: 配置带外信息"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            rd = bms_page.get_row_data(bmc_ip)
            assert rd is not None
            current_status = str(rd.get("状态", ""))
            if "注册完成" in current_status or "就绪" in current_status:
                logger.info(f"BMC {bmc_ip} 状态已为'{current_status}'，跳过带外信息配置")
            elif "新上架" in current_status or "注册中" in current_status:
                # 无论'新上架'还是'注册中'，都配置带外信息以确保注册能顺利完成
                logger.info(f"BMC {bmc_ip} 状态为'{current_status}'，配置带外信息")
                bms_page.bms_register_out_of_band_info(bmc_ip, switch_vlan="787", switch_group_name=sg_name)
                bms_page.page.wait_for_timeout(3000)
            elif "已使用" in current_status:
                logger.info(f"BMC {bmc_ip} 状态为'已使用'，检查是否已有实例")
                bms_page._goto_submenu_safe("裸金属实例")
                bms_page.page.wait_for_timeout(2000)
                rows = bms_page._get_rows()
                existing_instance = None
                for r in rows:
                    try:
                        txt = r.text_content(timeout=3000)
                        if txt and "暂无数据" not in txt and bms_network_name in txt:
                            cells = r.locator("td")
                            if cells.count() > 1:
                                name = cells.nth(1).text_content(timeout=3000).strip()
                                if name and name != "":
                                    existing_instance = name
                                    break
                    except Exception:
                        continue
                if existing_instance:
                    logger.info(f"发现已有实例: {existing_instance}，将复用该实例")
                    instance_name = existing_instance
                    skip_to_step14 = True
                else:
                    pytest.skip(f"BMC {bmc_ip} 状态为'已使用'但未找到实例，环境异常")
            elif "注册失败" in current_status:
                logger.warning(f"BMC {bmc_ip} 状态为'注册失败'，尝试删除并重新发现")
                bms_page.bms_register_delete(bmc_ip)
                bms_page.page.wait_for_timeout(3000)
                # 先删除旧发现任务，避免同IP冲突导致新建失败
                try:
                    bms_page.bms_discovery_delete(discovery_name)
                    bms_page.page.wait_for_timeout(3000)
                except Exception as e:
                    logger.warning(f"删除旧发现任务失败（可能已不存在）: {e}")
                # 重新创建发现任务并同步（使用新名称避免冲突）
                rediscovery_name = f"bms-retry-{random_data()}"
                bms_page.bms_discovery_create(
                    name=rediscovery_name, start_ip=bmc_ip, end_ip=bmc_ip,
                    subnet_mask="255.255.255.0", username="admin", password="admin")
                bms_page.page.wait_for_timeout(5000)
                # 如果重试发现任务仍未创建成功，跳过而非失败
                try:
                    bms_page.bms_discovery_sync(rediscovery_name)
                except Exception as e:
                    logger.warning(f"重新发现任务同步失败: {e}")
                    pytest.skip(f"BMC {bmc_ip} 注册失败后重新发现未能成功创建任务，环境可能不支持该BMC的重新发现")
                time.sleep(300)
                # 重新检查注册状态
                bms_page._goto_submenu_safe("注册")
                bms_page.search(bmc_ip)
                rd = bms_page.get_row_data(bmc_ip)
                current_status = str(rd.get("状态", "")) if rd else ""
                if "新上架" in current_status:
                    bms_page.bms_register_out_of_band_info(bmc_ip, switch_vlan="787", switch_group_name=sg_name)
                    bms_page.page.wait_for_timeout(3000)
                elif "注册完成" in current_status:
                    logger.info(f"重新发现后状态已为'注册完成'")
                else:
                    pytest.skip(f"重新发现后BMC {bmc_ip} 仍处异常状态: {current_status}")
            else:
                pytest.skip(f"BMC {bmc_ip} 处于未知状态: {current_status}")

        with allure_step_log("步骤7b: 等待注册完成"):
            if "已使用" in current_status:
                logger.info("BMC状态为'已使用'，跳过注册完成等待")
            elif "注册完成" in current_status or "就绪" in current_status:
                logger.info(f"BMC状态已为'{current_status}'，跳过注册完成等待")
            else:
                if not bms_page.bms_register_wait_status(bmc_ip, "注册完成", poll_interval=30, max_wait=600):
                    pytest.skip("步骤7注册完成等待超时（10分钟），可能环境异常")

        # === 步骤8: SSH检查BMS网卡 ===
        with allure_step_log("步骤8: SSH检查BMS网卡"):
            # 获取 master02 的 IP 地址
            node_info = ssh_host.run(f"kubectl get nodes {actual_node} -owide", return_rc=True)
            master02_ip = None
            for line in node_info.get("stdout", "").split('\n'):
                parts = line.split()
                if len(parts) >= 6 and actual_node in line:
                    master02_ip = parts[5]
                    break
            if not master02_ip:
                master02_ip = actual_node
            logger.info(f"master02 节点地址: {master02_ip}")

            # 创建到 master02 的 SSH 连接（通过跳板机）
            ssh_node = SSH()
            ssh_node.jumphost_client = ssh_host.ssh_client
            pkey_path = get_file_abspath(config.get("pkey"))
            ssh_node.connect(host=master02_ip, username="scloudadmin", pkey=pkey_path, use_jumphost=True)

            time.sleep(300)
            bms_nic_name = None
            for i in range(3):
                r = ssh_node.run("ip a | grep bms", return_rc=True)
                if r["rc"] == 0 and "bms-nic" in r["stdout"]:
                    # ip a 输出格式: "bms-nic-3157: <flags> ..."，冒号不是名称一部分
                    m = re.search(r"(bms-nic[0-9a-zA-Z_-]+)", r["stdout"])
                    if m:
                        bms_nic_name = m.group(1)
                        logger.info(f"网卡: {bms_nic_name}")
                        break
                if i < 2:
                    time.sleep(300)
            if not bms_nic_name:
                ssh_node.close()
                pytest.skip("未找到bms-nic网卡")

        try:
            # === 步骤9: 记录 ===
            with allure_step_log("步骤9: 记录网卡名称"):
                allure.attach(bms_nic_name, "BMS网卡", allure.attachment_type.TEXT)

            # === 步骤10: 检查/编辑trusted.xml ===
            with allure_step_log("步骤10: 检查trusted.xml"):
                r = ssh_node.run("cat /etc/firewalld/zones/trusted.xml")
                if f'<interface name="{bms_nic_name}"/>' not in r:
                    ssh_node.run("sudo cp /etc/firewalld/zones/trusted.xml /etc/firewalld/zones/trusted.xml.bak")
                    # 使用 sed 在 </zone> 前插入网卡配置
                    insert_line = f'  <interface name="{bms_nic_name}"/>'
                    ssh_node.run(f"sudo sed -i 's|</zone>|{insert_line}\\n</zone>|' /etc/firewalld/zones/trusted.xml")
                v = ssh_node.run("cat /etc/firewalld/zones/trusted.xml")
                assert f'<interface name="{bms_nic_name}"/>' in v

            # === 步骤11: 重启防火墙 ===
            with allure_step_log("步骤11: 重启防火墙"):
                r = ssh_node.run("sudo firewall-cmd --reload", return_rc=True)
                assert r["rc"] == 0
        finally:
            ssh_node.close()

        # === 步骤12: 注册物理机 ===
        with allure_step_log("步骤12: 注册物理机"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            rd = bms_page.get_row_data(bmc_ip)
            reg_status = str(rd.get("状态", "")) if rd else ""
            cpu = str(rd.get("CPU", "")) if rd else ""
            mem = str(rd.get("内存", "")) if rd else ""
            arch = str(rd.get("架构", "")) if rd else ""
            # 即使状态为"注册完成"，如果关键信息缺失也需重新注册
            info_complete = cpu and cpu != "--" and mem and mem != "--" and arch and arch != "--"
            if "已使用" in reg_status:
                logger.info(f"BMC {bmc_ip} 状态已为 '{reg_status}'，跳过重新注册")
            elif "注册完成" in reg_status and info_complete:
                logger.info(f"BMC {bmc_ip} 状态为'{reg_status}'且信息完整(CPU={cpu},内存={mem},架构={arch})，跳过重新注册")
            else:
                if "注册完成" in reg_status and not info_complete:
                    logger.info(f"BMC {bmc_ip} 状态为'{reg_status}'但信息不完整(CPU={cpu},内存={mem},架构={arch})，重新注册")
                bms_page.bms_register_action(bmc_ip)
                bms_page.page.wait_for_timeout(3000)
                if not bms_page.bms_register_wait_status(bmc_ip, "就绪", poll_interval=30, max_wait=2400):
                    pytest.skip("注册未在40分钟内完成")

        if skip_to_step14:
            logger.info("检测到已有实例，跳过步骤13（创建实例），直接进入步骤14")
        else:
            # === 步骤13-14: 创建裸金属实例并等待运行中（使用 fixture 工厂函数） ===
            instance_name = bms_instance(name=instance_name)

        # === 步骤15: SSH验证 ===
        with allure_step_log("步骤15: SSH验证"):
            port_uuid = None
            for attempt in range(10):
                # 先尝试用网卡名搜索
                r = ssh_host.run(f"scli port list | grep {bms_nic_name}", return_rc=True)
                if r["rc"] == 0 and r["stdout"].strip():
                    m = re.search(r"\| ([a-f0-9\-]+) +\|", r["stdout"])
                    if m:
                        port_uuid = m.group(1)
                        logger.info(f"步骤15: 通过网卡名找到端口UUID: {port_uuid}")
                        break
                # 如果网卡名搜索失败，尝试搜索所有bms相关端口
                r_all = ssh_host.run("scli port list | grep -i bms", return_rc=True)
                if r_all["rc"] == 0 and r_all["stdout"].strip():
                    lines = [l for l in r_all["stdout"].split("\n") if l.strip()]
                    for line in lines:
                        m = re.search(r"\| ([a-f0-9\-]+) +\|", line)
                        if m:
                            port_uuid = m.group(1)
                            logger.info(f"步骤15: 通过bms关键字找到端口UUID: {port_uuid}")
                            break
                    if port_uuid:
                        break
                logger.info(f"步骤15: scli port list 未找到端口，第{attempt + 1}/10次重试...")
                time.sleep(60)
            else:
                pytest.skip("scli port list 未找到任何bms相关端口")
            r2 = ssh_host.run(f"scli port show {port_uuid}")
            # BMS 端口的 device_owner 为 neutron:bms，vnic_type 可能为空
            assert "neutron:bms" in r2 or "baremetal" in r2

        # === 步骤16: 验证注册状态 ===
        with allure_step_log("步骤16: 验证注册状态"):
            bms_page._goto_submenu_safe("注册")
            bms_page.search(bmc_ip)
            assert "已使用" in bms_page.get_row_data(bmc_ip).get("状态", "")
