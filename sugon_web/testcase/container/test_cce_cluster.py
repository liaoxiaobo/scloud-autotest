import re
import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data, load_data


@allure.epic('容器服务')
@allure.feature('云容器引擎')
@allure.story('集群管理')
class TestCCEClusterCreate:

    @allure.title("集群管理-创建CCE集群-{params[network_model]}网络-{params[version]}版本-{params[container_runtime]}运行时")
    @pytest.mark.parametrize("params", load_data("test_cce_create", data_file='test_cce.yaml'))
    def test_cce_create(self, cce_page, ssh_host, ssh_vm, params):
        """测试创建CCE集群并验证后端配置（参数化）"""

        cluster_name = f"cce-{random_data(length=3)}"
        node_count = params['node_count']
        version = params['version']
        container_runtime = params['container_runtime']
        proxy_mode = params['proxy_mode']
        network_model = params['network_model']
        volume_size = params['volume_size']
        flavor = params['flavor']

        with allure_step_log(f"步骤1: 创建CCE集群 ({cluster_name}) {network_model}网络-{version}版本"):
            cce_page.cce_create(
                name=cluster_name,
                node_count=node_count,
                version=version,
                container_runtime=container_runtime,
                proxy_mode=proxy_mode,
                desc="测试cce",
                network_model=network_model,
                volume_size=volume_size,
                flavor=flavor
            )
            cce_page.assert_popup_success()
            cce_page.assert_status(cluster_name, status="运行中", timeout=1200)

        with allure_step_log("步骤2: 验证集群节点列表数据"):
            node_data = cce_page.get_cluster_node_data(cluster_name)
            if node_data:
                assert len(node_data) == node_count, f"节点数量不一致: 期望 {node_count}, 实际 {len(node_data)}"
                for node in node_data:
                    assert flavor in node.get("规格", ""), f"节点规格不一致: 期望包含 {flavor}"
            else:
                logger.info("UI节点列表未显示，跳过UI验证，后续通过SSH验证节点数量")

        with allure_step_log("步骤3: 连接集群节点并验证后端配置"):
            if node_data:
                first_node = node_data[0]
                fixed_ip = first_node.get("内网IP")
            else:
                detail_tab = cce_page.page.locator(".el-tabs__item").filter(has_text="详情")
                if detail_tab.count() > 0:
                    detail_tab.first.click()
                    cce_page.page.wait_for_timeout(500)
                body_text = cce_page.page.locator("body").inner_text()
                network_section = re.search(r"网络信息([\s\S]*?)(?:公网域名|存储类型|集群事件|告警历史)", body_text)
                if network_section:
                    ip_match = re.search(r"(\d+\.\d+\.\d+\.\d+)", network_section.group(1))
                    fixed_ip = ip_match.group(1) if ip_match else ""
                else:
                    fixed_ip = ""
            assert fixed_ip and fixed_ip != "--", f"未获取到内网IP"
            mfip = ssh_host.find_mfip(fixed_ip)
            logger.info(f"节点内网IP: {fixed_ip}, MFIP: {mfip}")

            ssh_vm.connect(mfip, port=22022, pwd="admin1234@sugon")

            # 3.1 验证节点数量、Kubernetes版本、容器运行时
            result = ssh_vm.run("kubectl get nodes -o wide", return_rc=True)
            assert result["rc"] == 0, f"kubectl get nodes 执行失败: {result.get('stderr', '')}"
            node_lines = [l for l in result["stdout"].splitlines() if "Ready" in l]
            assert len(node_lines) == node_count, f"节点数量不一致: 期望 {node_count}, 实际 {len(node_lines)}"
            assert version in result["stdout"], f"版本不一致: 期望 {version}"
            assert container_runtime in result["stdout"], f"容器运行时不一致: 期望 {container_runtime}"

            # 3.2 验证容器网络模型
            if network_model == "flannel":
                result = ssh_vm.run("kubectl get pods -n kube-system | grep flannel", return_rc=True)
                assert result["rc"] == 0, f"flannel pod查询失败: {result.get('stderr', '')}"
                assert "flannel" in result["stdout"], f"未找到flannel pod: {result['stdout']}"
            elif network_model == "calico":
                result = ssh_vm.run("kubectl get pods -n kube-system | grep calico", return_rc=True)
                assert result["rc"] == 0, f"calico pod查询失败: {result.get('stderr', '')}"
                assert "calico" in result["stdout"], f"未找到calico pod: {result['stdout']}"

            # 3.3 验证服务发现网段配置存在
            result = ssh_vm.run(
                "cat /etc/kubernetes/manifests/kube-apiserver.yaml | grep service-cluster-ip-range",
                return_rc=True
            )
            assert result["rc"] == 0, f"查询service-cluster-ip-range失败: {result.get('stderr', '')}"

        with allure_step_log("步骤4: 清理测试数据"):
            cce_page.cce_delete(cluster_name)
            cce_page.assert_deleted(cluster_name)
            ssh_host.wait_vm_deleted(cluster_name, timeout=600)
            ssh_host.wait_volume_deleted(cluster_name, timeout=600)
