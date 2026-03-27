import allure
import pytest
import ipaddress
import random
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data

@allure.epic('网络服务')
@allure.feature('负载均衡')
@allure.story('基本功能验证')
class TestSlbCreate:

    @allure.title("SLB创建: {params[case_desc]}")
    @pytest.mark.parametrize("params", load_data("test_slb_create_orthogonal", "test_slb.yaml"))
    def test_slb_create_orthogonal(self, slb_page, vpc, params):
        vpc_name = vpc["name"]
        cidr = vpc["cidr"]
        
        # 处理 IP 地址相关逻辑
        ip_address = None
        if params["ip_type"] in ["快速选择", "手动输入"]:
            if "ip_address" in params:
                ip_address = params["ip_address"]
            else:
                # 动态获取当前选定VPC/子网的真实CIDR可用IP
                network = ipaddress.ip_network(cidr, strict=False)
                hosts = list(network.hosts())
                # 避开前10个和最后10个地址以防网关或保留IP冲突
                safe_hosts = hosts[10:-10] if len(hosts) > 20 else hosts
                ip_address = str(random.choice(safe_hosts)) 
            
        slb_name = f"slb-{random_data()}"
        
        with allure_step_log(f"步骤1: 创建负载均衡 {slb_name}"):
            slb_page.slb_create(
                name=slb_name,
                version=params["version"],
                ha_enable=params["ha_enable"],
                ip_type=params["ip_type"],
                ip_address=ip_address,
                vpc=vpc_name,
                cluster=params.get("cluster"),
                spec=params.get("spec"),
                desc=params.get("slb_desc", f"Autotest created SLB {slb_name}")
            )
        
        with allure_step_log("步骤2: 验证负载均衡状态"):
            expected_msg = f"新建负载均衡 {slb_name} 成功" if params["version"] == "V1" else "新建负载均衡成功"
            slb_page.assert_popup_success(expected_msg)
            slb_page.assert_status(slb_name, status="运行中")
            
        with allure_step_log(f"步骤3: 删除负载均衡 {slb_name}"):
            slb_page.slb_delete(slb_name)
            slb_page.assert_deleted(slb_name)


    @allure.title("监听器创建: {params[case_desc]}")
    @pytest.mark.parametrize("params", load_data("test_slb_listener_create", "test_slb.yaml"))
    def test_slb_listener_create(self, slb_page, slb, params):
        """
        测试不同协议下的监听器创建，覆盖 TCP, UDP, HTTP。暂未覆盖 HTTPS (单向/双向认证)
        """
        lb_name = f"lb-{params['protocol'].lower()}-{params['port']}"
        
        # 准备 HTTPS 特定参数
        # kwargs = {}
        # if params['protocol'] == "HTTPS":
        #     kwargs.update({
        #         "auth_mode": params.get("auth_mode", "单向认证"),
        #         "cert_type": params.get("cert_type", "国际服务器证书"),
        #         "server_cert": params.get("server_cert"),
        #         "ca_cert": params.get("ca_cert"),
        #         "http_redirect": params.get("http_redirect", False),
        #         "redirect_port": params.get("redirect_port")
        #     })

        with allure_step_log(f"步骤1: 为负载均衡 {slb} 创建 {params['protocol']} 监听器 {lb_name}"):
            slb_page.slb_lb_create(
                slb_name=slb,
                lb_name=lb_name,
                protocol=params["protocol"],
                port=params["port"],
                pool_name=params.get("pool_name"),
                balance_method=params.get("balance_method", "轮询"),
                health_check=params.get("health_check", False),
                session_persistence=params.get("session_persistence", False),
                session_type=params.get("session_type"),
                health_type=params.get("health_type"),
                health_max_retries=params.get("health_max_retries"),
                health_timeout=params.get("health_timeout"),
                health_interval=params.get("health_interval"),
                http_method=params.get("http_method"),
                url_path=params.get("url_path"),
                # **kwargs
            )

        with allure_step_log("步骤2: 验证监听器创建成功"):
            # 验证弹出框成功提示
            slb_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            
            # 验证监听器是否在左侧列表显示 (slb_lb_create 执行完后应该仍在详情页的监听器Tab)
            slb_page.assert_listener_exists(lb_name)

        with allure_step_log(f"步骤3: 删除监听器 {lb_name}"):
            slb_page.slb_lb_delete(slb, lb_name)
            slb_page.assert_popup_success(f"删除监听器 {lb_name} 成功")
