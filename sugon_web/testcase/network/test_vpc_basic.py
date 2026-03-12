import ipaddress
import random
import pytest
import allure
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data, load_data


@allure.epic('网络服务')
@allure.feature('虚拟私有云')
@allure.story('基本功能操作验证')
class TestVPCBasic:

    @allure.title("虚拟私有云-创建和删除不同类型VPC-{params[case_name]}")
    @pytest.mark.parametrize("params", load_data('test_vpc_create_delete', data_file='test_network.yaml'))
    def test_vpc_create_delete(self, vpc_page, params, ssh_host):
        """测试创建和删除各种类型的虚拟私有云（数据驱动，覆盖字符类型和长度边界值）"""

        # ========== 新增判断逻辑 ==========
        # 如果 network_type 是 Flat，检查是否已存在 Flat 类型的 VPC
        if params['network_type'] == 'Flat':
            logger.info(f"检测到 network_type 为 Flat，正在检查是否已存在 Flat 类型的 VPC...")

            # ✨ 先设置每页显示 100 条，确保能看到所有数据
            logger.info("设置每页显示 100 条数据")
            vpc_page.locator("#cloud-container-content").get_by_placeholder("请选择").click()
            vpc_page.get_by_text("100条/页").click()
            vpc_page.wait_for_page_ready()  # 等待页面刷新完成

            # 获取"网络类型"列的所有数据
            network_types = vpc_page.get_column_data('网络类型')
            logger.info(f"当前网络类型列表: {network_types}")

            # 判断是否包含 flat 字符串（不区分大小写）
            if any('flat' in nt.lower() for nt in network_types):
                logger.warning(f"已存在 Flat 类型的 VPC，跳过测试用例")
                pytest.skip(f"已存在 Flat 类型的 VPC，跳过测试用例")
            else:
                logger.info(f"未发现 Flat 类型的 VPC，继续执行测试用例")
        # ================================

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
            # ssh_host.run(f'openstack network show {vpc_name}', check_rc=True)

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)
            # vpc_page.assert_popup_success("删除虚拟私有云成功")

        with allure_step_log("步骤4: 验证虚拟私有云已删除"):
            vpc_page.assert_deleted(vpc_name)
            # assert ssh_host.run(f'openstack network list| grep {vpc_name}') == ''

    @allure.title("虚拟私有云-创建和删除双栈VPC")
    def test_vpc_dual_stack_create_delete(self, vpc_page, ssh_host):
        """测试创建和删除双栈VPC（Geneve类型 + IPv6）"""

        vpc_name = random_data()
        cidr = random_data("cidr")

        with allure_step_log("步骤1: 创建双栈虚拟私有云（Geneve + IPv6）"):
            vpc_page.vpc_create(
                name=vpc_name,
                subnet_name=f"{vpc_name}-subnet",
                cidr=cidr,
                desc="双栈VPC测试",
                subnet_desc="双栈VPC子网",
                network_type="Geneve",
                enable_ipv6=True  # 开启IPv6
            )
            vpc_page.assert_popup_success("创建虚拟私有云成功")
            vpc_page.assert_status(vpc_name)

        with allure_step_log("步骤2: 验证VPC创建成功"):
            # 获取VPC行数据
            data = vpc_page.get_row_data(vpc_name)

            # 断言VPC名称
            assert vpc_name in data['名称'], f"VPC名称断言失败: 期望 {vpc_name}, 实际 {data['名称']}"

            # 断言网络类型
            assert "geneve" in data['网络类型'], f"网络类型断言失败: 期望包含 'Geneve', 实际 {data['网络类型']}"

            # 断言描述
            assert "双栈VPC测试" == data['描述'], f"描述断言失败: 期望 '双栈VPC测试', 实际 {data['描述']}"

            # SSH验证VPC已创建
            # ssh_host.run(f'openstack network show {vpc_name}', check_rc=True)
            logger.info(f"✓ 双栈VPC {vpc_name} 创建成功")

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)

        with allure_step_log("步骤4: 验证VPC已删除"):
            vpc_page.assert_deleted(vpc_name)
            expect(vpc_page.alert).to_have_count(0, timeout=10000)  # 解决创建vpc页面，alert弹窗遮挡创建按钮的问题
            # assert ssh_host.run(f'openstack network list| grep {vpc_name}') == ''
            logger.info(f"✓ 双栈VPC {vpc_name} 删除成功")

    @allure.title("虚拟私有云-修改名称和描述")
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

    @allure.title("虚拟私有云-生成授权码")
    def test_vpc_generate_auth_code(self, vpc_page, vpc):
        """测试生成VPC授权码（基于vpc fixture）"""

        with allure_step_log("步骤1: 生成授权码并复制"):
            auth_code = vpc_page.vpc_generate_auth_code(vpc['name'])
            vpc_page.assert_popup_success("复制成功")

        with allure_step_log("步骤2: 验证授权码复制成功"):
            # 从剪贴板获取复制的文本
            assert auth_code == vpc_page.page.evaluate("navigator.clipboard.readText()")

    @allure.title("虚拟私有云-新建子网")
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


    @allure.title("虚拟私有云-搜索&重置")
    def test_vpc_search(self, vpc_page, vpc):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = vpc['name'][:-2]
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.btn_reset.click()
            vpc_page.wait_for_page_ready()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("虚拟私有云-批量删除")
    def test_vpc_batch_delete(self, vpc_page, ssh_host):
        """测试批量删除多个VPC"""

        vpc_names = []

        with allure_step_log("步骤1: 创建3个VPC"):
            for i in range(3):
                vpc_name = random_data()
                vpc_names.append(vpc_name)

                vpc_page.vpc_create(
                    name=vpc_name,
                    subnet_name=f"{vpc_name}-subnet",
                    cidr=random_data("cidr"),
                    desc=f"批量删除测试VPC{i}"
                )
                vpc_page.assert_popup_success("创建虚拟私有云成功")
                vpc_page.assert_status(vpc_name)

        with allure_step_log("步骤2: 批量删除VPC"):
            vpc_page.vpc_delete(vpc_names)
            # vpc_page.assert_popup_success("删除虚拟私有云成功")  # 可选

        with allure_step_log("步骤3: 验证VPC已删除"):
            vpc_page.assert_deleted(vpc_names)


    @allure.title("虚拟私有云-子网创建和删除（详情页）-{params[case_name]}")
    @pytest.mark.parametrize("params", load_data('test_vpc_subnet_create_delete', data_file='test_network.yaml'))
    def test_vpc_subnet_create_delete(self, vpc, vpc_page, params):
        """测试在VPC详情页中创建和删除子网（数据驱动）"""

        vpc_name = vpc['name']
        subnet_name = params['subnet_name']
        cidr = params['cidr']
        desc = params['desc']
        gateway_ip = params['gateway_ip']
        available_ip = params['available_ip']
        dns = params['dns']

        # 计算默认网关IP（如果未指定）
        if not gateway_ip:
            default_gateway = str(next(ipaddress.ip_network(cidr, strict=False).hosts()))
        else:
            default_gateway = gateway_ip

        vpc_page.goto_service("虚拟私有云")  # 跳转到虚拟私有云页面

        with allure_step_log("步骤1: 在VPC详情页创建子网"):
            vpc_page.subnet_create_in_detail(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                cidr=cidr,
                desc=desc,
                gateway_ip=gateway_ip,
                available_ip=available_ip,
                dns=dns,
                # acl_policy="default"  # 可选
            )
            vpc_page.assert_popup_success("创建子网成功")

        with allure_step_log("步骤2: 验证子网创建成功（在子网tab页）"):
            # 获取子网行数据
            subnet_data = vpc_page.get_row_data(subnet_name)

            # 断言子网名称（使用相等判断）
            assert subnet_name == subnet_data['名称'], f"子网名称断言失败: 期望 {subnet_name}, 实际 {subnet_data['名称']}"

            # 断言CIDR（使用相等判断）
            assert cidr == subnet_data['CIDR'], f"CIDR断言失败: 期望 {cidr}, 实际 {subnet_data['CIDR']}"

            # 断言网关IP（使用相等判断）
            assert default_gateway == subnet_data[
                '网关IP'], f"网关IP断言失败: 期望 {default_gateway}, 实际 {subnet_data['网关IP']}"

            # 断言描述（使用相等判断）
            assert desc == subnet_data['描述'], f"描述断言失败: 期望 {desc}, 实际 {subnet_data['描述']}"

            # 断言可用IP（如果指定了，使用相等判断）
            if available_ip:
                assert available_ip == subnet_data[
                    'IP地址池'], f"可用IP断言失败: 期望 {available_ip}, 实际 {subnet_data['IP地址池']}"

            # 断言DNS（如果指定了）
            if dns:
                assert dns in subnet_data['DNS'], f"DNS断言失败: 期望包含 {dns}"

        with allure_step_log("步骤3: 在VPC详情页删除子网"):
            vpc_page.subnet_delete(
                vpc_name=vpc_name,
                names=subnet_name
            )
            # vpc_page.assert_popup_success("删除子网成功")

        with allure_step_log("步骤4: 验证子网删除成功（在子网tab页）"):
            # 此时还在子网tab页，直接断言子网已不在列表中
            vpc_page.assert_deleted(subnet_name)

    @allure.title("虚拟私有云-子网批量删除")
    def test_vpc_subnet_batch_delete(self, vpc, vpc_page):
        """测试批量删除多个子网"""

        vpc_name = vpc['name']
        subnet_names = []

        # 步骤1: 在VPC详情页创建2个子网
        with allure_step_log("步骤1: 在VPC详情页创建2个子网"):
            for i in range(1):
                subnet_name = f"{vpc_name}-subnet-{i}"
                subnet_names.append(subnet_name)
                cidr = random_data("cidr")
                desc = f"批量删除测试子网{i}"

                # 每次循环都返回VPC列表页
                vpc_page.goto_service("虚拟私有云")

                vpc_page.subnet_create_in_detail(
                    vpc_name=vpc_name,
                    subnet_name=subnet_name,
                    cidr=cidr,
                    desc=desc
                )
                vpc_page.assert_popup_success("创建子网成功")

        # 步骤2: 批量删除子网
        with allure_step_log("步骤2: 批量删除子网"):
            vpc_page.subnet_delete(vpc_name, subnet_names)

        # 步骤3: 验证子网已删除
        with allure_step_log("步骤3: 验证子网已删除"):
            vpc_page.assert_deleted(subnet_names)

    @allure.title("虚拟IP-创建和删除（自动分配）")
    def test_vip_create_delete_auto_assign(self, vpc_page, vpc):
        """测试虚拟IP的创建和删除（自动分配模式）"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']

        with allure_step_log("步骤1: 创建虚拟IP（自动分配）"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.vip_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name
            )
            vpc_page.assert_popup_success("申请虚拟IP端口成功")

        with allure_step_log("步骤3: 删除虚拟IP"):
            # 删除列表中的第一个虚拟IP
            vip_list = vpc_page.get_column_data('虚拟IP地址')
            print(vip_list)
            vip_name = vip_list[0]
            vpc_page.vip_delete(vip_name)

        with allure_step_log("步骤4: 验证虚拟IP已删除"):
            vpc_page.assert_deleted(vip_name)
            logger.info(f"✓ 虚拟IP {vip_name} 删除成功")

    @allure.title("虚拟IP-创建和删除（手动分配）")
    def test_vip_create_delete_manual_assign(self, vpc_page, vpc):
        """测试虚拟IP的创建和删除（手动分配模式）"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']
        cidr = vpc['cidr']
        # 根据cidr生成随机ip，避免与网关冲突
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 随机选择一个IP，跳过前10个IP以避免网关冲突
        vip_address = str(random.choice(hosts[10:])) if len(hosts) > 20 else str(random.choice(hosts[2:]))
        logger.info(f"虚拟IP地址: {vip_address}")

        with allure_step_log("步骤1: 创建虚拟IP（手动分配）"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.vip_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                ip_address=vip_address
            )
            vpc_page.assert_popup_success("申请虚拟IP端口成功")

        with allure_step_log("步骤2: 验证虚拟IP创建成功"):
            # 获取虚拟IP列表数据
            vip_list = vpc_page.get_column_data('虚拟IP地址')
            assert vip_address in vip_list, f"虚拟IP {vip_address} 未在列表中，创建失败"
            logger.info(f"✓ 虚拟IP手动分配成功: {vip_address}")

        with allure_step_log("步骤3: 删除虚拟IP"):
            vpc_page.vip_delete(vip_address)

        with allure_step_log("步骤4: 验证虚拟IP已删除"):
            vpc_page.assert_deleted(vip_address)
            logger.info(f"✓ 虚拟IP {vip_address} 删除成功")

    @allure.title("虚拟IP-批量删除")
    def test_vip_batch_delete(self, vpc_page, vpc):
        """测试批量删除多个虚拟IP"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']

        with allure_step_log("步骤1: 创建2个虚拟IP"):
            for i in range(2):
                # 每次循环都返回VPC列表页，确保 vip_create 的起始状态正确
                vpc_page.goto_service("虚拟私有云")
                vpc_page.vip_create(
                    vpc_name=vpc_name,
                    subnet_name=subnet_name
                )
                vpc_page.assert_popup_success("申请虚拟IP端口成功")

        with allure_step_log("步骤2: 批量删除虚拟IP"):
            vip_list = vpc_page.get_column_data('虚拟IP地址')
            target_vips = vip_list[:2]
            logger.info(f"待删除的虚拟IP: {target_vips}")
            vpc_page.vip_delete(target_vips)

        with allure_step_log("步骤3: 验证虚拟IP已删除"):
            vpc_page.assert_deleted(target_vips)
            logger.info(f"✓ 批量删除虚拟IP验证通过: {target_vips}")

    @allure.title("虚拟IP-绑定&解绑公网IP")
    def test_vip_bind_eip(self, vpc_page, vip):

        vpc_page.vip_bind_eip(vip)
        vpc_page.assert_popup_success("执行成功")

        # 执行解绑
        vpc_page.vip_unbind_eip(vip)
        vpc_page.assert_popup_success("执行成功")

    @allure.title("虚拟IP-绑定&解绑实例")
    def test_vip_bind_unbind_instance(self, ecs_page, vpc_page, vip, vm):
        """测试虚拟IP绑定和解绑虚拟机实例"""

        with allure_step_log("步骤1: 绑定实例"):
            vpc_page.vip_bind_instance(vip, vm['name'])
            vpc_page.assert_popup_success("虚拟IP端口绑定实例成功")

        with allure_step_log("步骤2: 解绑实例"):
            vpc_page.vip_unbind_instance(vip, vm['name'])
            vpc_page.assert_popup_success("虚拟IP端口解绑实例成功")
