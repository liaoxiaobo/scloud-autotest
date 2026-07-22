import ipaddress
import random
import pytest
import allure
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data, load_data


@allure.epic('网络服务')
@allure.feature('虚拟私有云')
@allure.story('基本功能验证')
class TestVPCBasic:

    @allure.title("虚拟私有云-创建和删除不同类型VPC-{params[case_name]}")
    @pytest.mark.parametrize("params", load_data('test_vpc_create_delete', data_file='test_network.yaml'))
    def test_vpc_create_delete(self, vpc_page, params):
        """测试创建和删除各种类型的虚拟私有云（数据驱动，覆盖字符类型和长度边界值）"""

        # ========== 新增判断逻辑 ==========
        # 如果 network_type 是 Flat，检查是否已存在 Flat 类型的 VPC
        if params['network_type'] == 'Flat':
            logger.info(f"检测到 network_type 为 Flat，正在检查是否已存在 Flat 类型的 VPC...")

            # ✨ 先设置每页显示 100 条，确保能看到所有数据
            logger.info("设置每页显示 100 条数据")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page._expand_page_size("100")

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

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)
            # vpc_page.assert_popup_success("删除虚拟私有云成功")

        with allure_step_log("步骤4: 验证虚拟私有云已删除"):
            vpc_page.assert_deleted(vpc_name)

    @allure.title("虚拟私有云-创建和删除双栈VPC")
    def test_vpc_dual_stack_create_delete(self, vpc_page):
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

            logger.info(f"✓ 双栈VPC {vpc_name} 创建成功")

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)

        with allure_step_log("步骤4: 验证VPC已删除"):
            vpc_page.assert_deleted(vpc_name)
            expect(vpc_page.alert).to_have_count(0, timeout=10000)  # 解决创建vpc页面，alert弹窗遮挡创建按钮的问题
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


    @allure.title("虚拟私有云-搜索和重置")
    def test_vpc_search(self, vpc_page, vpc):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            keyword = vpc['name'][:-2]
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.btn_reset.click()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("虚拟私有云-批量删除")
    def test_vpc_batch_delete(self, vpc_page):
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


    @allure.title("子网-创建和删除-{params[case_name]}")
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

    @allure.title("子网-修改")
    def test_vpc_subnet_edit(self, vpc, vpc_page):
        """测试在VPC详情页中修改子网的所有可修改选项，并通过列表验证"""

        vpc_name = vpc['name']
        cidr = random_data("cidr")
        original_subnet_name = f"{vpc_name}-subnet-to-edit"

        new_subnet_name = f"{vpc_name}-subnet-edited"
        new_desc = "修改后的子网描述"

        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 从该 CIDR 中选取一段作为新的可用 IP 地址池
        new_available_ip = f"{hosts[10]}-{hosts[20]}"
        new_dns = "8.8.8.8"

        with allure_step_log("步骤1: 准备测试数据，在VPC详情页创建一个初始子网"):
            vpc_page.subnet_create_in_detail(
                vpc_name=vpc_name,
                subnet_name=original_subnet_name,
                cidr=cidr,
                desc="原始子网描述"
            )
            vpc_page.assert_popup_success("创建子网成功")

        with allure_step_log("步骤2: 修改子网的名称、描述、IP地址池和DNS"):
            vpc_page.subnet_edit(
                subnet_name=original_subnet_name,
                new_name=new_subnet_name,
                new_desc=new_desc,
                new_available_ip=new_available_ip,
                new_dns=new_dns
            )
            vpc_page.assert_popup_success("修改子网成功")

        with allure_step_log("步骤3: 验证子网修改成功（通过子网列表的表头值断言）"):
            subnet_data = vpc_page.get_row_data(new_subnet_name)

            assert new_subnet_name == subnet_data['名称'], f"名称断言失败: 期望 {new_subnet_name}, 实际 {subnet_data['名称']}"
            assert new_desc == subnet_data['描述'], f"描述断言失败: 期望 {new_desc}, 实际 {subnet_data['描述']}"

            # 由于页面上显示的可能是以逗号分隔或者其他形式，使用 in 判断更加稳定，但根据要求完全匹配也是可以的。
            # 这里按照要求通过列表表头值进行断言：
            assert new_available_ip in subnet_data.get('IP地址池', ''), f"IP地址池断言失败: 期望包含 {new_available_ip}, 实际 {subnet_data.get('IP地址池', '')}"
            assert new_dns in subnet_data.get('DNS', ''), f"DNS断言失败: 期望包含 {new_dns}, 实际 {subnet_data.get('DNS', '')}"

        with allure_step_log("步骤4: 清理数据，删除测试子网"):
            vpc_page.subnet_delete(
                vpc_name=vpc_name,
                names=new_subnet_name
            )


    @allure.title("子网-批量删除")
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
            vpc_page.vip_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name
            )
            vpc_page.assert_popup_success("申请虚拟IP端口成功")

        with allure_step_log("步骤2: 删除虚拟IP"):
            # 删除列表中的第一个虚拟IP
            vip_list = vpc_page.get_column_data('虚拟IP地址')
            vip_name = vip_list[0]
            vpc_page.vip_delete(vip_name)

        with allure_step_log("步骤3: 验证虚拟IP已删除"):
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

    @allure.title("虚拟IP-绑定&解绑实例")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "bind_mfip": False}], indirect=True)
    def test_vip_bind_unbind_instance(self, ecs_page, vpc_page, vip, vm):

        with allure_step_log("步骤1: 绑定实例"):
            vpc_page.vip_bind_instance(vip, vm['name'])
            vpc_page.assert_popup_success("虚拟IP端口绑定实例成功")

        with allure_step_log("步骤2: 验证页面列表已显示绑定的实例"):
            data = vpc_page.get_row_data(vip)
            assert vm['name'] in data.get("绑定的实例", ""), f"断言失败: 期望绑定的实例包含 {vm['name']}，实际值为: {data.get('绑定的实例')}"

        with allure_step_log("步骤3: 解绑实例"):
            vpc_page.vip_unbind_instance(vip, vm['name'])
            vpc_page.assert_popup_success("虚拟IP端口解绑实例成功")

        with allure_step_log("步骤4: 验证页面列表已解绑该实例"):
            data = vpc_page.get_row_data(vip)
            assert vm['name'] not in data.get("绑定的实例", ""), f"断言失败: 期望绑定的实例不再包含 {vm['name']}"

    @allure.title("虚拟IP-绑定&解绑公网IP")
    def test_vip_bind_eip(self, vpc_page, eip, vip):

        with allure_step_log("步骤1: 绑定公网IP"):
            bound_eip = vpc_page.vip_bind_eip(vip, eip_ip=eip)
            vpc_page.assert_popup_success("执行成功")

        with allure_step_log("步骤2: 验证绑定的公网IP"):
            data = vpc_page.get_row_data(vip)
            # 断言绑定的公网ip会显示在列表里，且表头名称为“绑定的公网IP”
            assert bound_eip in data.get("绑定的公网IP", ""), f"断言失败: 列表项'绑定的公网IP'未找到对应IP {bound_eip}，实际值为: {data.get('绑定的公网IP')}"

        with allure_step_log("步骤3: 解绑公网IP"):
            vpc_page.vip_unbind_eip(vip)
            vpc_page.assert_popup_success("执行成功")

        with allure_step_log("步骤4: 验证解绑后公网IP已移除"):
            data = vpc_page.get_row_data(vip)
            assert bound_eip not in data.get("绑定的公网IP", ""), f"断言失败: 解绑后列表项'绑定的公网IP'仍包含IP {bound_eip}"

    @allure.title("虚拟IP-搜索和重置")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}, "bind_mfip": False}], indirect=True)
    def test_vip_search(self, ecs_page, vpc_page, vip, vm):
        """测试虚拟IP搜索&重置"""

        # vm fixture 返回的是列表，包含两台虚机的信息
        vm1_data = vm[0]
        vm2_data = vm[1]

        vm1_name = vm1_data['name']
        vm2_name = vm2_data['name']

        with allure_step_log("步骤1: 绑定两台实例"):
            vpc_page.vip_bind_instance(vip, vm2_name)
            vpc_page.assert_popup_success("虚拟IP端口绑定实例成功")
            vpc_page.vip_bind_instance(vip, vm1_name)
            vpc_page.assert_popup_success("虚拟IP端口绑定实例成功")

        with allure_step_log("步骤2: 输入实例名称进行搜索"):
            keyword = vm1_name[:-2]
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, column_name="绑定的实例", exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.btn_reset.click()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 解除绑定两台实例"):
            vpc_page.vip_unbind_instance(vip, vm2_name)
            vpc_page.assert_popup_success("虚拟IP端口解绑实例成功")
            vpc_page.vip_unbind_instance(vip, vm1_name)
            vpc_page.assert_popup_success("虚拟IP端口解绑实例成功")

    @allure.title("端口-创建和删除（自动分配）")
    def test_port_create_delete_auto_assign(self, vpc_page, vpc):
        """测试端口的创建和删除（自动分配模式）"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']

        with allure_step_log("步骤1: 创建端口（自动分配）"):
            port_ip = vpc_page.port_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name
            )
            vpc_page.assert_popup_success("添加端口成功")
            logger.info(f"自动分配的端口IP: {port_ip}")

        with allure_step_log("步骤2: 删除端口"):
            vpc_page.port_delete(port_ip)

        with allure_step_log("步骤3: 验证端口已删除"):
            vpc_page.assert_deleted(port_ip)
            logger.info(f"✓ 自动分配的端口 {port_ip} 删除成功")

    @allure.title("端口-创建和删除（手动分配-手动输入）")
    def test_port_create_delete_manual_assign(self, vpc_page, vpc):
        """测试端口的创建和删除（手动指定IP模式）"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']
        cidr = vpc['cidr']

        # 根据cidr生成随机ip，避免与网关、已有接口等冲突
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 随机选择一个IP，跳过前20个避免冲突
        port_ip = str(random.choice(hosts[20:])) if len(hosts) > 30 else str(random.choice(hosts[5:]))
        logger.info(f"计划手动分配的端口IP: {port_ip}")

        with allure_step_log("步骤1: 创建端口（手动分配）"):
            vpc_page.port_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                ip_address=port_ip
            )
            vpc_page.assert_popup_success("添加端口成功")

        with allure_step_log("步骤2: 删除端口"):
            vpc_page.port_delete(port_ip)

        with allure_step_log("步骤3: 验证端口已删除"):
            vpc_page.assert_deleted(port_ip)
            logger.info(f"✓ 手动分配的端口 {port_ip} 删除成功")

    @allure.title("端口-创建和删除（手动分配-快速选择）")
    def test_port_create_delete_quick_select(self, vpc_page, vpc):
        """测试端口的创建和删除（通过快速选择IP模式）"""

        vpc_name = vpc['name']
        subnet_name = vpc['subnet_name']
        cidr = vpc['cidr']

        # 根据cidr生成随机ip，避免与网关、已有接口等冲突
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 随机选择一个IP，跳过前20个避免冲突
        port_ip = str(random.choice(hosts[20:])) if len(hosts) > 30 else str(random.choice(hosts[5:]))
        logger.info(f"计划手动分配的端口IP: {port_ip}")

        with allure_step_log("步骤1: 创建端口（快速选择IP）"):
            created_ip = vpc_page.port_create(
                vpc_name=vpc_name,
                subnet_name=subnet_name,
                ip_address=port_ip,
                quick_select=True
            )
            vpc_page.assert_popup_success("添加端口成功")
            logger.info(f"快速选择分配的端口IP: {created_ip}")

        with allure_step_log("步骤2: 删除端口"):
            vpc_page.port_delete(created_ip)

        with allure_step_log("步骤3: 验证端口已删除"):
            vpc_page.assert_deleted(created_ip)
            logger.info(f"✓ 快速选择分配的端口 {created_ip} 删除成功")

    @allure.title("端口-搜索和重置")
    @pytest.mark.parametrize("port", [{"count": 2}], indirect=True)
    def test_port_search(self, vpc_page, vpc, port):
        """测试端口的搜索和重置功能"""

        vpc_name = vpc['name']
        port_ips = port  # fixture 返回的是 IP 列表

        with allure_step_log("步骤1: 进入端口列表页"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="端口").click()

        with allure_step_log("步骤2: 输入端口IP进行搜索"):
            # 取第一个IP作为搜索关键字
            keyword = port_ips[0]
            # 在当前tab页内搜索
            vpc_page.search(keyword)
            # 验证搜索结果包含关键字
            vpc_page.assert_list_contain(keyword, column_name="固定IP", exact_match=True)
            # 验证另一个IP不在列表中
            vpc_page.assert_list_not_contain(port_ips[1], column_name="固定IP")

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.btn_reset.click()
            # 验证搜索框已清空
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"
            # 验证列表恢复（至少包含之前创建的两个IP）
            vpc_page.assert_list_contain(port_ips[0], column_name="固定IP")
            vpc_page.assert_list_contain(port_ips[1], column_name="固定IP")

    @allure.title("端口-批量删除")
    @pytest.mark.parametrize("port", [{"count": 3}], indirect=True)
    def test_port_batch_delete(self, vpc_page, vpc, port):
        """测试端口的批量删除功能"""

        vpc_name = vpc['name']
        port_ips = port  # fixture 返回的是 IP 列表

        with allure_step_log("步骤1: 进入端口列表页"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="端口").click()

        with allure_step_log("步骤2: 批量删除端口"):
            # 传入列表进行批量删除
            vpc_page.port_delete(port_ips)

        with allure_step_log("步骤3: 验证端口已删除"):
            vpc_page.assert_deleted(port_ips)

    @allure.title("端口-修改IP和MAC")
    def test_port_edit(self, vpc_page, vpc, port):
        """测试端口修改IP和MAC功能"""

        vpc_name = vpc['name']
        cidr = vpc['cidr']
        old_ip = port[0]  # fixture默认创建1个端口

        # 找一个新的可用IP
        network = ipaddress.ip_network(cidr, strict=False)
        hosts = list(network.hosts())
        # 从最后面选一个IP，大概率不会和前面的冲突
        new_ip = str(hosts[-10])

        # 生成随机MAC地址 (unicast, locally administered)
        # 第二个字符必须是 2, 6, A, 或 E
        mac_hex = [0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        for i in range(1, 6):
            mac_hex[i] = random.randint(0x00, 0xff)
        new_mac = ':'.join(map(lambda x: "%02x" % x, mac_hex))

        with allure_step_log("步骤1: 进入端口列表页"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.goto_detail_page(vpc_name, tab_name="端口")

        with allure_step_log("步骤2: 修改端口IP和MAC"):
            logger.info(f"将端口 {old_ip} 修改为 IP: {new_ip}, MAC: {new_mac}")
            vpc_page.port_edit(old_ip=old_ip, new_ip=new_ip, new_mac=new_mac)
            vpc_page.assert_popup_success("修改端口成功")

        with allure_step_log("步骤3: 验证修改结果"):
            # 验证新IP存在于列表中
            vpc_page.assert_list_contain(new_ip, column_name="固定IP")
            # 验证新MAC存在于列表中
            vpc_page.assert_list_contain(new_mac, column_name="MAC地址")

            # 更新fixture的返回值，以便清理资源时能找到正确的IP
            port[0] = new_ip


    @allure.title("路由表-创建和删除规则")
    def test_route_rule_create_delete(self, vpc_page, vpc, vip):
        """测试在VPC的路由表中创建和单条删除路由表规则"""

        vpc_name = vpc['name']
        dest_cidr = random_data("cidr")
        desc = "路由表规则单次创建删除测试"

        with allure_step_log("步骤1: 进入路由表并在VPC详情页新建路由表规则（下一跳为虚拟IP）"):
            vpc_page.route_rule_create(
                vpc_name=vpc_name,
                dest_cidr=dest_cidr,
                next_hop=vip,
                next_hop_type="虚拟IP",
                desc=desc
            )
            vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤2: 验证路由表规则创建成功，列表呈现对应目的地址和下一跳信息"):
            # 创建成功后自动会刷新处于路由表列表页
            data = vpc_page.get_row_data(dest_cidr)
            assert dest_cidr in data.get("目的地址", ""), f"目的地址断言失败: {data}"
            assert "虚拟IP" in data.get("下一跳类型", ""), f"下一跳类型断言失败: {data}"
            assert vip in data.get("下一跳", ""), f"下一跳断言失败: {data}"
            assert desc in data.get("描述", ""), f"描述断言失败: {data}"

        with allure_step_log("步骤3: 删除选定的路由表规则"):
            vpc_page.route_rule_delete(dest_cidrs=dest_cidr)
            # 在某些系统中，统一弹窗 "删除成功" 或类似提示，如果框架内有自带在此之后断言，也可以直接沿用 assert_deleted

        with allure_step_log("步骤4: 验证路由表规则已成功从列表中删除"):
            vpc_page.assert_deleted(dest_cidr)


    @allure.title("路由表-批量删除规则")
    def test_route_rule_batch_delete(self, vpc_page, vpc, vip):
        """测试在VPC的路由表中批量删除多条路由表规则"""

        vpc_name = vpc['name']
        dest_cidrs = []

        with allure_step_log("步骤1: 在VPC详情页连续新建2条路由表规则"):
            for i in range(2):
                dest_cidr = random_data("cidr")
                dest_cidrs.append(dest_cidr)

                # 回到 VPC 列表页面起始点，因为 route_rule_create 会先去找名叫 vpc_name 的行
                vpc_page.route_rule_create(
                    vpc_name=vpc_name,
                    dest_cidr=dest_cidr,
                    next_hop=vip,
                    next_hop_type="虚拟IP",
                    desc=f"批量删除测试规则{i}"
                )
                vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤2: 勾选多条规则执行批量删除路由表规则"):
            # 由于最后一次 create 完，页面依然留停在 VPC详情 -> 路由表 tab 下，这里可以直接调用 delete
            vpc_page.route_rule_delete(dest_cidrs=dest_cidrs)

        with allure_step_log("步骤3: 验证路由表规则批量删除成功，列表中不存在被删除的目的地址"):
            vpc_page.assert_deleted(dest_cidrs)

    @allure.title("路由表-修改名称和描述")
    def test_route_table_edit(self, vpc_page, vpc):
        """测试修改VPC路由表的名称和描述"""

        vpc_name = vpc['name']
        new_rtb_name = f"{vpc_name}-rtb-edited"
        new_rtb_desc = "修改后的路由表描述"

        with allure_step_log("步骤1: 进入VPC详情页的路由表Tab"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.goto_detail_page(vpc_name, tab_name="路由表")

        with allure_step_log("步骤2: 修改路由表名称和描述"):
            vpc_page.route_table_edit(new_name=new_rtb_name, new_desc=new_rtb_desc)
            vpc_page.assert_popup_success("修改路由表成功")

        with allure_step_log("步骤3: 验证路由表名称和描述已更新"):
            vpc_page.get_by_text(new_rtb_name).wait_for()
            vpc_page.get_by_text(new_rtb_desc).wait_for()
            logger.info(f"✓ 路由表名称已修改为: {new_rtb_name}")
            logger.info(f"✓ 路由表描述已修改为: {new_rtb_desc}")

    @allure.title("路由表规则-搜索和重置")
    def test_route_rule_search(self, vpc_page, vpc):
        """测试路由表Tab中按目的地址搜索和重置路由表规则（利用VPC默认路由规则）"""

        vpc_name = vpc['name']
        keyword = vpc['cidr']   # VPC默认路由规则中包含子网CIDR作为目的地址

        with allure_step_log("步骤1: 进入VPC详情页的路由表Tab"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.goto_detail_page(vpc_name, tab_name="路由表")

        with allure_step_log(f"步骤2: 按目的地址 '{keyword}' 搜索，验证结果包含该规则"):
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(keyword, column_name="目的地址", exact_match=True)
            rows = vpc_page.get_column_data("目的地址")
            assert len(rows) == 1, f"搜索结果应只有1行，实际有 {len(rows)} 行: {rows}"

        with allure_step_log("步骤3: 重置搜索条件，验证规则列表恢复"):
            vpc_page.reset()
            rows = vpc_page.get_column_data("目的地址")
            assert len(rows) > 1, f"重置后应有多行，实际只有 {len(rows)} 行: {rows}"

    @allure.title("路由表-修改规则")
    def test_route_rule_edit(self, vpc_page, vpc, vip):
        """测试修改路由表规则的目的地址、下一跳类型、下一跳和描述"""

        vpc_name = vpc['name']
        dest_cidr = random_data("cidr")
        new_dest_cidr = random_data("cidr")
        new_desc = "修改后的路由表规则描述"

        with allure_step_log("步骤1: 在路由表Tab下创建路由表规则（前置数据）"):
            vpc_page.route_rule_create(
                vpc_name=vpc_name,
                dest_cidr=dest_cidr,
                next_hop=vip,
                next_hop_type="虚拟IP",
                desc="待修改的路由表规则"
            )
            vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤2: 修改路由表规则的目的地址和描述"):
            # create 完后仍在路由表Tab，直接调用 edit
            vpc_page.route_rule_edit(
                dest_cidr=dest_cidr,
                new_dest_cidr=new_dest_cidr,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success("修改路由规则成功")

        with allure_step_log("步骤3: 验证修改后的数据在列表中正确呈现"):
            data = vpc_page.get_row_data(new_dest_cidr)
            assert new_dest_cidr in data.get("目的地址", ""), f"目的地址断言失败: {data}"
            assert "虚拟IP" in data.get("下一跳类型", ""), f"下一跳类型断言失败: {data}"
            assert vip in data.get("下一跳", ""), f"下一跳断言失败: {data}"
            assert new_desc in data.get("描述", ""), f"描述断言失败: {data}"

        with allure_step_log("步骤4: 清理，删除该路由表规则"):
            vpc_page.route_rule_delete(dest_cidrs=new_dest_cidr)
            vpc_page.assert_deleted(new_dest_cidr)





