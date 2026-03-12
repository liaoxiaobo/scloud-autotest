import random
import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger

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


    @allure.title("双栈网络-同子网的两台虚机互通验证")
    @pytest.mark.parametrize("vpc", [{
        "network_type": "Geneve",
        "enable_ipv6": True
    }], indirect=True)
    def test_dual_stack_two_vms_ping(self, vpc, ecs_page, ssh_vm):
        """
        测试Flat网络内两台虚拟机通过内网IP互相ping通
        """

        # vpc fixture 返回的是字典，包含VPC信息
        vpc_name = vpc['name']
        vpc_subnet_name = vpc['subnet_name']
        vpc_network_type = vpc['network_type']

        logger.info(f"Vlan VPC: {vpc_name}, 子网: {vpc_subnet_name}, 网络类型: {vpc_network_type}")

        # 步骤1: 在Vlan VPC的子网中一次性创建两台虚机（count=2）
        with allure_step_log("步骤1: 在Vlan VPC的子网中创建两台虚机"):
            vm_base_name = f"{vpc_name}-vm"

            # 一次性创建两台虚机，使用count=2
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_create(
                name=vm_base_name,
                count=2,  # 创建2台虚机
                network=vpc_name,  # 使用Flat VPC
                subnet=vpc_subnet_name,  # 使用VPC的子网
                enable_ipv6=True
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")

            # 多台虚机时，名称会自动添加序号后缀
            vm1_name = f"{vm_base_name}-0"
            vm2_name = f"{vm_base_name}-1"

            # 等待两台虚机创建完成
            ecs_page.assert_status([vm1_name, vm2_name])

            # 先获取两台虚机的内网IP和项目信息
            vm1_data = ecs_page.get_row_data(vm1_name)
            vm1_ip = vm1_data['IP地址'].split("固定: ")[-1].strip()
            vm1_ipv6 = vm1_data['IP地址'].split("固定: ")[-2].strip()
            vm1_project = vm1_data['项目名称']

            vm2_data = ecs_page.get_row_data(vm2_name)
            vm2_ip = vm2_data['IP地址'].split("固定: ")[-1].strip()
            vm2_ipv6 = vm2_data['IP地址'].split("固定: ")[-2].strip()
            vm2_project = vm2_data['项目名称']

            logger.info(f"虚机1: {vm1_name}, 内网IP: {vm1_ip}, 项目: {vm1_project}")
            logger.info(f"虚机2: {vm2_name}, 内网IP: {vm2_ip}, 项目: {vm2_project}")

        # 步骤2: 一起为两台虚机绑定Mfip
        with allure_step_log("步骤2: 为两台虚机绑定Mfip"):
            ecs_page.goto_service("网络设施")

            # 绑定第一台虚机的Mfip
            ecs_page.mfip_create(vm1_project, vpc_name, vm1_ip, exact=False)
            ecs_page.assert_popup_success()

            # 绑定第二台虚机的Mfip
            ecs_page.mfip_create(vm2_project, vpc_name, vm2_ip, exact=False)
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
            ssh_vm.ping(vm2_ipv6, ipv6=True)
            logger.info(f"✓ {vm1_name} ping {vm2_ip} 成功")

        # 步骤4: 第二台虚机ping第一台虚机（同子网）
        with allure_step_log("步骤4: 第二台虚机ping第一台虚机（同子网）"):
            # 通过第二台虚机的mfip连接，并ping第一台虚机的内网IP
            ssh_vm.connect(vm2_mfip)

            ssh_vm.ping(vm1_ip)
            ssh_vm.ping(vm1_ipv6, ipv6=True)
            logger.info(f"✓ {vm2_name} ping {vm1_ip} 成功")

        # 步骤5: 清理测试数据
        with allure_step_log("步骤5: 清理测试数据"):
            # 手动清理两台虚机
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove([vm1_name, vm2_name])
            ecs_page.ecs_delete([vm1_name, vm2_name])
            ecs_page.assert_deleted([vm1_name, vm2_name])
            logger.info(f"已手动清理虚机: {vm1_name}, {vm2_name}")