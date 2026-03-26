import allure
import pytest
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data

@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclBasic:

    @allure.title("验证新建与删除网络ACL功能")
    def test_acl_create_delete(self, acl_page):
        acl_name = f"acl_{random_data()}"

        with allure_step_log(f"步骤1: 新建网络ACL"):
            acl_page.acl_create(acl_name, desc=f"创建网络ACL{acl_name}")
            acl_page.assert_status(acl_name, status="开启")

        with allure_step_log(f"步骤2: 单个删除网络ACL"):
            acl_page.acl_delete(acl_name)
            acl_page.assert_deleted(acl_name)

    @allure.title("验证搜索网络ACL功能")
    def test_acl_search(self, acl_page, acl):
        acl_name = acl
        with allure_step_log(f"步骤1: 搜索网络ACL: {acl_name}"):
            acl_page.acl_search(acl_name)
            
            # 使用模糊匹配断言列表中包含搜索关键字
            acl_page.assert_list_contain(acl_name, exact_match=False)

        with allure_step_log(f"步骤2: 重置搜索条件"):
            acl_page.acl_search_reset()
            # 断言重置后列表有数据
            acl_page.get_column_data("名称")

    @allure.title("验证编辑网络ACL功能")
    def test_acl_edit(self, acl_page, acl):
        acl_name = acl
        new_name = f"{acl_name}-edit"
        new_desc = f"巨长的描述：{acl_name}{random_data(length=260)}"

        with allure_step_log(f"步骤1: 选定网络ACL进行修改: {acl_name} -> {new_name}"):
            acl_page.acl_edit(acl_name, new_name=new_name, new_desc=new_desc)
            acl_page.assert_popup_success()
            
            # 搜索后验证修改是否成功
            acl_page.acl_search(new_name)
            acl_page.assert_list_contain(new_name, exact_match=False)

        with allure_step_log(f"步骤2: 恢复网络ACL名称: {new_name} -> {acl_name}"):
            acl_page.acl_search_reset()
            acl_page.acl_edit(new_name, new_name=acl_name)
            acl_page.assert_popup_success()
            acl_page.acl_search(acl_name)
            acl_page.assert_list_contain(acl_name, exact_match=False)
            acl_page.acl_search_reset()

    @allure.title("验证开启和关闭单条网络ACL及流量生效情况")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": False, "sub2_acl": True}], indirect=True)
    def test_acl_enable_disable(self, acl_vpc_vms, acl_page, ssh_vm):
        env = acl_vpc_vms
        acl_name = env["acl_name"]
        
        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        vm_a_ip = vm_a_info["ip"]
        vm_b_ip = vm_b_info["ip"]
        vm_a_mfip = vm_a_info["mfip"]
        vm_b_mfip = vm_b_info["mfip"]

        try:
            with allure_step_log("步骤1: ACL下新建入方向规则"):
                acl_page.goto_service("网络ACL")
                acl_page.acl_rule_create(
                    acl_name=acl_name,
                    source_ip=env["cidr1"],
                    dest_ip=env["cidr2"],
                    description="Allow Sub1 to Sub2"
                )

            with allure_step_log("步骤2: 生效验证: 虚机A 能ping通虚机B, 虚机B 不能ping通虚机A"):
                ssh_vm.connect(vm_a_mfip)
                ssh_vm.ping(vm_b_ip, connected=True, count=5)
                ssh_vm.connect(vm_b_mfip)
                ssh_vm.ping(vm_a_ip, connected=False, count=5)

            with allure_step_log("步骤3: 关闭ACL,虚机A、B不能互通"):
                acl_page.acl_disable(acl_name)
                ssh_vm.connect(vm_a_mfip)
                ssh_vm.ping(vm_b_ip, connected=False, count=5)
                ssh_vm.connect(vm_b_mfip)
                ssh_vm.ping(vm_a_ip, connected=False, count=5)

            with allure_step_log("步骤4: 重新开启ACL"):
                acl_page.acl_enable(acl_name)
                ssh_vm.connect(vm_a_mfip)
                ssh_vm.ping(vm_b_ip, connected=True, count=5)

            with allure_step_log("步骤5: 验证重新开启后: 虚机B ping 虚机A,期望可以ping通"):
                ssh_vm.connect(vm_b_mfip)
                ssh_vm.ping(vm_a_ip, connected=True, count=5)

        finally:
            with allure_step_log("清理: 删除测试创建的入方向规则"):
                try:
                    acl_page.goto_service("网络ACL")
                    acl_page.acl_rule_delete(acl_name, direction="入方向")
                except Exception as e:
                    from sugon_web.utils.logger import logger
                    logger.warning(f"删除规则失败: {e}")

    @allure.title("验证批量开启、关闭和删除网络ACL功能")
    def test_acl_batch_operations(self, acl_page):

        with allure_step_log(f"步骤1: 新建第二个参与批量的网络ACL"):
            base_name = random_data()
            acl_names = [f"acl-batch-{base_name}-{i}" for i in range(3)]
            [acl_page.acl_create(name) for name in acl_names]

        with allure_step_log(f"步骤2: 批量关闭网络ACL"):
            acl_page.acl_batch_disable(acl_names)
            
        with allure_step_log(f"步骤3: 批量开启网络ACL"):
            acl_page.acl_batch_enable(acl_names)
            
        with allure_step_log(f"步骤4: 批量删除测试临时生成的网络ACL"):
            acl_page.acl_batch_delete(acl_names)
            acl_page.assert_deleted(acl_names)

    @allure.title("验证批量开启和关闭网络ACL及流量生效情况")
    @pytest.mark.parametrize("acl_vpc_vms", [{"vpc_acl": False, "sub2_acl": True}], indirect=True)
    def test_acl_batch_op_connectivity(self, acl_vpc_vms, acl_page, ssh_vm):
        """
        前置：存在至少3个ACL实例，如ACL1、ACL2、ACL3，vpc下的两个子网A和子网B，两个子网下分别各存在一台云服务器实例vma、vmb。ACL1已关联子网B。
        步骤1：ACL1下新建入方向规则（允许 Sub A -> Sub B）
        步骤2：ssh_vm连接虚机vma，ping虚机vmb。预期是通。ssh_vm连接虚机vmb，ping虚机vma,预期是不通。
        步骤3：批量关闭前置创建的3个ACL。重复步骤2，预期是均不通。
        步骤4：批量开启3个acl,重复步骤2，预期是a能通b，b不能通a。
        """
        env = acl_vpc_vms
        acl_name = env["acl_name"]
        
        vma = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vmb = next(vm for vm in env["vms"] if vm["tag"] == "B")
        
        # 步骤1: 新组建3个ACL的批量环境
        base_name = random_data()
        extra_acl_names = [f"acl-extra-{base_name}-{i}" for i in range(2)]
        all_acl_names = [acl_name] + extra_acl_names
        
        try:
            with allure_step_log(f"前置: 创建额外的ACL {extra_acl_names}"):
                for name in extra_acl_names:
                    acl_page.acl_create(name)

            with allure_step_log("步骤1: ACL1下新建入方向规则 (允许 Sub A -> Sub B)"):
                acl_page.goto_service("网络ACL")
                acl_page.acl_rule_create(
                    acl_name=acl_name,
                    source_ip=env["cidr1"],
                    dest_ip=env["cidr2"],
                    description="Batch Test: Allow Sub1 to Sub2"
                )

            with allure_step_log("步骤2: 虚机A 能ping通虚机B, 虚机B 不能ping通虚机A"):
                ssh_vm.connect(vma["mfip"])
                ssh_vm.ping(vmb["ip"], connected=True, count=5)
                ssh_vm.connect(vmb["mfip"])
                ssh_vm.ping(vma["ip"], connected=False, count=5)

            with allure_step_log(f"步骤3: 批量关闭网络ACL {all_acl_names}"):
                acl_page.goto_service("网络ACL")
                acl_page.acl_batch_disable(all_acl_names)
                
                with allure_step_log("验证关闭后流量均不通"):
                    ssh_vm.connect(vma["mfip"])
                    ssh_vm.ping(vmb["ip"], connected=False, count=5)
                    ssh_vm.connect(vmb["mfip"])
                    ssh_vm.ping(vma["ip"], connected=False, count=5)

            with allure_step_log(f"步骤4: 批量开启网络ACL {all_acl_names}"):
                acl_page.goto_service("网络ACL")
                acl_page.acl_batch_enable(all_acl_names)
                
                with allure_step_log("验证开启后流量恢复 (A->B通, B->A不通)"):
                    ssh_vm.connect(vma["mfip"])
                    ssh_vm.ping(vmb["ip"], connected=True, count=5)
                    ssh_vm.connect(vmb["mfip"])
                    ssh_vm.ping(vma["ip"], connected=False, count=5)

        finally:
            with allure_step_log("清理: 删除额外的ACL"):
                try:
                    acl_page.goto_service("网络ACL")
                    acl_page.acl_batch_delete(extra_acl_names)
                except:
                    pass

    @allure.title("验证网络ACL关联/解关联子网功能")
    def test_acl_subnet_management(self, acl_page, acl, vpc):
        acl_name = acl
        subnet_name = vpc["subnet_name"]
        
        with allure_step_log(f"步骤1: 将网络ACL {acl_name} 关联至子网 {subnet_name}"):
            acl_page.acl_associate_subnet(acl_name, subnets=[subnet_name])
            
        with allure_step_log(f"步骤2: 从网络ACL {acl_name} 中解关联子网 {subnet_name}"):
            acl_page.acl_disassociate_subnet(acl_name, subnets=[subnet_name])


