import allure
import pytest
from sugon_web.utils.logger import logger, allure_step_log

@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclScenario:

    @allure.title("网络ACL关联子网: 网络ACL列表关联子网")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": False, "sub2_acl": False}], indirect=True)
    def test_acl_associate_subnet_acl(self, acl_vpc_vms, acl_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景1：网络ACL列表，选择预置的ACL关联子网sub1。
        关联完成后ssh_vm连接虚机b，进行ping虚机a，预期是不通。
        """
        env = acl_vpc_vms
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        vm_a_ip = vm_a_info["ip"]
        vm_b_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log(f"步骤1: ACL列表，关联子网{env['sub1_name']}"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_associate_subnet(acl_name, env["sub1_name"])
        
        with allure_step_log("步骤2: ssh_vm连接虚机b，进行ping虚机a，预期不通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=False, count=5)

        with allure_step_log("步骤3: acl创建入方向规则，允许ping"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")
            
        with allure_step_log("步骤4: 验证ping通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=True, count=5)

    @allure.title("网络ACL关联子网: VPC页面关联ACL策略")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": True, "sub2_acl": False}], indirect=True)
    def test_acl_associate_subnet_vpc(self, acl_vpc_vms, acl_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景2：新建vpc关联acl策略选择预置的acl，vpc新建子网sub2不关联预置的acl。
        基于这两个sub创建虚机a、b，ssh_vm连接虚机b，ping虚机a，预期是不通。
        """
        env = acl_vpc_vms
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        vm_a_ip = vm_a_info["ip"]
        vm_b_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机b，进行ping虚机a，预期不通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=False, count=5)
        
        with allure_step_log("步骤2: acl创建入方向规则，允许ping"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")
            
        with allure_step_log("步骤3: 验证ping通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=True, count=5)


    @allure.title("网络ACL关联子网: VPC新建子网页面关联ACL策略")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": False, "sub2_acl": True}], indirect=True)
    def test_acl_associate_subnet_sub(self, acl_vpc_vms, acl_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景3：新建vpc不关联acl策略，vpc新建子网sub2关联预置的acl。
        基于这两个sub创建虚机a、b，ssh_vm连接虚机b，ping虚机a，预期不通。
        """
        env = acl_vpc_vms
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        vm_b_ip = vm_b_info["ip"]
        vm_a_mfip = vm_a_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机b，进行ping虚机a，预期不通"):
            ssh_vm.connect(host=vm_a_mfip)
            ssh_vm.ping(vm_b_ip, connected=False, count=5)

        with allure_step_log("步骤2: acl创建入方向规则，允许ping"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")
            
        with allure_step_log("步骤3: 验证ping通"):
            ssh_vm.connect(host=vm_a_mfip)
            ssh_vm.ping(vm_b_ip, connected=True, count=5)

    @allure.title("网络ACL: 取消关联子网")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": False, "sub2_acl": True}], indirect=True)
    def test_acl_disassociate_subnet(self, acl_vpc_vms, acl_page, ssh_vm):
        """
        前置：存在ACL，默认无任何规则，同一vpc下子网A、B。子网B已关联ACL，且ACL下没有任何规则。
        步骤1：ssh_vm连接虚机vm2(B子网下)，ping 虚机vm1(A子网下)，预期是不通。
        步骤2：acl取消关联子网B。检查关联子网列表无数据
        步骤3：ssh_vm连接虚机vm2，ping 虚机vm1，预期是通。
        """
        env = acl_vpc_vms
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        vm_a_ip = vm_a_info["ip"]
        vm_b_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]
        sub2_name = env["sub2_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机vm2，ping 虚机vm1，预期是不通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=False, count=5)

        with allure_step_log(f"步骤2+3: acl取消关联子网B ({sub2_name})，且关联子网列表应无该数据"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_disassociate_subnet(acl_name, subnets=[sub2_name])

        with allure_step_log("步骤4: ssh_vm连接虚机vm2，ping 虚机vm1，预期是通"):
            ssh_vm.connect(host=vm_b_mfip)
            ssh_vm.ping(vm_a_ip, connected=True, count=5)

    @allure.title("验证ACL新建入方向规则: 新建-允许全部")
    def test_acl_create_inbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：存在ACL，vpc下的两个子网A、B（分别存在2台云服务器实例，A下vm_a_0, vm_a_1，B下vm_b_0, vm_b_1）
        步骤1：入方向新建规则：源IP：vm_a_0的ip及不包含vm_a_0的段，目的IP：vm_b_0的ip及不包含vm_b_0的段，允许ALL
        步骤2：vm_a_0 ping vm_b_0 预期通
        步骤3：vm_a_0 ping vm_b_1 预期不通
        步骤4：vm_b_0 ping vm_a_0 预期不通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]
        
        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")
        vm_b_1 = next(vm for vm in env["vms"] if vm["tag"] == "B-1")

        # 使用一个无关网段 (如: 192.168.254.0/24 肯定不包含现有的 10.x.x.x)
        # 用换行符隔开多个IP/CIDR在文本域中
        source_ips = f"{vm_a_0['ip']}\n99.99.99.0/24"
        dest_ips = f"{vm_b_0['ip']}\n99.99.99.0/24"

        with allure_step_log("步骤1: ACL下新建复杂入方向规则"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_create(
                acl_name=acl_name,
                source_ip=source_ips,
                dest_ip=dest_ips,
                description="新建入方向允许全部的ipv4规则"
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vm1-0, 执行ping vm2-0，预期是可以通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=True, count=5)
            ssh_vm.ping(vm_b_1["ip"], connected=False, count=5)

        with allure_step_log("步骤3: ssh_vm连接虚机vm2-0, 执行ping vm1-0，预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)

    @allure.title("验证ACL操作入方向规则: 关闭-开启")
    def test_acl_disable_enable_inbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：基于test_acl_create_inbound_rule创建的允许全部入方向规则
        场景1：关闭规则，验证不通
        场景2：开启规则，验证通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 将允许全部的入方向规则进行操作-关闭"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_disable(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm1-0, ping虚机vm2-0，预期是不通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=False, count=5)

        with allure_step_log("步骤3: 将允许全部的入方向规则进行操作-开启"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_enable(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤4: ssh_vm连接虚机vm1-0, ping虚机vm2-0，预期是通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=True, count=5)

    @allure.title("验证ACL修改入方向规则: 修改目的IP和策略")
    def test_acl_edit_inbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：基于test_acl_create_inner_rule创建的入方向规则
        场景1：修改目的地址
        场景2：修改策略为拒绝
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]
        
        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")
        vm_b_1 = next(vm for vm in env["vms"] if vm["tag"] == "B-1")

        # -----------------------------
        # 场景1：修改acl入方向的规则，其它信息不变
        # 将目的地址修改为：包含vm2的ip地址，以及包含vm2-1的地址段
        # -----------------------------
        dest_ips_modified = f"{vm_b_0['ip']}\n{vm_b_1['ip']}/32"

        with allure_step_log("步骤1: 修改ACL入方向规则，将目的IP改为包含vm2-0以及涵盖vm2-1的地址段"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_edit(
                acl_name=acl_name,
                direction="入方向",
                new_dest_ip=dest_ips_modified
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vm1-0, ping 虚机vm2-0, vm2-1，预期是通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=True, count=5)
            ssh_vm.ping(vm_b_1["ip"], connected=True, count=5)

        # -----------------------------
        # 场景2：修改入方向规则，策略改为拒绝
        # -----------------------------
        with allure_step_log("步骤3: 修改入方向规则，将策略修改为拒绝"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_edit(
                acl_name=acl_name,
                direction="入方向",
                new_policy="拒绝"
            )

        with allure_step_log("步骤4: ssh_vm连接虚机vm1-0, ping 虚机vm2-0, vm2-1，预期是不通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=False, count=5)
            ssh_vm.ping(vm_b_1["ip"], connected=False, count=5)

    @allure.title("验证ACL操作入方向规则: 删除规则")
    def test_acl_delete_inbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：基于test_acl_create_inbound_rule创建的入方向规则（因复用fixture，当前为编辑后的拒绝状态）
        场景1：删除该入方向规则
        场景2：验证vm1-0 ping vm2-0不通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 删除由于前置用例遗留下的入方向规则"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_delete(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm1-0, ping 虚机vm2-0, 预期是不通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=False, count=5)

    @allure.title("验证ACL新建出方向规则: 新建-允许全部")
    def test_acl_create_outbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：存在ACL，vpc下的两个子网A、B（分别存在2台云服务器实例，A下vm_a_0, vm_a_1，B下vm_b_0, vm_b_1）
        步骤1：出方向新建规则：源IP：vm_b_0的ip及不包含vm_b_0的段，目的IP：vm_a_0的ip及不包含vm_a_0的段，允许ALL
        步骤2：vm_b_0 ping vm_a_0 预期通
        步骤3：vm_b_0 ping vm_a_1 预期不通
        步骤4：vm_a_0 ping vm_b_0 预期不通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]
        
        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_a_1 = next(vm for vm in env["vms"] if vm["tag"] == "A-1")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        # 使用一个无关网段确保复杂的文本包含逻辑正常
        source_ips = f"{vm_b_0['ip']}\n99.99.99.0/24"
        dest_ips = f"{vm_a_0['ip']}\n99.99.99.0/24"

        with allure_step_log("步骤1: ACL下新建出方向规则"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_create(
                acl_name=acl_name,
                direction="出方向",
                source_ip=source_ips,
                dest_ip=dest_ips,
                description="新建出方向允许全部的ipv4规则"
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, 执行ping vm1-0，预期是可以通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=True, count=5)
            ssh_vm.ping(vm_a_1["ip"], connected=False, count=5)

        with allure_step_log("步骤3: ssh_vm连接虚机vm1-0, 执行ping vm2-0，预期是不通"):
            ssh_vm.connect(vm_a_0["mfip"])
            ssh_vm.ping(vm_b_0["ip"], connected=False, count=5)

    @allure.title("验证ACL操作出方向规则: 关闭-开启")
    def test_acl_disable_enable_outbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的允许全部出方向规则
        场景1：关闭规则，验证不通
        场景2：开启规则，验证通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 将允许全部的出方向规则进行操作-关闭"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_disable(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, ping虚机vm1-0，预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)

        with allure_step_log("步骤3: 将允许全部的出方向规则进行操作-开启"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_enable(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤4: ssh_vm连接虚机vm2-0, ping虚机vm1-0，预期是通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=True, count=5)

    @allure.title("验证ACL修改出方向规则: 修改目的IP和策略")
    def test_acl_edit_outbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的出方向规则
        场景1：修改目的地址
        场景2：修改策略为拒绝
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]
        
        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_a_1 = next(vm for vm in env["vms"] if vm["tag"] == "A-1")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        # -----------------------------
        # 场景1：修改acl出方向的规则，其它信息不变
        # 将目的地址修改为：包含vm1的ip地址，以及包含vm1-1的地址段
        # -----------------------------
        dest_ips_modified = f"{vm_a_0['ip']}\n{vm_a_1['ip']}/32"

        with allure_step_log("步骤1: 修改ACL出方向规则，将目的IP改为包含vm1-0以及涵盖vm1-1的地址段"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_edit(
                acl_name=acl_name,
                direction="出方向",
                new_dest_ip=dest_ips_modified
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, ping 虚机vm1-0, vm1-1，预期是通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=True, count=5)
            ssh_vm.ping(vm_a_1["ip"], connected=True, count=5)

        # -----------------------------
        # 场景2：修改出方向规则，策略改为拒绝
        # -----------------------------
        with allure_step_log("步骤3: 修改出方向规则，将策略修改为拒绝"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_edit(
                acl_name=acl_name,
                direction="出方向",
                new_policy="拒绝"
            )

        with allure_step_log("步骤4: ssh_vm连接虚机vm2-0, ping 虚机vm1-0, vm1-1，预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)
            ssh_vm.ping(vm_a_1["ip"], connected=False, count=5)

    @allure.title("验证ACL操作出方向规则: 删除规则")
    def test_acl_delete_outbound_rule(self, acl_in_out_bound_rules, acl_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的出方向规则（因复用fixture，当前为编辑后的拒绝状态）
        场景1：删除该出方向规则
        场景2：验证vm2-0 ping vm1-0不通
        """
        env = acl_in_out_bound_rules
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 删除由于前置用例遗留下的出方向规则"):
            acl_page.goto_service("网络ACL")
            acl_page.acl_rule_delete(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, ping 虚机vm1-0, 预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)
