import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


@allure.epic('网络服务')
@allure.feature('虚拟私有云')
@allure.story('基本功能操作验证')
class TestVPCBasic:

    @allure.title("创建和删除-{params[case_name]}")
    @pytest.mark.parametrize("params", load_data('test_vpc_create_delete', data_file='test_network.yaml'))
    def test_vpc_create_delete(self, vpc_page, params, ssh_host):
        """测试创建和删除各种类型的虚拟私有云（数据驱动，覆盖字符类型和长度边界值）"""

        vpc_name = random_data()
        cidr = random_data("cidr")

        with allure_step_log(f"步骤1: 创建 {params['case_name']} 的虚拟私有云"):
            vpc_page.vpc_create(
                name=vpc_name,
                subnet_name=params['subnet_name'],
                cidr=cidr,
                desc=params['desc'],
                subnet_desc=params['subnet_desc'],
                network_type=params['network_type'],
                gateway_mode=params['gateway_mode'],
                vlan_id=params['vlan_id']
            )

        with allure_step_log("步骤2: 验证虚拟私有云列表数据"):
            vpc_page.assert_popup_success("创建虚拟私有云成功")
            vpc_page.assert_status(vpc_name)
            data = vpc_page.get_row_data(vpc_name)
            assert params['desc'] == data['描述']
            assert params['network_type'].lower() in data['网络类型']
            assert params['subnet_name'] in data['已连接的子网']
            ssh_host.run(f'openstack network show {vpc_name}', check_rc=True)

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)
            # vpc_page.assert_popup_success("删除虚拟私有云成功")

        with allure_step_log("步骤4: 验证虚拟私有云已删除"):
            vpc_page.assert_deleted(vpc_name)
            assert ssh_host.run(f'openstack network list| grep {vpc_name}') == ''

    @allure.title("修改名称和描述")
    def test_vpc_edit(self, vpc_page, vpc):
        """测试修改VPC的名称和描述"""

        new_desc = "修改后的VPC描述"

        with allure_step_log("步骤1: 修改VPC名称和描述"):
            vpc_page.vpc_edit(
                name=vpc['name'],
                new_desc=new_desc
            )
            vpc_page.assert_popup_success("修改虚拟私有云成功")

        with allure_step_log("步骤2: 验证修改后的VPC信息"):
            # 验证新名称在列表中
            vpc_page.assert_list_contain(vpc['name'])

            # 获取VPC行数据并验证描述
            data = vpc_page.get_row_data(vpc['name'])
            assert new_desc == data['描述'], f"描述验证失败"

    @allure.title("生成授权码")
    def test_vpc_generate_auth_code(self, vpc_page, vpc):
        """测试生成VPC授权码（基于vpc fixture）"""

        with allure_step_log("步骤1: 生成授权码并复制"):
            auth_code = vpc_page.vpc_generate_auth_code(vpc['name'])
            vpc_page.assert_popup_success("复制成功")

        with allure_step_log("步骤2: 验证授权码复制成功"):
            # 从剪贴板获取复制的文本
            assert auth_code == vpc_page.page.evaluate("navigator.clipboard.readText()")

    @allure.title("新建子网")
    def test_vpc_subnet_create(self, vpc, vpc_page):
        """测试在VPC中新建子网"""

        vpc_name = vpc['name']
        subnet_name = f"{vpc_name}-subnet-1"
        cidr = random_data("cidr")
        desc = "测试子网描述"

        with allure_step_log("步骤1: 新建子网"):
            vpc_page.subnet_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                cidr=cidr,
                desc=desc,
                # available_ip="10.0.100.10-10.0.100.100",  # 可选
                # dns="8.8.8.8",  # 可选
                # acl_policy="default"  # 可选
            )
            vpc_page.assert_popup_success("创建子网成功")

        with allure_step_log("步骤2: 验证子网创建成功"):
            data = vpc_page.get_row_data(vpc_name)
            assert subnet_name, cidr in data['网络类型']
            
            
    @allure.title("列表页搜索&重置")
    def test_vpc_search(self, vpc_page, vpc):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = vpc['name'][:-2]
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.btn_reset.click()
            vpc_page.wait_for_page_ready()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

