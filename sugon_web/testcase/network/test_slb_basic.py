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


