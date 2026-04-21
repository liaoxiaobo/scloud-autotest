from time import sleep

import pytest
import allure
from sugon_web.utils.util import random_data, load_data
from sugon_web.utils.logger import allure_step_log, logger


def _get_snat_public_ip(data):
    """兼容页面可能使用的不同公网 IP 列名。"""
    return data.get("弹性公网IP", "") or data.get("公网IP", "")


@allure.epic('网络服务')
@allure.feature('NAT网关')
@allure.story('基本功能验证')
class TestNAT:
    
    @allure.title("NAT网关-创建和删除")
    def test_nat_create_delete(self, vpc_page, vpc):
        """测试创建和删除NAT网关功能"""
        nat_name = random_data()
        vpc_name = vpc['name']
        
        with allure_step_log("步骤1: 创建NAT网关"):
            # 记录里的操作入口在NAT网关
            vpc_page.goto_service("NAT网关")
            vpc_page.nat_create(
                name=nat_name,
                vpc_name=vpc_name,
                desc="NAT网关单条创建删除测试"
            )
            # 根据录制脚本，会有“新建NAT网关成功”的提示
            vpc_page.assert_popup_success("新建NAT网关成功")
            
        with allure_step_log("步骤2: 验证NAT网关列表数据"):
            data = vpc_page.get_row_data(nat_name)
            logger.info(f"NAT网关行数据: {data}")
            assert vpc_name in data.get("连接资源", ""), \
                f"连接资源断言失败: 期望包含 {vpc_name}, 实际 {data.get('连接资源')}"
            assert "NAT网关单条创建删除测试" in data.get("描述", ""), \
                f"描述断言失败: 期望包含 'NAT网关单条创建删除测试', 实际 {data.get('描述')}"
            
        with allure_step_log("步骤3: 删除NAT网关"):
            vpc_page.nat_delete(nat_name)
            
        with allure_step_log("步骤4: 验证NAT网关已删除"):
            vpc_page.assert_deleted(nat_name)

    @allure.title("NAT网关-批量删除")
    def test_nat_batch_delete(self, vpc_page, vpc):
        """测试批量删除多个NAT网关"""
        vpc_name = vpc['name']
        nat_names = []
        
        with allure_step_log("步骤1: 创建2个NAT网关"):
            for i in range(2):
                nat_name = random_data()
                nat_names.append(nat_name)
                
                # 每次创建前回到列表页
                vpc_page.goto_service("NAT网关")
                vpc_page.nat_create(
                    name=nat_name,
                    vpc_name=vpc_name,
                    desc=f"NAT网关批量删除测试_{i}"
                )
                vpc_page.assert_popup_success("新建NAT网关成功")
                
        with allure_step_log("步骤2: 批量删除NAT网关"):
            vpc_page.nat_delete(nat_names)
            
        with allure_step_log("步骤3: 验证NAT网关已删除"):
            vpc_page.assert_deleted(nat_names)

    @allure.title("NAT网关-搜索&重置")
    def test_nat_search(self, vpc_page, nat):
        """测试NAT网关搜索和重置功能（依赖 nat fixture）"""
        nat_name = nat['name']

        with allure_step_log("步骤1: 输入名称关键字进行搜索"):
            # 取名称前几位作为模糊搜索关键字（随机名通常较长，取前 4 位即可区分）
            keyword = nat_name[:-2]
            vpc_page.goto_service("NAT网关")
            vpc_page.search(keyword)


        with allure_step_log("步骤2: 验证搜索结果正确"):
            # 断言列表中包含该 NAT 网关名称
            vpc_page.assert_list_contain(nat_name)

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.btn_reset.click()
            # 断言搜索框已清空
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 验证重置后列表恢复，目标NAT网关仍存在"):
            vpc_page.assert_list_contain(nat_name)

    @allure.title("NAT网关-修改名称和描述")
    def test_nat_edit(self, vpc_page, nat):
        """测试修改NAT网关名称和描述（依赖 nat fixture）"""
        old_name = nat['name']
        new_name = random_data()
        new_desc = "修改后的NAT网关描述"

        with allure_step_log("步骤1: 修改NAT网关名称和描述"):
            vpc_page.goto_service("NAT网关")
            vpc_page.nat_edit(
                name=old_name,
                new_name=new_name,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success("修改NAT网关成功")

        with allure_step_log("步骤2: 验证修改结果"):
            data = vpc_page.get_row_data(new_name)
            logger.info(f"修改后NAT网关行数据: {data}")
            assert new_name == data.get("名称", ""), \
                f"名称断言失败: 期望 {new_name}, 实际 {data.get('名称')}"
            assert new_desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {new_desc}, 实际 {data.get('描述')}"

        # 将名称同步回 nat fixture，确保 teardown 能正确删除
        nat['name'] = new_name

    @allure.title("NAT网关-解绑&绑定公网IP")
    def test_nat_bind_unbind_eip(self, vpc_page, nat):
        """测试NAT网关解绑和绑定弹性公网IP（依赖 nat fixture）"""
        nat_name = nat['name']

        with allure_step_log("步骤1: 解绑弹性公网IP"):
            vpc_page.goto_service("NAT网关")
            eip = vpc_page.nat_unbind_eip(nat_name)
            logger.info(f"被解绑的EIP: {eip}")
            vpc_page.assert_popup_success("绑定/解绑 FIP成功")

        with allure_step_log("步骤2: 验证解绑后列表EIP字段已清空"):
            data = vpc_page.get_row_data(nat_name)
            logger.info(f"解绑后行数据: {data}")
            # 页面未绑定 EIP 时显示"--"占位符而非空字符串，所以断言原 EIP 不在字段中
            assert eip not in data.get("弹性公网IP", ""), \
                f"解绑后断言失败: 期望字段不包含 {eip}, 实际 {data.get('弹性公网IP')}"


        with allure_step_log("步骤3: 重新绑定弹性公网IP"):
            new_eip = vpc_page.nat_bind_eip(nat_name)
            logger.info(f"绑定的EIP: {new_eip}")
            vpc_page.assert_popup_success("绑定/解绑 FIP成功")

        with allure_step_log("步骤4: 验证绑定后列表EIP字段已更新"):
            data = vpc_page.get_row_data(nat_name)
            logger.info(f"绑定后行数据: {data}")
            assert new_eip in data.get("弹性公网IP", ""), \
                f"绑定后断言失败: 期望'弹性公网IP'包含 {new_eip}, 实际 {data.get('弹性公网IP')}"

    @allure.title("SNAT规则-创建和删除-{params[case_name]}")
    @pytest.mark.parametrize("params", [
        {"case_name": "所有源地址", "source_type": "所有", "source_value_mode": "all"},
        {"case_name": "子网源地址", "source_type": "子网", "source_value_mode": "subnet"},
        {"case_name": "私网IP源地址", "source_type": "私网IP", "source_value_mode": "private_ip"},
        {"case_name": "自定义源地址", "source_type": "自定义", "source_value_mode": "custom"},
    ])
    def test_snat_rule_create_delete(self, vpc_page, nat, vpc, request, params):
        """测试在NAT网关详情页创建和删除不同源地址类型的SNAT规则"""
        nat_name = nat['name']
        source_type = params["source_type"]
        source_value_mode = params["source_value_mode"]
        desc = f"SNAT规则{params['case_name']}创建删除测试"

        if source_value_mode == "all":
            source_value = None
            source_address = "0.0.0.0/0"
        elif source_value_mode == "subnet":
            source_value = vpc["cidr"]
            source_address = source_value
        elif source_value_mode == "private_ip":
            vm_data = request.getfixturevalue("vm")
            source_value = {"subnet_cidr": vpc["cidr"], "private_ip": vm_data["ip"]}
            source_address = vm_data["ip"]
        else:
            source_value = random_data("cidr")
            source_address = source_value

        with allure_step_log(f"步骤1: 进入NAT网关详情页，创建{params['case_name']}的SNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.snat_rule_create(
                nat_name=nat_name,
                source_type=source_type,
                source_value=source_value,
                desc=desc
            )
            vpc_page.assert_popup_success("新建SNAT规则成功")

        with allure_step_log("步骤2: 验证SNAT规则列表数据"):
            data = vpc_page.get_row_data(source_address)
            logger.info(f"SNAT规则行数据: {data}")
            assert source_address in data.get("源地址", ""), \
                f"源地址断言失败: 期望包含 {source_address}, 实际 {data.get('源地址')}"
            assert desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {desc}, 实际 {data.get('描述')}"

        with allure_step_log("步骤3: 删除SNAT规则"):
            vpc_page.snat_rule_delete(source_address)

        with allure_step_log("步骤4: 验证SNAT规则已删除"):
            vpc_page.assert_deleted(source_address)

    @allure.title("SNAT规则-修改私有子网和描述")
    def test_snat_rule_edit(self, vpc_page, nat):
        """测试在NAT网关详情页修改SNAT规则的源地址和描述"""
        nat_name = nat['name']
        old_source_address = "0.0.0.0/0"
        new_source_address = random_data("cidr")
        old_desc = "SNAT规则修改前描述"
        new_desc = "SNAT规则修改后描述"

        with allure_step_log("步骤1: 新建一条SNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.snat_rule_create(
                nat_name=nat_name,
                source_type="所有",
                desc=old_desc
            )
            vpc_page.assert_popup_success("新建SNAT规则成功")

        with allure_step_log("步骤2: 修改SNAT规则的源地址和描述"):
            vpc_page.goto_service("NAT网关")
            vpc_page.snat_rule_edit(
                nat_name=nat_name,
                source_address=old_source_address,
                new_source_type="自定义",
                new_source_value=new_source_address,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success("修改SNAT规则成功")

        with allure_step_log("步骤3: 验证SNAT规则修改结果"):
            data = vpc_page.get_row_data(new_source_address)
            logger.info(f"修改后SNAT规则行数据: {data}")
            assert new_source_address in data.get("源地址", ""), \
                f"源地址断言失败: 期望包含 {new_source_address}, 实际 {data.get('源地址')}"
            assert new_desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {new_desc}, 实际 {data.get('描述')}"

        with allure_step_log("步骤4: 清理测试数据"):
            vpc_page.snat_rule_delete(new_source_address)
            vpc_page.assert_deleted(new_source_address)

    @allure.title("SNAT规则-批量删除")
    def test_snat_rule_batch_delete(self, vpc_page, nat):
        """测试在NAT网关详情页批量删除SNAT规则"""
        nat_name = nat['name']
        source_addresses = [
            random_data("cidr"),
            random_data("cidr")
        ]

        with allure_step_log("步骤1: 创建2条SNAT规则"):
            vpc_page.goto_service("NAT网关")
            for source_address in source_addresses:
                vpc_page.snat_rule_create(
                    nat_name=nat_name,
                    source_type="自定义",
                    source_value=source_address,
                    desc=f"SNAT批量删除测试{source_address}"
                )
                vpc_page.assert_popup_success("新建SNAT规则成功")

        with allure_step_log("步骤2: 批量删除SNAT规则"):
            vpc_page.snat_rule_delete(source_addresses)

        with allure_step_log("步骤3: 验证SNAT规则已删除"):
            vpc_page.assert_deleted(source_addresses)

    @allure.title("SNAT规则-搜索和重置")
    def test_snat_rule_search_reset(self, vpc_page, nat):
        """测试在NAT网关详情页搜索和重置SNAT规则"""
        nat_name = nat['name']
        source_address = "0.0.0.0/0"

        with allure_step_log("步骤1: 进入NAT网关详情页，创建一个SNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.snat_rule_create(
                nat_name=nat_name,
                source_type="所有",
                desc="SNAT搜索重置测试"
            )
            vpc_page.assert_popup_success("新建SNAT规则成功")

        with allure_step_log("步骤2: 按源地址进行搜索"):
            vpc_page.search(source_address)
            vpc_page.assert_list_contain(source_address, column_name="源地址")

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.btn_reset.click()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 验证重置后列表恢复并清理测试数据"):
            vpc_page.assert_list_contain(source_address, column_name="源地址")
            vpc_page.snat_rule_delete(source_address)
            vpc_page.assert_deleted(source_address)

    @allure.title("DNAT规则-创建和删除-{params[case_name]}")
    @pytest.mark.parametrize("params", load_data('test_dnat_rule_create_delete', data_file='test_network.yaml'))
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": False}], indirect=True)
    def test_dnat_rule_create_delete(self, vpc_page, nat, vpc, vm, params):

        """测试在NAT网关详情页创建和删除DNAT规则"""
        nat_name = nat['name']
        subnet_cidr = vpc['cidr']   # 使用 vpc fixture 提供的子网 CIDR 定位子网
        private_ip = vm['ip']       # 使用 vm fixture 提供的虚机内网IP
        ext_port = params['ext_port']
        int_port = params['int_port']
        protocol = params['protocol']
        desc = params['desc']
        logger.info(f"使用虚机 {vm['name']} 的内网IP {private_ip} 作为DNAT私网IP")

        with allure_step_log("步骤1: 进入NAT网关详情页，创建DNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=ext_port,
                subnet_cidr=subnet_cidr,
                protocol=protocol,
                private_ip=private_ip,
                int_port=int_port,
                desc=desc
            )
            vpc_page.assert_popup_success("新建DNAT规则成功")

        with allure_step_log("步骤2: 验证DNAT规则列表数据"):
            data = vpc_page.get_row_data(str(ext_port))
            logger.info(f"DNAT规则行数据: {data}")
            assert str(ext_port) in data.get("公网端口", ""), \
                f"公网端口断言失败: 期望包含 {ext_port}, 实际 {data.get('公网端口')}"
            assert str(int_port) in data.get("私网端口", ""), \
                f"私网端口断言失败: 期望包含 {int_port}, 实际 {data.get('私网端口')}"
            assert protocol in data.get("协议", ""), \
                f"协议断言失败: 期望包含 {protocol}, 实际 {data.get('协议')}"
            assert private_ip in data.get("私网IP", ""), \
                f"私网IP断言失败: 期望包含 {private_ip}, 实际 {data.get('私网IP')}"
            assert desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {desc}, 实际 {data.get('描述')}"

        with allure_step_log("步骤3: 删除DNAT规则"):
            vpc_page.dnat_rule_delete(ext_port)

        with allure_step_log("步骤4: 验证DNAT规则已删除"):
            vpc_page.assert_deleted(str(ext_port))

    @allure.title("DNAT规则-修改协议和端口等配置")
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": False}], indirect=True)
    def test_dnat_rule_edit(self, vpc_page, nat, vpc, vm):
        """测试在NAT网关详情页修改DNAT规则的协议、公网端口、内部端口和描述"""
        nat_name = nat['name']
        subnet_cidr = vpc['cidr']
        private_ip = vm['ip']
        ext_port = 9080
        new_ext_port = 9081
        old_int_port = 80
        new_int_port = 8080
        old_protocol = "TCP"
        new_protocol = "UDP"
        old_desc = "DNAT规则修改前描述"
        new_desc = "DNAT规则修改后描述"

        with allure_step_log("步骤1: 进入NAT网关详情页，创建一条DNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=ext_port,
                subnet_cidr=subnet_cidr,
                protocol=old_protocol,
                private_ip=private_ip,
                int_port=old_int_port,
                desc=old_desc
            )
            vpc_page.assert_popup_success("新建DNAT规则成功")

        with allure_step_log("步骤2: 修改DNAT规则的协议、公网端口、内部端口和描述"):
            vpc_page.goto_service("NAT网关")
            vpc_page.dnat_rule_edit(
                nat_name=nat_name,
                ext_port=ext_port,
                new_ext_port=new_ext_port,
                new_protocol=new_protocol,
                new_int_port=new_int_port,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success("修改DNAT规则成功")

        with allure_step_log("步骤3: 验证DNAT规则修改结果"):
            data = vpc_page.get_row_data(str(new_ext_port))
            logger.info(f"修改后DNAT规则行数据: {data}")
            assert new_protocol in data.get("协议", ""), \
                f"协议断言失败: 期望包含 {new_protocol}, 实际 {data.get('协议')}"
            assert str(new_ext_port) in data.get("公网端口", ""), \
                f"公网端口断言失败: 期望包含 {new_ext_port}, 实际 {data.get('公网端口')}"
            assert str(new_int_port) in data.get("私网端口", ""), \
                f"私网端口断言失败: 期望包含 {new_int_port}, 实际 {data.get('私网端口')}"
            assert private_ip in data.get("私网IP", ""), \
                f"私网IP断言失败: 期望包含 {private_ip}, 实际 {data.get('私网IP')}"
            assert new_desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {new_desc}, 实际 {data.get('描述')}"

        with allure_step_log("步骤4: 删除DNAT规则"):
            vpc_page.dnat_rule_delete(new_ext_port)

        with allure_step_log("步骤5: 验证DNAT规则已删除"):
            vpc_page.assert_deleted(str(new_ext_port))

    @allure.title("DNAT规则-批量删除")
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": False}], indirect=True)
    def test_dnat_rule_batch_delete(self, vpc_page, nat, vpc, vm):
        """测试在NAT网关详情页批量删除DNAT规则"""
        nat_name = nat['name']
        subnet_cidr = vpc['cidr']
        private_ip = vm['ip']
        ports = ["8080", "8082"]
        
        with allure_step_log("步骤1: 进入NAT网关详情页，创建2条DNAT规则"):
            vpc_page.goto_service("NAT网关")
            for port in ports:
                vpc_page.dnat_rule_create(
                    nat_name=nat_name,
                    ext_port=port,
                    subnet_cidr=subnet_cidr,
                    private_ip=private_ip,
                    int_port=port,
                    desc=f"批量删除测试端口 {port}"
                )
                vpc_page.assert_popup_success("新建DNAT规则成功")
                # 创建完后会留在详情页，不需要每次 goto_service

        with allure_step_log("步骤2: 批量删除DNAT规则"):
            vpc_page.dnat_rule_delete(ports)

        with allure_step_log("步骤3: 验证DNAT规则均已删除"):
            vpc_page.assert_deleted(ports)

    @allure.title("DNAT规则-搜索和重置")
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": False}], indirect=True)
    def test_dnat_rule_search_reset(self, vpc_page, nat, vpc, vm):
        """测试在NAT网关详情页搜索和重置DNAT规则"""
        nat_name = nat['name']
        subnet_cidr = vpc['cidr']
        private_ip = vm['ip']
        ext_port = 9090
        int_port = 80
        protocol = "TCP"
        
        with allure_step_log("步骤1: 进入NAT网关详情页，创建一个DNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=ext_port,
                subnet_cidr=subnet_cidr,
                protocol=protocol,
                private_ip=private_ip,
                int_port=int_port,
                desc="搜索重置测试规则"
            )
            vpc_page.assert_popup_success("新建DNAT规则成功")

        with allure_step_log("步骤2: 按协议搜索"):
            vpc_page.search(protocol)
            vpc_page.assert_list_contain(protocol, column_name="协议")

        with allure_step_log("步骤3: 按公网端口搜索"):
            vpc_page.search(str(ext_port))
            vpc_page.assert_list_contain(str(ext_port), column_name="公网端口")

        with allure_step_log("步骤4: 按私网端口搜索"):
            vpc_page.search(str(int_port))
            vpc_page.assert_list_contain(str(int_port), column_name="私网端口")

        with allure_step_log("步骤5: 重置搜索"):
            vpc_page.btn_reset.click()
            # 重置后应该能看到之前的规则（如果列表只有这一条的话）
            vpc_page.assert_list_contain(str(ext_port), column_name="公网端口")
            # 也可以验证搜索框是否清空（如果 BasePage 有 _input_search 属性且暴露出来的逻辑支持）
            # expect(vpc_page._input_search).to_have_value("")
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("清理数据: 删除测试规则"):
            vpc_page.dnat_rule_delete(ext_port)
            vpc_page.assert_deleted(str(ext_port))

    @allure.title("DNAT场景-通过公网IP+公网端口登录虚机（TCP协议）")
    @pytest.mark.parametrize("vm", [{"bind_mfip": False}], indirect=True)
    def test_dnat_tcp_ssh_scenario(self, vpc_page, nat, vpc, vm):
        """场景一：通过公网IP:公网端口（基于TCP协议）来ssh登录虚机，登录成功即代表dnat规则已生效"""
        nat_name = nat['name']
        vpc_name = vpc['name']
        subnet_cidr = vpc['cidr']
        private_ip = vm['ip']
        vm_password = "admin1234@sugon"
        ext_port = 2222
        int_port = 22
        
        vpc_page.goto_service("NAT网关")
        with allure_step_log("步骤1: 获取NAT网关的公网IP"):
            data = vpc_page.get_row_data(nat_name)
            eip = data.get("弹性公网IP", "").strip()
            logger.info(f"NAT网关 EIP: {eip}")
            assert eip and eip != "--", "未获取到有效的EIP"

        with allure_step_log(f"步骤2: 创建DNAT规则，TCP映射 {eip}:{ext_port} 到 {private_ip}:{int_port}"):
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=ext_port,
                subnet_cidr=subnet_cidr,
                protocol="TCP",
                private_ip=private_ip,
                int_port=int_port,
                desc="DNAT TCP SSH登录验证"
            )
            vpc_page.assert_popup_success("新建DNAT规则成功")
            
        with allure_step_log("步骤3: 添加VPC路由表规则(下一跳NAT网关)"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.route_rule_create(
                vpc_name=vpc_name,
                dest_cidr="0.0.0.0/0",
                next_hop=nat_name,
                next_hop_type="NAT网关",
                desc="指向NAT网关的默认路由"
            )
            vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤4: 验证通过公网IP和公网端口SSH登录虚机"):
            from sugon_web.common.ssh import SSH
            ssh = SSH()
            try:
                ssh.connect(host=eip, port=ext_port, username='root', pwd=vm_password, use_jumphost=False)
                output = ssh.run("hostname")
                logger.info(f"成功通过公网IP登录虚机，hostname: {output}")
                assert output.strip() == vm['name'], f"期望hostname为 {vm['name']}，实际为 {output}"
            finally:
                ssh.close()
                # 清理数据：删除DNAT规则和路由表规则
                vpc_page.goto_service("NAT网关")
                # 需要进入详情页删除规则
                vpc_page.get_by_role("cell", name=nat_name).locator("a").click()
                vpc_page.get_by_role("tab", name="DNAT规则").click()
                vpc_page.dnat_rule_delete(ext_port)
                vpc_page.assert_deleted(str(ext_port))
                
                # 清理路由表规则
                vpc_page.goto_service("虚拟私有云")
                # 路由表规则删除
                vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
                vpc_page.get_by_role("tab", name="路由表").click()
                vpc_page.route_rule_delete("0.0.0.0/0")

    @allure.title("DNAT场景-探测公网IP公网端口验证规则生效（UDP协议）")
    def test_dnat_udp_probe_scenario(self, vpc_page, nat, vpc, vm, ssh_vm, ssh_host):
        """场景二：通过探测公网IP:公网端口（基于UDP协议）来验证dnat规则已生效"""
        nat_name = nat['name']
        vpc_name = vpc['name']
        subnet_cidr = vpc['cidr']
        private_ip = vm['ip']
        vm_mfip = vm['mfip']

        udp_ext_port = 4080  # UDP探测公网端口
        int_port = 8080      # UDP服务端私网端口
        
        vpc_page.goto_service("NAT网关")
        with allure_step_log("步骤1: 获取NAT网关的公网IP"):
            data = vpc_page.get_row_data(nat_name)
            eip = data.get("弹性公网IP", "").strip()
            logger.info(f"NAT网关 EIP: {eip}")
            assert eip and eip != "--", "未获取到有效的EIP"

        with allure_step_log("步骤2: 创建UDP DNAT规则"):
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=udp_ext_port,
                subnet_cidr=subnet_cidr,
                protocol="UDP",
                private_ip=private_ip,
                int_port=int_port,
                desc="DNAT UDP 探测验证"
            )
            vpc_page.assert_popup_success("新建DNAT规则成功")

        with allure_step_log("步骤2.5: 添加VPC路由表规则(下一跳NAT网关)"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.route_rule_create(
                vpc_name=vpc_name,
                dest_cidr="0.0.0.0/0",
                next_hop=nat_name,
                next_hop_type="NAT网关",
                desc="指向NAT网关的默认路由"
            )
            vpc_page.assert_popup_success("新建路由表规则成功")

        with allure_step_log("步骤3: 通过mfip登录虚机并启动UDP监听服务"):
            ssh_vm.connect(host=vm_mfip)
            ssh_vm.run("rm -f /tmp/udp_receive.log")
            ssh_vm.run(
                f"nohup sh -c \"nc -uvl {int_port} > /tmp/udp_receive.log 2>&1\" > /dev/null 2>&1 &"
            )
            logger.info(f"在虚机 {vm['name']} 启动了 nc UDP {int_port} 端口监听...")
            import time
            listen_ready = False
            listen_output = ""
            for _ in range(20):
                time.sleep(5)
                listen_output = ssh_vm.run("cat /tmp/udp_receive.log")
                if str(int_port) in listen_output:
                    listen_ready = True
                    break
            logger.info(f"虚机UDP监听启动日志: {listen_output}")
            assert listen_ready, f"虚机nc未成功监听UDP {int_port} 端口，日志输出: {listen_output}"

        with allure_step_log("步骤4: 后台向公网IP:UDP公网端口发送探测报文"):
            msg = "dnat_udp_probe_test_message"
            udp_send_code = (
                "import socket; "
                "sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
                f"sock.sendto({msg!r}.encode('utf-8'), ({eip!r}, {udp_ext_port})); "
                "sock.close()"
            )
            ssh_host.run(f"python3 -c {udp_send_code!r} || python -c {udp_send_code!r}")
            logger.info(f"向 {eip}:{udp_ext_port} 发送了UDP消息: {msg}")

        with allure_step_log("步骤5: 验证虚机是否收到UDP请求，以证明DNAT生效"):
            output = ""
            for _ in range(20):
                time.sleep(5)
                output = ssh_vm.run("cat /tmp/udp_receive.log")
                if msg in output:
                    break
            logger.info(f"虚机UDP监听日志输出: {output}")
            assert msg in output, "虚机未能接收到UDP探测报文，DNAT规则（UDP）可能未生效"

        with allure_step_log("步骤6: 清理UDP监听进程和测试配置"):
            ssh_vm.run(f"pkill -f \"nc -uvl {int_port}\"")
            vpc_page.goto_service("NAT网关")
            vpc_page.get_by_role("cell", name=nat_name).locator("a").click()
            vpc_page.get_by_role("tab", name="DNAT规则").click()
            vpc_page.dnat_rule_delete(str(udp_ext_port))
            vpc_page.assert_deleted(str(udp_ext_port))

            vpc_page.goto_service("虚拟私有云")
            vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="路由表").click()
            vpc_page.route_rule_delete("0.0.0.0/0")
