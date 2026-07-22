import allure
import pytest
import ipaddress
import random
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data, load_data

@allure.epic('网络服务')
@allure.feature('负载均衡')
@allure.story('基本功能验证')
class TestSlbBasic:

    @allure.title("SLB创建: {params[case_desc]}")
    @pytest.mark.parametrize("params", load_data("test_slb_create_orthogonal", "test_slb.yaml"))
    def test_slb_create_orthogonal(self, vpc_page, vpc, params):
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
            vpc_page.slb_create(
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
            vpc_page.assert_popup_success(expected_msg)
            vpc_page.assert_status(slb_name, status="运行中")

        with allure_step_log(f"步骤3: 删除负载均衡 {slb_name}"):
            vpc_page.slb_delete(slb_name)
            vpc_page.assert_deleted(slb_name)


    @allure.title("监听器创建: {params[case_desc]}")
    @pytest.mark.parametrize("params", load_data("test_slb_listener_create", "test_slb.yaml"))
    def test_slb_listener_create(self, vpc_page, slb, params):
        """
        测试不同协议下的监听器创建，当前覆盖 TCP、UDP、HTTP。
        HTTPS 和 ACL 参数暂未做参数化覆盖，保留参数组装入口，便于扩展。
        """
        lb_name = f"lb-{params['protocol'].lower()}-{params['port']}"
        create_kwargs = {
            "slb_name": slb["name"],
            "lb_name": lb_name,
            "protocol": params["protocol"],
            "port": params["port"],
            "desc": params.get("desc", f"Autotest listener {lb_name}"),
            "acl_enable": params.get("acl_enable", False),
            "access_policy": params.get("access_policy"),
            "ip_group": params.get("ip_group"),
            "pool_name": params.get("pool_name"),
            "balance_method": params.get("balance_method", "轮询"),
            "health_check": params.get("health_check", False),
            "session_persistence": params.get("session_persistence", False),
            "session_type": params.get("session_type"),
            "health_type": params.get("health_type"),
            "health_max_retries": params.get("health_max_retries"),
            "health_timeout": params.get("health_timeout"),
            "health_interval": params.get("health_interval"),
            "http_method": params.get("http_method"),
            "url_path": params.get("url_path"),
            "auth_mode": params.get("auth_mode", "单向认证"),
            "cert_type": params.get("cert_type", "国际服务器证书"),
            "server_cert": params.get("server_cert"),
            "ca_cert": params.get("ca_cert"),
            "http_redirect": params.get("http_redirect", False),
            "redirect_port": params.get("redirect_port"),
        }

        with allure_step_log(f"步骤1: 为负载均衡 {slb['name']} 创建 {params['protocol']} 监听器 {lb_name}"):
            vpc_page.slb_lb_create(**create_kwargs)

        with allure_step_log("步骤2: 验证监听器创建成功"):
            # 验证弹出框成功提示
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")

            # 验证监听器是否在左侧列表显示 (slb_lb_create 执行完后应该仍在详情页的监听器Tab)
            vpc_page.assert_listener_exists(lb_name)

        with allure_step_log(f"步骤3: 删除监听器 {lb_name}"):
            vpc_page.slb_lb_delete(slb["name"], lb_name)
            vpc_page.assert_popup_success(f"删除监听器 {lb_name} 成功")

    @allure.title("通过SLB列表页进入监听器详情页")
    def test_goto_lb_detail_from_slb_list(self, vpc_page, slb):
        lb_name = f"lb-tcp-{random_data()}"

        with allure_step_log(f"步骤1: 为负载均衡 {slb['name']} 创建监听器 {lb_name}"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=80,
                desc=f"Autotest listener {lb_name}",
                pool_name=f"pool-{random_data()}",
                balance_method="轮询",
                health_check=False
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)

        with allure_step_log(f"步骤2: 从SLB列表页进入监听器 {lb_name} 详情页"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.assert_listener_exists(lb_name)
            vpc_page.assert_lb_basic_info(lb_name)

        with allure_step_log(f"步骤3: 删除监听器 {lb_name}"):
            vpc_page.slb_lb_delete(slb["name"], lb_name)
            vpc_page.assert_popup_success(f"删除监听器 {lb_name} 成功")

    @allure.title("监听器详情编辑名称")
    def test_lb_detail_edit_name(self, vpc_page, lb):
        original_name = lb["name"]
        new_name = f"{original_name}-edit"

        with allure_step_log(f"步骤1: 进入监听器 {original_name} 详情页"):
            vpc_page.slb_list_goto_lb_detail(lb["slb_name"], lb["name"])

        with allure_step_log(f"步骤2: 将监听器名称从 {original_name} 修改为 {new_name}"):
            vpc_page.lb_edit_basic_info(original_name, "name", new_name=new_name)
            lb["name"] = new_name

        with allure_step_log("步骤3: 校验名称修改结果"):
            vpc_page.assert_listener_exists(new_name)
            vpc_page.assert_lb_basic_info(new_name)

    @allure.title("监听器详情编辑描述")
    def test_lb_detail_edit_description(self, vpc_page, lb):
        new_desc = "autotest listener description"

        with allure_step_log(f"步骤1: 修改监听器 {lb['name']} 的描述"):
            vpc_page.slb_list_goto_lb_detail(lb["slb_name"], lb["name"])
            vpc_page.lb_edit_basic_info(lb["name"], "description", new_desc=new_desc)
            lb["desc"] = new_desc

        with allure_step_log("步骤2: 校验描述修改结果"):
            vpc_page.assert_lb_basic_info(new_desc)

    @allure.title("监听器详情编辑前端端口")
    @pytest.mark.parametrize("new_port", [65535, 8080, 443, 1])
    def test_lb_detail_edit_frontend_protocol_port(self, vpc_page, lb, new_port):

        with allure_step_log(f"步骤1: 将监听器 {lb['name']} 的端口修改为 {new_port}"):
            vpc_page.slb_list_goto_lb_detail(lb["slb_name"], lb["name"])
            vpc_page.lb_edit_basic_info(lb["name"], "port", protocol="TCP", port=new_port)
            vpc_page.assert_popup_success()
            lb["port"] = new_port

        with allure_step_log("步骤2: 校验端口修改结果"):
            vpc_page.assert_lb_basic_info(f"TCP/{new_port}")

    @allure.title("监听器详情编辑访问控制")
    def test_lb_detail_edit_access_control(self, vpc_page, lb, ip_group):
        with allure_step_log(f"步骤1: 为监听器 {lb['name']} 启用访问控制"):
            vpc_page.slb_list_goto_lb_detail(lb["slb_name"], lb["name"])
            vpc_page.lb_edit_basic_info(
                lb["name"],
                "access_control",
                enable=True,
                access_policy="白名单",
                ip_group=ip_group["name"],
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 校验访问控制开启结果"):
            vpc_page.assert_lb_basic_info("白名单")

        with allure_step_log("步骤3: 关闭访问控制，避免影响 IP 地址组清理"):
            vpc_page.lb_edit_basic_info(lb["name"], "access_control", enable=False)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤4: 校验访问控制关闭结果"):
            vpc_page.assert_lb_basic_info("允许所有IP访问")

@allure.epic('网络服务')
@allure.feature('负载均衡')
@allure.story('基本功能验证')
class TestSlbDelete:
    @allure.title("SLB删除前存在监听器时删除失败，删除监听器后可删除SLB")
    def test_slb_delete_with_lb(self, vpc_page, slb):
        lb_name = f"lb-tcp-{random_data()}"

        with allure_step_log(f"步骤1: 为负载均衡 {slb['name']} 创建监听器 {lb_name}"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="TCP",
                port=80,
                desc=f"Autotest listener {lb_name}",
                pool_name=f"pool-{random_data()}",
                balance_method="轮询",
                health_check=False
            )
            vpc_page.assert_popup_success(f"新建监听器 {lb_name} 成功")
            vpc_page.assert_listener_exists(lb_name)

        with allure_step_log(f"步骤2: 删除仍存在监听器的负载均衡 {slb['name']}，校验失败提示"):
            vpc_page.goto_submenu("负载均衡（基础版）")
            vpc_page.slb_delete(slb["name"])
            vpc_page.assert_slb_dialog_error("该负载均衡存在监听器,不允许删除", "共删除1项，删除失败1项")

        with allure_step_log(f"步骤3: 进入负载均衡 {slb['name']} 详情删除监听器 {lb_name}"):
            vpc_page.goto_slb_detail(slb["name"], "监听器")
            vpc_page.slb_lb_delete(slb["name"], lb_name)
            vpc_page.assert_popup_success(f"删除监听器 {lb_name} 成功")

        with allure_step_log(f"步骤4: 再次删除负载均衡 {slb['name']}"):
            vpc_page.slb_delete(slb["name"])
            vpc_page.assert_deleted(slb["name"])
