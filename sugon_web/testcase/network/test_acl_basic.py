import allure
import pytest
from sugon_web.testcase.network._acl_helpers import build_acl_pair_env
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


ACL_VM_PAIR_PARAMS = {
    "inject_dependencies": False,
    "instances": [
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.subnet_name"}]}},
        {"network": {"networks": [{"network": "@vpc.name", "subnet": "@vpc.extra_subnets[0].name"}]}},
    ],
}
@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('基本功能验证')
class TestAclBasic:

    @allure.title("网络ACL-创建和删除")
    def test_acl_create_delete(self, vpc_page):
        acl_name = f"acl_{random_data()}"

        with allure_step_log(f"步骤1: 新建网络ACL"):
            vpc_page.acl_create(acl_name, desc=f"创建网络ACL{acl_name}")
            vpc_page.assert_status(acl_name, status="启用")

        with allure_step_log(f"步骤2: 单个删除网络ACL"):
            vpc_page.acl_delete(acl_name)
            vpc_page.assert_deleted(acl_name)

    @allure.title("网络ACL-搜索和重置")
    def test_acl_search(self, vpc_page, acl):
        acl_name = acl
        with allure_step_log(f"步骤1: 搜索网络ACL: {acl_name}"):
            vpc_page.acl_search(acl_name)

            # 使用模糊匹配断言列表中包含搜索关键字
            vpc_page.assert_list_contain(acl_name, exact_match=False)

        with allure_step_log(f"步骤2: 重置搜索条件"):
            vpc_page.acl_search_reset()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("网络ACL-修改名称和描述")
    def test_acl_edit(self, vpc_page, acl):
        acl_name = acl
        new_name = f"{acl_name}-edit"
        new_desc = f"巨长的描述：{acl_name}{random_data(length=260)}"

        with allure_step_log(f"步骤1: 选定网络ACL进行修改: {acl_name} -> {new_name}"):
            vpc_page.acl_edit(acl_name, new_name=new_name, new_desc=new_desc)
            vpc_page.assert_popup_success()

            # 搜索后验证修改是否成功
            vpc_page.acl_search(new_name)
            vpc_page.assert_list_contain(new_name, exact_match=False)

        with allure_step_log(f"步骤2: 恢复网络ACL名称: {new_name} -> {acl_name}"):
            vpc_page.acl_search_reset()
            vpc_page.acl_edit(new_name, new_name=acl_name)
            vpc_page.assert_popup_success()
            vpc_page.acl_search(acl_name)
            vpc_page.assert_list_contain(acl_name, exact_match=False)
            vpc_page.acl_search_reset()

    @allure.title("网络ACL-开启和关闭")
    @pytest.mark.parametrize(
        "vpc",
        [{
            "extra_subnets": [{"cidr": "10.241.2.0/24", "acl_policy": "@acl"}],
            "cidr": "10.241.1.0/24",
        }],
        indirect=True,
    )
    @pytest.mark.parametrize("vm", [ACL_VM_PAIR_PARAMS], indirect=True)
    def test_acl_enable_disable(self, acl, vpc, vm_sg_binding, vpc_page, ssh_vm):
        env = build_acl_pair_env(acl, vpc, vm_sg_binding, vpc_page)
        acl_name = env["acl_name"]

        vm_a_info = next(vm for vm in env["vms"] if vm["tag"] == "A")
        vm_b_info = next(vm for vm in env["vms"] if vm["tag"] == "B")

        vm_a_ip = vm_a_info["ip"]
        vm_b_ip = vm_b_info["ip"]
        vm_a_mfip = vm_a_info["mfip"]
        vm_b_mfip = vm_b_info["mfip"]

        try:
            with allure_step_log("步骤1: ACL下新建入方向规则"):
                vpc_page.acl_rule_create(
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
                vpc_page.acl_disable(acl_name)
                ssh_vm.connect(vm_a_mfip)
                ssh_vm.ping(vm_b_ip, connected=False, count=5)
                ssh_vm.connect(vm_b_mfip)
                ssh_vm.ping(vm_a_ip, connected=False, count=5)

            with allure_step_log("步骤4: 重新开启ACL"):
                vpc_page.acl_enable(acl_name)
                ssh_vm.connect(vm_a_mfip)
                ssh_vm.ping(vm_b_ip, connected=True, count=5)

            with allure_step_log("步骤5: 验证重新开启后: 虚机B ping 虚机A,期望可以ping通"):
                ssh_vm.connect(vm_b_mfip)
                ssh_vm.ping(vm_a_ip, connected=True, count=5)

        finally:
            with allure_step_log("清理: 删除测试创建的入方向规则"):
                try:
                    vpc_page.goto_submenu("网络ACL")
                    vpc_page.acl_rule_delete(acl_name, direction="入方向")
                except Exception as e:
                    from sugon_web.utils.logger import logger
                    logger.warning(f"删除规则失败: {e}")

    @allure.title("网络ACL-批量开启关闭和删除")
    def test_acl_batch_operations(self, vpc_page):

        with allure_step_log(f"步骤1: 新建第二个参与批量的网络ACL"):
            base_name = random_data()
            acl_names = [f"acl-batch-{base_name}-{i}" for i in range(3)]
            [vpc_page.acl_create(name) for name in acl_names]

        with allure_step_log(f"步骤2: 批量关闭网络ACL"):
            vpc_page.acl_batch_disable(acl_names)

        with allure_step_log(f"步骤3: 批量开启网络ACL"):
            vpc_page.acl_batch_enable(acl_names)

        with allure_step_log(f"步骤4: 批量删除测试临时生成的网络ACL"):
            vpc_page.acl_batch_delete(acl_names)
            vpc_page.assert_deleted(acl_names)

    @allure.title("网络ACL-关联和解关联子网")
    def test_acl_subnet_management(self, vpc_page, acl, vpc):
        acl_name = acl
        subnet_name = vpc["subnet_name"]

        with allure_step_log(f"步骤1: 将网络ACL {acl_name} 关联至子网 {subnet_name}"):
            vpc_page.acl_associate_subnet(acl_name, subnets=[subnet_name])

        with allure_step_log(f"步骤2: 从网络ACL {acl_name} 中解关联子网 {subnet_name}"):
            vpc_page.acl_disassociate_subnet(acl_name, subnets=[subnet_name])


@allure.epic('网络服务')
@allure.feature('网络安全-网络ACL')
@allure.story('场景验证')
class TestAclScenario:

    @allure.title("验证入方向网络ACL规则创建场景组合")
    @pytest.mark.parametrize("scenario", load_data("test_acl_rule_create_scenarios", "test_acl.yaml"))
    def test_acl_rule_create_scenarios(self, vpc_page, acl, scenario):
        acl_name = acl
        desc_text = f"autotest_{scenario['desc']}_{random_data(4)}"

        with allure_step_log(f"步骤1: 创建入方向规则: {scenario['desc']}"):
            vpc_page.acl_rule_create(
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
        #     vpc_page.acl_rule_delete(acl_name, direction=scenario.get("direction", "入方向"), detail_mode=True)
