import time

import allure
import pytest
from sugon_web.testcase.network._acl_helpers import build_acl_env
from sugon_web.testcase.network._acl_fixtures import (
    clean_acl_inbound_rules,
    clean_acl_inbound_rules_4vms,
    clean_acl_outbound_rules,
)
from sugon_web.utils.logger import logger, allure_step_log


ACL_VM_PAIR_PARAMS = {
    "inject_dependencies": False,
    "instances": [
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.subnet_name"}]}},
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.extra_subnets[0].name"}]}},
    ],
}

ACL_VM_4_INSTANCE_PARAMS = {
    "inject_dependencies": False,
    "instances": [
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.subnet_name"}]}},
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.subnet_name"}]}},
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.extra_subnets[0].name"}]}},
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.extra_subnets[0].name"}]}},
    ],
}
@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclAssociateSubnetAcl:
    @allure.title("网络ACL关联子网: 网络ACL列表关联子网")
    @pytest.mark.parametrize(
        "vpc",
        [{"cidr": "10.242.1.0/24", "extra_subnets": [{"cidr": "10.242.2.0/24"}]}],
        indirect=True,
    )
    @pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
    def test_acl_associate_subnet_acl(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景1：网络ACL列表，选择预置的ACL关联子网sub1。
        关联完成后ssh_vm连接虚机b，进行ping虚机a，预期是不通。
        """
        env = build_acl_env(acl, vpc, vm)
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vma_ip = vm_a_info["ip"]
        vmb_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log(f"步骤1: ACL列表，关联子网{env['sub1_name']}"):
            vpc_page.acl_associate_subnet(acl_name, env["sub1_name"])

        with allure_step_log("步骤2: ssh_vm连接虚机b，进行ping虚机a，预期不通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=False, count=5)

        with allure_step_log("步骤3: acl创建入方向规则，允许ping"):
            vpc_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")

        with allure_step_log("步骤4: 验证ping通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=True, count=5)


@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclAssociateVpcAcl:
    @allure.title("网络ACL关联子网: VPC页面关联ACL策略")
    @pytest.mark.parametrize(
        "vpc",
        [{"cidr": "10.243.1.0/24", "acl_policy": "@acl", "extra_subnets": [{"cidr": "10.243.2.0/24"}]}],
        indirect=True,
    )
    @pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
    def test_acl_associate_subnet_vpc(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景2：新建vpc关联acl策略选择预置的acl，vpc新建子网sub2不关联预置的acl。
        基于这两个sub创建虚机a、b，ssh_vm连接虚机b，ping虚机a，预期是不通。
        """
        env = build_acl_env(acl, vpc, vm)
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vma_ip = vm_a_info["ip"]
        vmb_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机b，进行ping虚机a，预期不通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=False, count=5)

        with allure_step_log("步骤2: acl创建入方向规则，允许ping"):
            vpc_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")

        with allure_step_log("步骤3: 验证ping通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=True, count=5)


@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
@pytest.mark.parametrize(
    "vpc",
    [{"cidr": "10.244.1.0/24", "extra_subnets": [{"cidr": "10.244.2.0/24", "acl_policy": "@acl"}]}],
    indirect=True,
)
@pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
class TestAclSubnetAclReuse:
    @allure.title("网络ACL关联子网: VPC新建子网页面关联ACL策略")
    def test_acl_associate_subnet_sub(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景3：新建vpc不关联acl策略，vpc新建子网sub2关联预置的acl。
        基于这两个sub创建虚机a、b，ssh_vm连接虚机b，ping虚机a，预期不通。
        """
        env = build_acl_env(acl, vpc, vm)
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vmb_ip = vm_b_info["ip"]
        vma_mfip = vm_a_info["mfip"]
        acl_name = env["acl_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机a,进行ping虚机b,预期不通"):
            ssh_vm.connect(vma_mfip)
            ssh_vm.ping(vmb_ip, connected=False, count=5)

        with allure_step_log("步骤2: acl创建入方向规则"):
            vpc_page.acl_rule_create(acl_name, direction="入方向", ip_version="IPv4", policy="允许", protocol="ICMP")

        with allure_step_log("步骤3: ssh_vm连接虚机a,进行ping虚机b,验证ping通"):
            ssh_vm.connect(vma_mfip)
            ssh_vm.ping(vmb_ip, connected=True, count=5)

    @allure.title("网络ACL: 取消关联子网")
    def test_acl_disassociate_subnet(self, acl, vpc, vm, vpc_page, ssh_vm):
        """
        前置：存在ACL，默认无任何规则，同一vpc下子网A、B。子网B已关联ACL，且ACL下没有任何规则。
        步骤1：ssh_vm连接虚机vma(B子网下)，ping 虚机vma(A子网下)，预期是不通。
        步骤2：acl取消关联子网B。检查关联子网列表无数据
        步骤3：ssh_vm连接虚机vmb，ping 虚机vma，预期是通。
        """
        env = build_acl_env(acl, vpc, vm)
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vma_ip = vm_a_info["ip"]
        vmb_mfip = vm_b_info["mfip"]
        acl_name = env["acl_name"]
        sub2_name = env["sub2_name"]

        with allure_step_log("步骤1: ssh_vm连接虚机vmb,ping 虚机vma,预期是不通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=False, count=5)

        with allure_step_log(f"步骤2: acl取消关联子网B ({sub2_name}),验证关联子网列表应无该数据"):
            vpc_page.acl_disassociate_subnet(acl_name, subnets=[sub2_name])

        with allure_step_log("步骤3: ssh_vm连接虚机vmb,ping 虚机vma，预期是通"):
            ssh_vm.connect(vmb_mfip)
            ssh_vm.ping(vma_ip, connected=True, count=5)

@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
@pytest.mark.parametrize(
    "vpc",
    [{"cidr": "10.246.1.0/24", "extra_subnets": [{"cidr": "10.246.2.0/24", "acl_policy": "@acl"}]}],
    indirect=True,
)
@pytest.mark.parametrize("vm", [ACL_VM_4_INSTANCE_PARAMS], indirect=True)
class TestAclRuleReuse:

    @allure.title("验证ACL新建入方向规则: 新建-允许全部")
    def test_acl_create_inbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：存在ACL，vpc下的两个子网A、B（分别存在2台云服务器实例，A下vma0, vma1，B下vmb0, vmb1）
        步骤1：入方向新建规则：源IP：vma0的ip及不含vma0的段，目的IP：vmb0的ip及不含vmb0的段，允许ALL
        步骤2：vma0 ping vmb0 预期通
        步骤3：vma0 ping vmb1 预期不通
        步骤4：vmb0 ping vma0 预期不通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vma0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vmb0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")
        vmb1 = next(vm for vm in env["vms"] if vm["tag"] == "B-1")

        # 使用一个无关网段 (如: 99.99.99.0/24)
        source_ips = f"{vma0['ip']}\n99.99.99.0/24"
        dest_ips = f"{vmb0['ip']}\n99.99.99.0/24"

        with allure_step_log("步骤1: ACL下新建入方向规则"):
            vpc_page.acl_rule_create(
                acl_name=acl_name,
                source_ip=source_ips,
                dest_ip=dest_ips,
                description="新建入方向允许全部的ipv4规则"
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vma0, 执行ping vmb0，预期是可以通"):
            ssh_vm.connect(vma0["mfip"])
            ssh_vm.ping(vmb0["ip"], connected=True, count=5)
            ssh_vm.ping(vmb1["ip"], connected=False, count=5)

        with allure_step_log("步骤3: ssh_vm连接虚机vmb0, 执行ping vma0，预期是不通"):
            ssh_vm.connect(vmb0["mfip"])
            ssh_vm.ping(vma0["ip"], connected=False, count=5)

    @allure.title("验证ACL操作入方向规则: 关闭-开启")
    def test_acl_disable_enable_inbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：基于test_acl_create_inbound_rule创建的允许全部入方向规则
        场景1：关闭规则，验证不通
        场景2：开启规则，验证通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vma0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vmb0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 将允许全部的入方向规则进行操作-关闭"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_disable(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vma0, ping虚机vmb0，预期是不通"):
            ssh_vm.connect(vma0["mfip"])
            ssh_vm.ping(vmb0["ip"], connected=False, count=5)

        with allure_step_log("步骤3: 将允许全部的入方向规则进行操作-开启"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_enable(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤4: ssh_vm连接虚机vma0, ping虚机vmb0，预期是通"):
            ssh_vm.connect(vma0["mfip"])
            ssh_vm.ping(vmb0["ip"], connected=True, count=5)

    @allure.title("验证ACL修改入方向规则: 修改目的IP和策略")
    def test_acl_edit_inbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        前置：基于test_acl_create_inner_rule创建的入方向规则
        场景1：修改目的地址
        场景2：修改策略为拒绝
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vma0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vmb0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")
        vmb1 = next(vm for vm in env["vms"] if vm["tag"] == "B-1")

        dest_ips_modified = f"{vmb0['ip']}\n{vmb1['ip']}/32"

        with allure_step_log("步骤1: 修改ACL入方向规则，将目的IP改为包含vmb0以及涵盖vmb1的地址段"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_edit(
                acl_name=acl_name,
                direction="入方向",
                new_dest_ip=dest_ips_modified
            )

        with allure_step_log("步骤2: ssh_vm连接虚机vma0, ping 虚机vmb0、vmb1，预期是通"):
            ssh_vm.connect(vma0["mfip"])
            ssh_vm.ping(vmb0["ip"], connected=True, count=5)
            ssh_vm.ping(vmb1["ip"], connected=True, count=5)

        with allure_step_log("步骤3: 修改入方向规则，将策略修改为拒绝"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_edit(
                acl_name=acl_name,
                direction="入方向",
                new_policy="拒绝"
            )

        with allure_step_log("步骤4: ssh_vm连接虚机vma0, ping 虚机vmb0、vmb1，预期是不通"):
            ssh_vm.connect(vma0["mfip"])
            ssh_vm.ping(vmb0["ip"], connected=False, count=5)
            ssh_vm.ping(vmb1["ip"], connected=False, count=5)

    @allure.title("验证ACL操作入方向规则: 删除规则")
    def test_acl_delete_inbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules_4vms):
        """
        场景1：删除入方向的所有规则
        场景2：创建入方向允许所有的规则。ssh_vm连接虚机vma-0，ping 虚机vmb-0，预期是通
        场景3：删除acl入方向的规则
        场景4：ssh_vm连接虚机vma-0，ping 虚机vmb-0，预期是不通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vma_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vmb_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 删除入方向的所有规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.goto_acl_detail(acl_name, tab_name="入方向规则")
            # 循环删除所有入方向规则
            while vpc_page.get_by_role("row").filter(has=vpc_page.get_by_text("删除", exact=True)).count() > 0:
                vpc_page.acl_rule_delete(acl_name, direction="入方向")

        with allure_step_log("步骤2: 创建入方向允许所有的规则，并验证通"):
            vpc_page.acl_rule_create(
                acl_name=acl_name,
                direction="入方向",
                source_ip="0.0.0.0/0",
                dest_ip="0.0.0.0/0",
                description="允许所有的入方向规则"
            )
            ssh_vm.connect(vma_0["mfip"])
            ssh_vm.ping(vmb_0["ip"], connected=True, count=5)

        with allure_step_log("步骤3: 删除acl入方向的规则"):
            vpc_page.acl_rule_delete(acl_name=acl_name, direction="入方向")

        with allure_step_log("步骤4: ssh_vm连接虚机vma-0，ping 虚机vmb-0，预期是不通"):
            ssh_vm.connect(vma_0["mfip"])
            ssh_vm.ping(vmb_0["ip"], connected=False, count=5)

    @allure.title("验证ACL新建出方向规则: 新建-允许全部")
    def test_acl_create_outbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：存在ACL，vpc下的两个子网A、B（分别存在2台云服务器实例，A下vm_a_0, vm_a_1，B下vm_b_0, vm_b_1）
        步骤1：出方向新建规则：源IP：vm_b_0的ip及不包含vm_b_0的段，目的IP：vm_a_0的ip及不包含vm_a_0的段，允许ALL
        步骤2：vm_b_0 ping vm_a_0 预期通
        步骤3：vm_b_0 ping vm_a_1 预期不通
        步骤4：vm_a_0 ping vm_b_0 预期不通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_a_1 = next(vm for vm in env["vms"] if vm["tag"] == "A-1")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        # 使用一个无关网段确保复杂的文本包含逻辑正常
        source_ips = f"{vm_b_0['ip']}\n99.99.99.0/24"
        dest_ips = f"{vm_a_0['ip']}\n99.99.99.0/24"

        with allure_step_log("步骤1: ACL下新建出方向规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_create(
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
    def test_acl_disable_enable_outbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的允许全部出方向规则
        场景1：关闭规则，验证不通
        场景2：开启规则，验证通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 将允许全部的出方向规则进行操作-关闭"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_disable(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, ping虚机vm1-0，预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)

        with allure_step_log("步骤3: 将允许全部的出方向规则进行操作-开启"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_enable(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤4: ssh_vm连接虚机vm2-0, ping虚机vm1-0，预期是通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=True, count=5)

    @allure.title("验证ACL修改出方向规则: 修改目的IP和策略")
    def test_acl_edit_outbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的出方向规则
        场景1：修改目的地址
        场景2：修改策略为拒绝
        """
        env = build_acl_env(acl, vpc, vm)
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
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_edit(
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
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_edit(
                acl_name=acl_name,
                direction="出方向",
                new_policy="拒绝"
            )

        with allure_step_log("步骤4: ssh_vm连接虚机vm2-0, ping 虚机vm1-0, vm1-1，预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)
            ssh_vm.ping(vm_a_1["ip"], connected=False, count=5)

    @allure.title("验证ACL操作出方向规则: 删除规则")
    def test_acl_delete_outbound_rule(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_outbound_rules):
        """
        前置：基于test_acl_create_outbound_rule创建的出方向规则（因复用fixture，当前为编辑后的拒绝状态）
        场景1：删除该出方向规则
        场景2：验证vm2-0 ping vm1-0不通
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]

        vm_a_0 = next(vm for vm in env["vms"] if vm["tag"] == "A-0")
        vm_b_0 = next(vm for vm in env["vms"] if vm["tag"] == "B-0")

        with allure_step_log("步骤1: 删除由于前置用例遗留下的出方向规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_delete(acl_name=acl_name, direction="出方向")

        with allure_step_log("步骤2: ssh_vm连接虚机vm2-0, ping 虚机vm1-0, 预期是不通"):
            ssh_vm.connect(vm_b_0["mfip"])
            ssh_vm.ping(vm_a_0["ip"], connected=False, count=5)

@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclBatchScenario:

    @allure.title("验证ACL出方向规则: 批量关闭和开启规则")
    @pytest.mark.parametrize(
        "vpc",
        [{"cidr": "10.247.1.0/24", "extra_subnets": [{"cidr": "10.247.2.0/24", "acl_policy": "@acl"}]}],
        indirect=True,
    )
    @pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
    def test_acl_outbound_rules_scenario(self, acl, vpc, vm, vpc_page, ssh_vm):
        """
        场景：
        1. 存在ACL关联子网B，子网A无ACL。
        2. 新增3条出方向规则：
           - 规则1: IPv4, 允许, TCP, 源:子网B的cidr, 源端口:8081, 目的:子网A的cidr, 目的端口:8080-8090
           - 规则2: IPv4, 允许, TCP, 源:子网B的cidr, 源端口:8082, 目的:子网A的cidr, 目的端口:8080
           - 规则3: IPv4, 允许, ICMP, 源:子网B的cidr, 目的:子网A的cidr
        3. vm1(A) 启动 8080 端口服务。
        4. vm2(B) 验证 ping 通，curl 结合 --local-port 8081/8082 通。
        5. 批量关闭规则。
        6. 验证不通。
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]
        cidr_a = env["cidr1"]
        cidr_b = env["cidr2"]

        vm1 = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm2 = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vm1_ip = vm1["ip"]
        vm1_mfip = vm1["mfip"]
        vm2_mfip = vm2["mfip"]

        rule_matches = [
            {"protocol": "TCP", "source_port": "8081", "dest_port": "8080-8090", "source_ip": cidr_b, "dest_ip": cidr_a},
            {"protocol": "TCP", "source_port": "8082", "dest_port": "8080", "source_ip": cidr_b, "dest_ip": cidr_a},
            {"protocol": "ICMP", "source_ip": cidr_b, "dest_ip": cidr_a}
        ]

        with allure_step_log("步骤1: 新建3条出方向规则"):
            vpc_page.goto_submenu("网络ACL")
            # 规则1
            vpc_page.acl_rule_create(acl_name, direction="出方向", protocol="TCP", source_ip=cidr_b, source_port="8081", dest_ip=cidr_a, dest_port="8080-8090")
            # 规则2
            vpc_page.acl_rule_create(acl_name, direction="出方向", protocol="TCP", source_ip=cidr_b, source_port="8082", dest_ip=cidr_a, dest_port="8080")
            # 规则3
            vpc_page.acl_rule_create(acl_name, direction="出方向", protocol="ICMP", source_ip=cidr_b, dest_ip=cidr_a)

        with allure_step_log("步骤2: vm1连接并执行 python server"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.run("nohup python3 -m http.server 8080 > /dev/null 2>&1 </dev/null & disown", check_rc=True)

            # 循环检查服务是否启动
            with allure_step_log("等待vm1上的http服务启动"):
                for i in range(6):
                    time.sleep(10)
                    res = ssh_vm.run("netstat -anp | grep :8080 | grep LISTEN")
                    out = res['stdout'] if isinstance(res, dict) else res
                    if "LISTEN" in out:
                        logger.info(f"http server started after {i*10+10}s")
                        break
                else:
                    raise RuntimeError(f"vm1上的http服务超过{60}s未启动")

        with allure_step_log("步骤3: vm2 验证流量连通性"):
            ssh_vm.connect(vm2_mfip)
            # ping 验证
            ssh_vm.ping(vm1_ip, connected=True, count=5)

            curl_success = "Directory listing for /"
            # curl 验证 --local-port 8081
            stdout_8081 = ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8081", check_rc=True)
            assert curl_success in stdout_8081, f"curl {vm1_ip}:8080 --local-port 8081失败: {stdout_8081}"

            # curl 验证 --local-port 8082
            stdout_8082 = ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8082", check_rc=True)
            assert curl_success in stdout_8082, f"curl {vm1_ip}:8080 --local-port 8082失败: {stdout_8082}"

        with allure_step_log("步骤4: 批量关闭规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_batch_operation(acl_name, direction="出方向", rule_matches=rule_matches, operation="关闭")

        with allure_step_log("步骤5: 验证流量不通"):
            ssh_vm.connect(vm2_mfip)
            # ping 验证不通
            ssh_vm.ping(vm1_ip, connected=False, count=3)
            # curl 验证不通 --local-port 8081
            try:
                ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8081", check_rc=True)
                assert False, f"curl {vm1_ip}:8080 --local-port 8081异常成功"
            except Exception:
                logger.info("规则关闭后，curl --local-port 8081 失败，预期正常")

            # curl 验证不通 --local-port 8082
            try:
                ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8082", check_rc=True)
                assert False, f"curl {vm1_ip}:8080 --local-port 8082异常成功"
            except Exception:
                logger.info("规则关闭后，curl --local-port 8082 失败，预期正常")

        with allure_step_log("步骤6: 批量启用规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_batch_operation(acl_name, direction="出方向", rule_matches=rule_matches, operation="启用")

        with allure_step_log("步骤7: 再次验证流量连通性"):
            ssh_vm.connect(vm2_mfip)
            # ping 验证
            ssh_vm.ping(vm1_ip, connected=True, count=5)
            # curl 验证
            res_8081 = ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8081", check_rc=True)
            assert curl_success in res_8081, f"重新开启规则后，curl {vm1_ip}:8080 --local-port 8081 失败"

            res_8082 = ssh_vm.run(f"curl -s --connect-timeout 5 {vm1_ip}:8080 --local-port 8082", check_rc=True)
            assert curl_success in res_8082, f"重新开启规则后，curl {vm1_ip}:8080 --local-port 8082 失败"

    @allure.title("验证ACL入方向规则: 批量开启和关闭规则")
    @pytest.mark.parametrize(
        "vpc",
        [{"cidr": "10.248.1.0/24", "extra_subnets": [{"cidr": "10.248.2.0/24", "acl_policy": "@acl"}]}],
        indirect=True,
    )
    @pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
    def test_acl_inbound_batch_op_scenario(self, acl, vpc, vm, vpc_page, ssh_vm, clean_acl_inbound_rules):
        """
        场景：
        1. 存在ACL关联子网B，子网A无ACL。
        2. 新增3条入方向规则（允许：TCP 8081->8080-8090, UDP 8082->1-65535, ICMP）。
        3. vm2(B) 启动 8080 端口服务和 8888 UDP服务。
        4. vm1(A) 验证连通性（ping, curl, nc-udp）。
        5. 批量关闭规则，验证不通。
        6. 批量开启规则，验证通 (按照已批准的 plan 执行)。
        """
        env = build_acl_env(acl, vpc, vm)
        acl_name = env["acl_name"]
        cidr_a = env["cidr1"]
        cidr_b = env["cidr2"]

        vm1 = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm2 = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vm2_ip = vm2["ip"]
        vm1_mfip = vm1["mfip"]
        vm2_mfip = vm2["mfip"]

        rule_matches = [
            {"protocol": "TCP", "source_port": "8081", "dest_port": "8080-8090", "source_ip": cidr_a, "dest_ip": cidr_b},
            {"protocol": "UDP", "source_port": "8082", "dest_port": "1-65535", "source_ip": cidr_a, "dest_ip": cidr_b},
            {"protocol": "ICMP", "source_ip": cidr_a, "dest_ip": cidr_b}
        ]

        with allure_step_log("步骤1: 新建3条入方向规则"):
            vpc_page.goto_submenu("网络ACL")
            # 规则1: TCP
            vpc_page.acl_rule_create(acl_name, direction="入方向", protocol="TCP", source_ip=cidr_a, source_port="8081", dest_ip=cidr_b, dest_port="8080-8090")
            # 规则2: UDP
            vpc_page.acl_rule_create(acl_name, direction="入方向", protocol="UDP", source_ip=cidr_a, source_port="8082", dest_ip=cidr_b, dest_port="1-65535", detail_mode=True)
            # 规则3: ICMP
            vpc_page.acl_rule_create(acl_name, direction="入方向", protocol="ICMP", source_ip=cidr_a, dest_ip=cidr_b, detail_mode=True)

        with allure_step_log("步骤2: vm2启动 TCP (8080) 和 UDP (8888) 服务"):
            ssh_vm.connect(vm2_mfip)
            ssh_vm.run("nohup python3 -m http.server 8080 > /dev/null 2>&1 </dev/null & disown", check_rc=True)
            ssh_vm.run("nohup nc -vul 8888 > /dev/null 2>&1 </dev/null & disown", check_rc=True)

            # 轮询等待服务可用
            with allure_step_log("等待vm2上的服务启动"):
                for i in range(10):  # 最多等待50秒
                    time.sleep(5)
                    out_tcp = ssh_vm.run("netstat -anp | grep :8080 | grep LISTEN")
                    out_udp = ssh_vm.run("netstat -anp | grep :8888 | grep udp")
                    if "LISTEN" in out_tcp and "8888" in out_udp:
                        logger.info(f"vm2 服务已在 {i*5+5}s 后成功启动")
                        break
                else:
                    raise RuntimeError(f"vm2 服务启动超时: TCP({out_tcp}), UDP({out_udp})")

        with allure_step_log("步骤3: vm1 验证流量连通性 (TCP/UDP/ICMP)"):
            ssh_vm.connect(vm1_mfip)
            # ICMP
            ssh_vm.ping(vm2_ip, connected=True, count=3)
            # TCP (Local Port 8081)
            curl_success = "Directory listing for /"
            stdout_tcp = ssh_vm.run(f"curl -s --connect-timeout 5 {vm2_ip}:8080 --local-port 8081", check_rc=True)
            assert curl_success in stdout_tcp, f"vm1 -> vm2:8080 curl失败: {stdout_tcp}"
            # UDP (Local Port 8082)
            ssh_vm.run(f"echo 'test' | nc -vu -p 8082 -w 3 {vm2_ip} 8888", check_rc=True)

        with allure_step_log("步骤4: 批量关闭入方向规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_batch_operation(acl_name, direction="入方向", rule_matches=rule_matches, operation="关闭")

        with allure_step_log("步骤5: 验证流量全部不通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=False, count=3)
            try:
                ssh_vm.run(f"curl -s --connect-timeout 5 {vm2_ip}:8080 --local-port 8081", check_rc=True)
                assert False, "TCP 仍通畅，异常"
            except Exception:
                logger.info("TCP 已阻断，正常")
            try:
                ssh_vm.run(f"echo 'test' | nc -vu -p 8082 -w 2 {vm2_ip} 8888", check_rc=True)
                assert False, "UDP 仍通畅，异常"
            except Exception:
                logger.info("UDP 已阻断，正常")

        with allure_step_log("步骤6: 批量开启入方向规则"):
            vpc_page.goto_submenu("网络ACL")
            vpc_page.acl_rule_batch_operation(acl_name, direction="入方向", rule_matches=rule_matches, operation="启用")

        with allure_step_log("步骤7: 再次验证流量连通性"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=True, count=3)
            res_tcp = ssh_vm.run(f"curl -s --connect-timeout 5 {vm2_ip}:8080 --local-port 8081", check_rc=True)
            assert curl_success in res_tcp, "重新开启规则后 TCP 不通"
            ssh_vm.run(f"echo 'test' | nc -vu -p 8082 -w 3 {vm2_ip} 8888", check_rc=True)
            logger.info("重新开启规则后 UDP 恢复连通")