@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('场景验证')
class TestAclScenario:

    @allure.title("验证入方向网络ACL规则创建场景组合")
    @pytest.mark.parametrize("scenario", load_data("test_acl_rule_create_scenarios", "test_acl.yaml"))
    def test_acl_rule_create_scenarios(self, acl_page, acl, scenario):
        acl_name = acl
        desc_text = f"autotest_{scenario['desc']}_{random_data(4)}"
        
        with allure_step_log(f"步骤1: 创建入方向规则: {scenario['desc']}"):
            acl_page.acl_rule_create(
                acl_name=acl_name,
                direction=scenario.get("direction", "入方向"),
                ip_version=scenario.get("ip_version"),
                policy=scenario.get("policy"),
                protocol=scenario.get("protocol"),
                source_ip=scenario.get("source_ip"),
                source_port=scenario.get("source_port"),
                dest_ip=scenario.get("dest_ip"),
                dest_port=scenario.get("dest_port"),
                description=desc_text
            )
            
        # with allure_step_log(f"步骤2: 验证并清理刚才创建的规则以保证用例间隔离环境相对干净"):
        #     # 在单用例下我们建完之后将其删除
        #     # detail_mode=True 因为刚刚建完，页面会停留在详情页“入方向”规则列表中 (不用重新走列表进入详情)
        #     acl_page.acl_rule_delete(acl_name, direction=scenario.get("direction", "入方向"), detail_mode=True)
