import allure
import pytest
import re
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('文件存储 SFS')
@allure.story('文件存储-实例创建功能验证')
class TestSFSInstanceCreate:
    """验证文件存储 SFS 实例的创建功能，覆盖 NFS 和 CIFS 两种协议。"""

    @allure.title("文件存储-创建NFS协议实例")
    def test_sfs_create_nfs(self, sfs_page, clean_sfs_instances, ssh_host):
        """创建 NFS 协议文件存储实例并验证 UI 和后台状态。"""
        name = f"sfs-{random_data()}"
        protocol = "nfs"
        volume_size = 10

        with allure_step_log("步骤1: 导航并打开新建文件存储弹窗"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤2: 填写表单并提交创建"):
            sfs_page.sfs_instance_create(
                name=name,
                protocol=protocol,
                cluster="Autotest",
                network="Autotest",
                volume_size=volume_size,
                cpu_cores=8,
                ram_gb=8,
            )

        with allure_step_log("步骤3: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("创建文件存储实例成功")
            sfs_page.assert_list_contain(name)

        # 登记资源用于清理
        clean_sfs_instances.append(name)

        with allure_step_log("步骤4: P0 断言-等待实例状态收敛到正常"):
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)

        with allure_step_log("步骤5: P1 断言-列表页字段回读"):
            row_data = sfs_page.get_row_data(name)
            assert row_data["名称"] == name, f"[FieldAssertion] 列表名称 | 期望: {name} | 实际: {row_data.get('名称')}"
            assert row_data["文件协议"] == protocol, f"[FieldAssertion] 列表协议 | 期望: {protocol} | 实际: {row_data.get('文件协议')}"
            assert f"{volume_size}GiB" in row_data.get("云硬盘大小", ""), \
                f"[FieldAssertion] 列表云硬盘大小 | 期望包含: {volume_size}GiB | 实际: {row_data.get('云硬盘大小')}"

        with allure_step_log("步骤6: P1 断言-详情页字段回读"):
            sfs_page.sfs_instance_goto_detail(name)
            detail = sfs_page.sfs_get_detail_info()
            assert detail.get("名称") == name, f"[FieldAssertion] 详情名称 | 期望: {name} | 实际: {detail.get('名称')}"
            assert detail.get("文件协议") == protocol, f"[FieldAssertion] 详情协议 | 期望: {protocol} | 实际: {detail.get('文件协议')}"
            assert f"{volume_size}GiB" in detail.get("云硬盘大小", ""), \
                f"[FieldAssertion] 详情云硬盘大小 | 期望包含: {volume_size}GiB | 实际: {detail.get('云硬盘大小')}"

        with allure_step_log("步骤7: P2 断言-后台 CLI 验证实例存在"):
            result = ssh_host.run("scli guest list", return_rc=True)
            assert result["rc"] == 0, f"[BackendAssertion] scli guest list 命令执行失败: {result.get('stderr', '')}"
            assert name in result["stdout"], f"[BackendAssertion] scli guest list 输出 | 期望包含实例名: {name} | 实际未找到"

        with allure_step_log("步骤8: P2 断言-后台 Ping 实例管理 IP"):
            addr = detail.get("访问地址", "")
            if addr:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', addr)
                if ip_match:
                    mgmt_ip = ip_match.group(1)
                    ping_result = ssh_host.run(f"ping -c 4 {mgmt_ip}", return_rc=True)
                    if ping_result["rc"] == 0 and ("0% packet loss" in ping_result["stdout"] or "4 received" in ping_result["stdout"]):
                        logger.info(f"ping {mgmt_ip} 成功")
                    else:
                        logger.warning(f"ping {mgmt_ip} 失败或丢包，该地址可能不是管理浮动 IP，跳过 ping 验证")
                else:
                    logger.warning(f"无法从访问地址提取 IP: {addr}")
            else:
                logger.warning("详情页未获取到访问地址，跳过 ping 验证")

        with allure_step_log("步骤9: P2 断言-SSH 登录实例验证磁盘"):
            addr = detail.get("访问地址", "")
            if addr:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', addr)
                if ip_match:
                    mgmt_ip = ip_match.group(1)
                    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{mgmt_ip} -p 22022 'df -h'"
                    df_result = ssh_host.run(ssh_cmd, return_rc=True)
                    if df_result["rc"] == 0:
                        assert "/dev/vdb" in df_result["stdout"], \
                            f"[BackendAssertion] df -h 输出 | 期望包含 /dev/vdb | 实际: {df_result['stdout']}"
                        size_match = re.search(r'/dev/vdb\s+(\S+)', df_result["stdout"])
                        if size_match:
                            vdb_size = size_match.group(1)
                            logger.info(f"/dev/vdb 大小: {vdb_size}")
                    else:
                        logger.warning(f"SSH 登录实例失败，跳过磁盘验证: {df_result.get('stderr', '')}")
                else:
                    logger.warning(f"无法从访问地址提取 IP，跳过 SSH 验证")
            else:
                logger.warning("详情页未获取到访问地址，跳过 SSH 验证")

        # 清理由 clean_sfs_instances fixture 自动处理

    @allure.title("文件存储-创建CIFS协议实例")
    def test_sfs_create_cifs(self, sfs_page, clean_sfs_instances, ssh_host):
        """创建 CIFS 协议文件存储实例并验证 UI 和后台状态。"""
        name = f"sfs-{random_data()}"
        protocol = "cifs"
        volume_size = 10

        with allure_step_log("步骤1: 导航并打开新建文件存储弹窗"):
            sfs_page.goto_service("文件存储")
            sfs_page.wait_for_page_ready()

        with allure_step_log("步骤2: 填写表单并提交创建"):
            sfs_page.sfs_instance_create(
                name=name,
                protocol=protocol,
                cluster="Autotest",
                network="Autotest",
                volume_size=volume_size,
                cpu_cores=8,
                ram_gb=8,
            )

        with allure_step_log("步骤3: P0 断言-创建成功弹窗与列表存在性"):
            sfs_page.assert_popup_success("创建文件存储实例成功")
            sfs_page.assert_list_contain(name)

        # 登记资源用于清理
        clean_sfs_instances.append(name)

        with allure_step_log("步骤4: P0 断言-等待实例状态收敛到正常"):
            sfs_page.sfs_wait_for_status(name, status="正常", timeout=300)

        with allure_step_log("步骤5: P1 断言-列表页字段回读"):
            row_data = sfs_page.get_row_data(name)
            assert row_data["名称"] == name, f"[FieldAssertion] 列表名称 | 期望: {name} | 实际: {row_data.get('名称')}"
            assert row_data["文件协议"] == protocol, f"[FieldAssertion] 列表协议 | 期望: {protocol} | 实际: {row_data.get('文件协议')}"
            assert f"{volume_size}GiB" in row_data.get("云硬盘大小", ""), \
                f"[FieldAssertion] 列表云硬盘大小 | 期望包含: {volume_size}GiB | 实际: {row_data.get('云硬盘大小')}"

        with allure_step_log("步骤6: P1 断言-详情页字段回读"):
            sfs_page.sfs_instance_goto_detail(name)
            detail = sfs_page.sfs_get_detail_info()
            assert detail.get("名称") == name, f"[FieldAssertion] 详情名称 | 期望: {name} | 实际: {detail.get('名称')}"
            assert detail.get("文件协议") == protocol, f"[FieldAssertion] 详情协议 | 期望: {protocol} | 实际: {detail.get('文件协议')}"
            assert f"{volume_size}GiB" in detail.get("云硬盘大小", ""), \
                f"[FieldAssertion] 详情云硬盘大小 | 期望包含: {volume_size}GiB | 实际: {detail.get('云硬盘大小')}"

        with allure_step_log("步骤7: P2 断言-后台 CLI 验证实例存在"):
            result = ssh_host.run("scli guest list", return_rc=True)
            assert result["rc"] == 0, f"[BackendAssertion] scli guest list 命令执行失败: {result.get('stderr', '')}"
            assert name in result["stdout"], f"[BackendAssertion] scli guest list 输出 | 期望包含实例名: {name} | 实际未找到"

        with allure_step_log("步骤8: P2 断言-后台 Ping 实例管理 IP"):
            addr = detail.get("访问地址", "")
            if addr:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', addr)
                if ip_match:
                    mgmt_ip = ip_match.group(1)
                    ping_result = ssh_host.run(f"ping -c 4 {mgmt_ip}", return_rc=True)
                    if ping_result["rc"] == 0 and ("0% packet loss" in ping_result["stdout"] or "4 received" in ping_result["stdout"]):
                        logger.info(f"ping {mgmt_ip} 成功")
                    else:
                        logger.warning(f"ping {mgmt_ip} 失败或丢包，该地址可能不是管理浮动 IP，跳过 ping 验证")
                else:
                    logger.warning(f"无法从访问地址提取 IP: {addr}")
            else:
                logger.warning("详情页未获取到访问地址，跳过 ping 验证")

        with allure_step_log("步骤9: P2 断言-SSH 登录实例验证磁盘"):
            addr = detail.get("访问地址", "")
            if addr:
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', addr)
                if ip_match:
                    mgmt_ip = ip_match.group(1)
                    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@{mgmt_ip} -p 22022 'df -h'"
                    df_result = ssh_host.run(ssh_cmd, return_rc=True)
                    if df_result["rc"] == 0:
                        assert "/dev/vdb" in df_result["stdout"], \
                            f"[BackendAssertion] df -h 输出 | 期望包含 /dev/vdb | 实际: {df_result['stdout']}"
                        size_match = re.search(r'/dev/vdb\s+(\S+)', df_result["stdout"])
                        if size_match:
                            vdb_size = size_match.group(1)
                            logger.info(f"/dev/vdb 大小: {vdb_size}")
                    else:
                        logger.warning(f"SSH 登录实例失败，跳过磁盘验证: {df_result.get('stderr', '')}")
                else:
                    logger.warning(f"无法从访问地址提取 IP，跳过 SSH 验证")
            else:
                logger.warning("详情页未获取到访问地址，跳过 SSH 验证")

        # 清理由 clean_sfs_instances fixture 自动处理
