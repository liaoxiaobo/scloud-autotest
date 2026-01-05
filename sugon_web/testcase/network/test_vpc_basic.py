import ipaddress
import random
import pytest
import allure
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
            ssh_host.run(f'openstack network show {vpc_name}', check_rc=True)
            logger.info(f"✓ 双栈VPC {vpc_name} 创建成功")

        with allure_step_log("步骤3: 删除虚拟私有云"):
            vpc_page.vpc_delete(vpc_name)

        with allure_step_log("步骤4: 验证VPC已删除"):
            vpc_page.assert_deleted(vpc_name)
            assert ssh_host.run(f'openstack network list| grep {vpc_name}') == ''
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
            for vpc_name in vpc_names:
                vpc_page.assert_deleted(vpc_name)
                assert ssh_host.run(f'openstack network list| grep {vpc_name}') == ''


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
            for i in range(2):
                subnet_name = f"{vpc_name}-subnet-{i}"
                subnet_names.append(subnet_name)
                cidr = random_data("cidr")
                desc = f"批量删除测试子网{i}"

                # 每次创建子网前先进入VPC详情页
                vpc_page.goto_service("虚拟私有云")
                # vpc_page.get_by_role("row", name=vpc_name).locator("a").click()

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
            for subnet_name in subnet_names:
                vpc_page.assert_deleted(subnet_name)


