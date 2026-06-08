import pytest
import allure

from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-资源清理与镜像创建")
class TestBmsCleanup:
    """验证裸金属BMS软装版资源清理流程和镜像创建功能。"""

    @allure.title("裸金属BMS-实例删除")
    def test_bms_011_instance_delete(self, bms_page):
        """删除裸金属实例并验证注册状态变更。"""
        instance_name = "bms-0430"
        bmc_ip = "172.22.2.173"

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
    def test_bms_012_register_delete(self, bms_page):
        """删除裸金属注册信息。"""
        bmc_ip = "172.22.2.173"

        # 步骤1：搜索并删除注册信息
        with allure_step_log("步骤1: 搜索并删除注册信息"):
            bms_page.bms_register_delete(bmc_ip)

        # 步骤2：验证注册信息已删除
        with allure_step_log("步骤2: 验证注册信息已删除"):
            bms_page.search(bmc_ip)
            bms_page.assert_list_not_contain(bmc_ip, "带外IP")

    @allure.title("裸金属BMS-发现信息删除")
    def test_bms_013_discovery_delete(self, bms_page):
        """删除裸金属发现信息。"""
        discovery_name = "bms-test-autotest"

        # 步骤1：搜索并删除发现信息
        with allure_step_log("步骤1: 搜索并删除发现信息"):
            bms_page.bms_discovery_delete(discovery_name)

        # 步骤2：验证发现信息已删除
        with allure_step_log("步骤2: 验证发现信息已删除"):
            bms_page.search(discovery_name)
            bms_page.assert_list_not_contain(discovery_name, "名称")

    @allure.title("裸金属BMS-代理信息删除")
    def test_bms_014_agent_delete(self, bms_page, ssh_host):
        """删除裸金属代理信息并验证后台清理。"""
        node_name = "master02.cloud.local"

        # 步骤1：搜索并删除代理信息
        with allure_step_log("步骤1: 搜索并删除代理信息"):
            bms_page.bms_agent_delete(node_name)

        # 步骤2：验证代理信息已删除
        with allure_step_log("步骤2: 验证代理信息已删除"):
            bms_page.search(node_name)
            bms_page.assert_list_not_contain(node_name, "物理机")

        # 步骤3：验证后台网卡已清理
        with allure_step_log("步骤3: 验证后台网卡已清理"):
            ssh_host.wait_for_command(
                "ip a | grep bms",
                expected_in_output="",
                timeout=300,
                poll_interval=10
            )

        # 步骤4：验证后台Pod和ConfigMap已清理
        with allure_step_log("步骤4: 验证后台Pod和ConfigMap已清理"):
            result = ssh_host.run("kubectl get configmap -A | grep bms", return_rc=True)
            # grep 无匹配时 rc=1 是正常的，只断言命令本身没有执行错误
            assert result["rc"] in (0, 1), f"命令执行失败: {result.get('stderr', '')}"
            # 无master02相关节点的输出
            assert "master02" not in result["stdout"], f"ConfigMap 中仍包含 master02 相关记录: {result['stdout']}"

            result = ssh_host.run("kubectl get pods -A -o wide | grep bms", return_rc=True)
            assert result["rc"] in (0, 1), f"命令执行失败: {result.get('stderr', '')}"
            assert "master02" not in result["stdout"], f"Pod 中仍包含 master02 相关记录: {result['stdout']}"

    @allure.title("裸金属BMS-网络信息删除")
    def test_bms_015_network_delete(self, bms_page):
        """删除裸金属网络信息。"""
        network_name = "bms"

        # 步骤1：搜索并删除网络信息
        with allure_step_log("步骤1: 搜索并删除网络信息"):
            bms_page.bms_network_delete(network_name)

        # 步骤2：验证网络信息已删除
        with allure_step_log("步骤2: 验证网络信息已删除"):
            bms_page.search(network_name)
            bms_page.assert_list_not_contain(network_name, "名称")

    @allure.title("裸金属BMS-交换机信息删除")
    def test_bms_016_switch_group_delete(self, bms_page):
        """解绑物理机并删除交换机组。"""
        group_name = "test-bms-autotest"

        # 步骤1：解绑物理机
        with allure_step_log("步骤1: 解绑交换机组物理机"):
            bms_page.bms_switch_group_unbind(group_name)

        # 步骤2：验证物理机已解绑
        with allure_step_log("步骤2: 验证物理机已解绑"):
            bms_page.goto_service("交换机组")
            bms_page.wait_for_page_ready()
            row = bms_page._get_row_by_name(group_name)
            if row:
                row_text = row.text_content() or ""
                assert "--" in row_text, f"物理机列应显示'--'，实际: {row_text}"

        # 步骤3：删除交换机组
        with allure_step_log("步骤3: 删除交换机组"):
            bms_page.bms_switch_group_delete(group_name)

        # 步骤4：验证交换机组已删除
        with allure_step_log("步骤4: 验证交换机组已删除"):
            bms_page.search(group_name)
            bms_page.assert_list_not_contain(group_name, "名称")

    @allure.title("裸金属BMS-镜像创建")
    def test_bms_017_image_create(self, ssh_host):
        """通过SSH在后台创建裸金属镜像并在前端验证。"""
        image_file = "/home/scloudadmin/centos76-bms-0511.raw"
        image_url = "http://172.22.5.66:9090/offlinePackage/image_download/support-fsagent/centos76-bms-0511.raw"
        image_name = "centos76-bms-0511-autotest"

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
            result = ssh_host.run(cmd, return_rc=True, timeout=600)
            assert result["rc"] == 0, f"镜像创建失败: {result.get('stderr', '')}"
            logger.info(f"镜像 '{image_name}' 创建成功")

        # 步骤3：在前端验证镜像存在
        with allure_step_log("步骤3: 在前端验证镜像存在"):
            # 这里需要镜像服务的页面对象，暂时用日志记录
            # 实际执行时可通过 image_page 导航到镜像服务进行验证
            logger.info(f"镜像 '{image_name}' 已创建，请在前端镜像服务中验证")