@allure.epic('网络服务')
@allure.feature('虚拟私有云')
@allure.story('VPC网络互通性验证')
class TestVPCNetwork:

    @allure.title("Geneve网络-同子网的两台虚机互通验证")
    @pytest.mark.parametrize("vm", [{"count": 2}], indirect=True)
    def test_vpc_two_vms_ping(self, vm, ssh_vm):
        """
        测试Geneve网络内两台虚拟机通过内网IP互相ping通

        测试步骤：
        1. 预置两台虚拟机（vm fixture，使用默认Geneve网络）
        2. 分别ping对方虚机的内网IP，验证能ping通
        """

        # vm fixture 返回的是列表，包含两台虚机的信息
        vm1_data = vm[0]
        vm2_data = vm[1]

        vm1_name = vm1_data['name']
        vm2_name = vm2_data['name']
        vm1_ip = vm1_data['ip']
        vm2_ip = vm2_data['ip']
        vm1_mfip = vm1_data['mfip']
        vm2_mfip = vm2_data['mfip']

        logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, Mfip: {vm1_mfip}")
        logger.info(f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, Mfip: {vm2_mfip}")

        with allure_step_log("步骤1: 第一台虚机ping第二台虚机"):
            # 通过第一台虚机的mfip连接，并ping第二台虚机的内网IP
            ssh_vm.connect(vm1_mfip)

            ssh_vm.ping(vm2_ip)
            logger.info(f"✓ {vm1_name} ping {vm2_ip} 成功")

        with allure_step_log("步骤2: 第二台虚机ping第一台虚机"):
            # 通过第二台虚机的mfip连接，并ping第一台虚机的内网IP
            ssh_vm.connect(vm2_mfip)

            ssh_vm.ping(vm1_ip)
            logger.info(f"✓ {vm2_name} ping {vm1_ip} 成功")

    @allure.title("Geneve网络-跨子网两台虚机互通验证")
    def test_vpc_cross_subnet_ping(self, vm, ecs_page, ssh_vm):
        """
        测试Geneve网络内跨子网的两台虚拟机通过内网IP互相ping通

        测试步骤：
        1. 预置一台虚拟机（vm fixture，使用默认子网）
        2. 在预置的subnet子网中创建第二台虚机
        3. 分别ping对方虚机的内网IP，验证能ping通
        """

        # vm fixture 返回的是字典，包含第一台虚机的信息
        vm1_data = vm

        vm1_name = vm1_data['name']
        vm1_ip = vm1_data['ip']
        vm1_mfip = vm1_data['mfip']
        vm1_network = vm1_data['network']
        vm1_subnet = vm1_data['subnet']

        logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, Mfip: {vm1_mfip}, 网络: {vm1_network}, 子网: {vm1_subnet}")

        # 步骤1: 在预置的subnet子网中创建第二台虚机
        with allure_step_log("步骤1: 在预置的subnet子网中创建第二台虚机"):
            vm2_name = f"{vm1_name}-vm2"
            # 使用环境中预置的子网名称
            existing_subnet_name = "subnet"

            ecs_page.ecs_create(
                name=vm2_name,
                count=1,
                network=vm1_network,  # 使用第一台虚机的网络
                subnet=existing_subnet_name,  # 使用环境中预置的subnet子网
                cluster=vm1_network  # 使用第一台虚机的集群
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status([vm2_name])

            # 获取第二台虚机的信息
            vm2_data = ecs_page.get_row_data(vm2_name)
            vm2_ip = vm2_data['IP地址'].split(':')[1].strip()
            vm2_project = vm2_data['项目名称']

            # 绑定Mfip
            ecs_page.goto_service("网络设施")
            ecs_page.mfip_create(vm2_project, vm1_network, vm2_ip)
            ecs_page.assert_popup_success()
            ecs_page.mfip_search(vm2_ip)
            vm2_mfip = ecs_page.get_column_data("Mfip 地址")[0]
            ecs_page.goto_service("弹性云服务器")

            logger.info(
                f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, Mfip: {vm2_mfip}, 网络: {vm1_network}, 子网: {existing_subnet_name}")

        # 步骤2: 第一台虚机ping第二台虚机（跨子网）
        with allure_step_log("步骤2: 第一台虚机ping第二台虚机（跨子网）"):
            # 通过第一台虚机的mfip连接，并ping第二台虚机的内网IP
            ssh_vm.connect(vm1_mfip)

            # ping方法不返回值，成功时直接return，失败时抛出异常
            ssh_vm.ping(vm2_ip)
            logger.info(f"✓ {vm1_name} ({vm1_subnet}) ping {vm2_ip} ({existing_subnet_name}) 成功")

        # 步骤3: 第二台虚机ping第一台虚机（跨子网）
        with allure_step_log("步骤3: 第二台虚机ping第一台虚机（跨子网）"):
            # 通过第二台虚机的mfip连接，并ping第一台虚机的内网IP
            ssh_vm.connect(vm2_mfip)

            # ping方法不返回值，成功时直接return，失败时抛出异常
            ssh_vm.ping(vm1_ip)
            logger.info(f"✓ {vm2_name} ({existing_subnet_name}) ping {vm1_ip} ({vm1_subnet}) 成功")

        with allure_step_log("步骤4: 清理测试数据"):
            # 第二台虚机需要手动清理
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(vm2_name)
            ecs_page.ecs_delete(vm2_name)
            ecs_page.assert_deleted(vm2_name)
            logger.info(f"已手动清理虚机: {vm2_name}")

    @allure.title("Vlan网络-同子网的两台虚机互通验证")
    @pytest.mark.parametrize("vpc", [{
        "network_type": "Vlan",
        "gateway_mode": "分布式网关",
        "vlan_id": random.randint(610, 699)
    }], indirect=True)
    def test_vlan_two_vms_ping(self, vpc, ecs_page, ssh_vm):
        """
        测试Vlan网络内两台虚拟机通过内网IP互相ping通

        测试步骤：
        1. 预置一个Vlan类型的VPC（vpc fixture）
        2. 在Vlan VPC的子网中创建两台虚机（一次创建，count=2）
        3. 先获取两台虚机的内网IP，再一起绑定Mfip
        4. 分别ping对方虚机的内网IP，验证能ping通
        """

        # vpc fixture 返回的是字典，包含VPC信息
        vpc_name = vpc['name']
        vpc_subnet_name = vpc['subnet_name']
        vpc_network_type = vpc['network_type']  # 应该是 "Vlan"

        logger.info(f"Vlan VPC: {vpc_name}, 子网: {vpc_subnet_name}, 网络类型: {vpc_network_type}")

        # 步骤1: 在Vlan VPC的子网中一次性创建两台虚机（count=2）
        with allure_step_log("步骤1: 在Vlan VPC的子网中创建两台虚机"):
            vm_base_name = f"{vpc_name}-vm"

            # 一次性创建两台虚机，使用count=2
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_create(
                name=vm_base_name,
                count=2,  # 创建2台虚机
                network=vpc_name,  # 使用Vlan VPC
                subnet=vpc_subnet_name  # 使用VPC的子网
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")

            # 多台虚机时，名称会自动添加序号后缀
            vm1_name = f"{vm_base_name}-0"
            vm2_name = f"{vm_base_name}-1"

            # 等待两台虚机创建完成
            ecs_page.assert_status([vm1_name, vm2_name])

            # 先获取两台虚机的内网IP和项目信息
            vm1_data = ecs_page.get_row_data(vm1_name)
            vm1_ip = vm1_data['IP地址'].split(':')[1].strip()
            vm1_project = vm1_data['项目名称']

            vm2_data = ecs_page.get_row_data(vm2_name)
            vm2_ip = vm2_data['IP地址'].split(':')[1].strip()
            vm2_project = vm2_data['项目名称']

            logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, 项目: {vm1_project}")
            logger.info(f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, 项目: {vm2_project}")

        # 步骤2: 一起为两台虚机绑定Mfip
        with allure_step_log("步骤2: 为两台虚机绑定Mfip"):
            ecs_page.goto_service("网络设施")

            # 绑定第一台虚机的Mfip
            ecs_page.mfip_create(vm1_project, vpc_name, vm1_ip)
            ecs_page.assert_popup_success()

            # 绑定第二台虚机的Mfip
            ecs_page.mfip_create(vm2_project, vpc_name, vm2_ip)
            ecs_page.assert_popup_success()

            # 搜索并获取两台虚机的Mfip地址
            ecs_page.mfip_search(vm1_ip)
            vm1_mfip = ecs_page.get_column_data("Mfip 地址")[0]

            ecs_page.mfip_search(vm2_ip)
            vm2_mfip = ecs_page.get_column_data("Mfip 地址")[0]

            logger.info(f"虚机1 Mfip: {vm1_mfip}")
            logger.info(f"虚机2 Mfip: {vm2_mfip}")

        # 步骤3: 第一台虚机ping第二台虚机（同子网）
        with allure_step_log("步骤3: 第一台虚机ping第二台虚机（同子网）"):
            # 通过第一台虚机的mfip连接，并ping第二台虚机的内网IP
            ssh_vm.connect(vm1_mfip)

            ssh_vm.ping(vm2_ip)
            logger.info(f"✓ {vm1_name} ping {vm2_ip} 成功")

        # 步骤4: 第二台虚机ping第一台虚机（同子网）
        with allure_step_log("步骤4: 第二台虚机ping第一台虚机（同子网）"):
            # 通过第二台虚机的mfip连接，并ping第一台虚机的内网IP
            ssh_vm.connect(vm2_mfip)

            ssh_vm.ping(vm1_ip)
            logger.info(f"✓ {vm2_name} ping {vm1_ip} 成功")

        # 步骤5: 清理测试数据
        with allure_step_log("步骤5: 清理测试数据"):
            # 手动清理两台虚机
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove([vm1_name, vm2_name])
            ecs_page.ecs_delete([vm1_name, vm2_name])
            ecs_page.assert_deleted([vm1_name, vm2_name])
            logger.info(f"已手动清理虚机: {vm1_name}, {vm2_name}")

    # @allure.title("Vlan网络-同子网的两台虚机互通验证")
    # @pytest.mark.parametrize("vpc", [{
    #     "network_type": "Vlan",
    #     "gateway_mode": "分布式网关",
    #     "vlan_id": random.randint(3000, 4000)
    # }], indirect=True)
    # @pytest.mark.parametrize("vm", [{"count": 2}], indirect=True)
    # def test_vlan_two_vms_ping2(self, vpc, vm, ssh_vm):
    #     """
    #     测试Vlan网络内两台虚拟机通过内网IP互相ping通
    #
    #     测试步骤：
    #     1. 预置一个Vlan类型的VPC（vpc fixture）
    #     2. 预置两台虚机到VPC的子网中（vm fixture，自动使用vpc的网络和子网）
    #     3. 分别ping对方虚机的内网IP，验证能ping通
    #     """
    #
    #     # vpc fixture 返回VPC信息
    #     vpc_name = vpc['name']
    #     vpc_subnet_name = vpc['subnet_name']
    #
    #     logger.info(f"Vlan VPC: {vpc_name}, 子网: {vpc_subnet_name}")
    #
    #     # vm fixture 返回两台虚机信息的列表（自动绑定Mfip）
    #     vm1_data = vm[0]
    #     vm2_data = vm[1]
    #
    #     vm1_name = vm1_data['name']
    #     vm2_name = vm2_data['name']
    #     vm1_ip = vm1_data['ip']
    #     vm2_ip = vm2_data['ip']
    #     vm1_mfip = vm1_data['mfip']
    #     vm2_mfip = vm2_data['mfip']
    #
    #     logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, Mfip: {vm1_mfip}")
    #     logger.info(f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, Mfip: {vm2_mfip}")
    #
    #     with allure_step_log("步骤1: 第一台虚机ping第二台虚机"):
    #         ssh_vm.connect(vm1_mfip)
    #         ssh_vm.ping(vm2_ip)
    #         logger.info(f"✓ {vm1_name} ping {vm2_ip} 成功")
    #
    #     with allure_step_log("步骤2: 第二台虚机ping第一台虚机"):
    #         ssh_vm.connect(vm2_mfip)
    #         ssh_vm.ping(vm1_ip)
    #         logger.info(f"✓ {vm2_name} ping {vm1_ip} 成功")

    @allure.title("Vlan网络-同子网的两台虚机互通验证（集中式网关）")
    @pytest.mark.parametrize("vpc", [{
        "network_type": "Vlan",
        "gateway_mode": "集中式网关",
        "vlan_id": 303,
        "cidr": "172.22.16.0/24",
        "gateway_ip": "172.22.16.254",
        "mac": "60:f1:8a:5a:31:9b"
    }], indirect=True)
    def test_vlan_two_vms_ping_centralized(self, vpc, ecs_page, ssh_vm):
        """
        测试集中式网关模式下Vlan网络内两台虚拟机通过内网IP互相ping通

        测试步骤：
        1. 预置一个集中式网关模式的Vlan类型VPC（vpc fixture）
        2. 在Vlan VPC的子网中创建两台虚机（一次创建，count=2）
        3. 先获取两台虚机的内网IP，再一起绑定Mfip
        4. 分别ping对方虚机的内网IP，验证能ping通
        """

        # vpc fixture 返回的是字典，包含VPC信息
        vpc_name = vpc['name']
        vpc_subnet_name = vpc['subnet_name']
        vpc_network_type = vpc['network_type']  # 应该是 "Vlan"
        vpc_gateway_mode = vpc['gateway_mode']  # 应该是 "集中式网关"

        logger.info(
            f"Vlan VPC: {vpc_name}, 子网: {vpc_subnet_name}, 网络类型: {vpc_network_type}, 网关模式: {vpc_gateway_mode}")

        # 步骤1: 在Vlan VPC的子网中一次性创建两台虚机（count=2）
        with allure_step_log("步骤1: 在Vlan VPC的子网中创建两台虚机"):
            vm_base_name = f"{vpc_name}-vm"

            # 一次性创建两台虚机，使用count=2
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_create(
                name=vm_base_name,
                count=2,  # 创建2台虚机
                network=vpc_name,  # 使用Vlan VPC
                subnet=vpc_subnet_name  # 使用VPC的子网
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")

            # 多台虚机时，名称会自动添加序号后缀
            vm1_name = f"{vm_base_name}-0"
            vm2_name = f"{vm_base_name}-1"

            # 等待两台虚机创建完成
            ecs_page.assert_status([vm1_name, vm2_name])

            # 先获取两台虚机的内网IP和项目信息
            vm1_data = ecs_page.get_row_data(vm1_name)
            vm1_ip = vm1_data['IP地址'].split(':')[1].strip()
            vm1_project = vm1_data['项目名称']

            vm2_data = ecs_page.get_row_data(vm2_name)
            vm2_ip = vm2_data['IP地址'].split(':')[1].strip()
            vm2_project = vm2_data['项目名称']

            logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, 项目: {vm1_project}")
            logger.info(f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, 项目: {vm2_project}")

        # 步骤2: 一起为两台虚机绑定Mfip
        with allure_step_log("步骤2: 为两台虚机绑定Mfip"):
            ecs_page.goto_service("网络设施")

            # 绑定第一台虚机的Mfip
            ecs_page.mfip_create(vm1_project, vpc_name, vm1_ip)
            ecs_page.assert_popup_success()

            # 绑定第二台虚机的Mfip
            ecs_page.mfip_create(vm2_project, vpc_name, vm2_ip)
            ecs_page.assert_popup_success()

            # 搜索并获取两台虚机的Mfip地址
            ecs_page.mfip_search(vm1_ip)
            vm1_mfip = ecs_page.get_column_data("Mfip 地址")[0]

            ecs_page.mfip_search(vm2_ip)
            vm2_mfip = ecs_page.get_column_data("Mfip 地址")[0]

            logger.info(f"虚机1 Mfip: {vm1_mfip}")
            logger.info(f"虚机2 Mfip: {vm2_mfip}")

        # 步骤3: 第一台虚机ping第二台虚机（同子网）
        with allure_step_log("步骤3: 第一台虚机ping第二台虚机（同子网）"):
            # 通过第一台虚机的mfip连接，并ping第二台虚机的内网IP
            ssh_vm.connect(vm1_mfip)

            ssh_vm.ping(vm2_ip)
            logger.info(f"✓ {vm1_name} ping {vm2_ip} 成功")

        # 步骤4: 第二台虚机ping第一台虚机（同子网）
        with allure_step_log("步骤4: 第二台虚机ping第一台虚机（同子网）"):
            # 通过第二台虚机的mfip连接，并ping第一台虚机的内网IP
            ssh_vm.connect(vm2_mfip)

            ssh_vm.ping(vm1_ip)
            logger.info(f"✓ {vm2_name} ping {vm1_ip} 成功")

        # 步骤5: 清理测试数据
        with allure_step_log("步骤5: 清理测试数据"):
            # 手动清理两台虚机
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove([vm1_name, vm2_name])
            ecs_page.ecs_delete([vm1_name, vm2_name])
            ecs_page.assert_deleted([vm1_name, vm2_name])
            logger.info(f"已手动清理虚机: {vm1_name}, {vm2_name}")
