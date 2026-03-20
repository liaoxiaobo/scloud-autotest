import pytest
import allure
from sugon_web.utils.util import random_data
from sugon_web.utils.logger import allure_step_log, logger

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
            vpc_page.wait_for_page_ready()
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

    @allure.title("DNAT规则-创建和删除")
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": False}], indirect=True)
    def test_dnat_rule_create_delete(self, vpc_page, nat, vpc, vm):

        """测试在NAT网关详情页创建和删除DNAT规则"""
        nat_name = nat['name']
        subnet_cidr = vpc['cidr']   # 使用 vpc fixture 提供的子网 CIDR 定位子网
        private_ip = vm['ip']       # 使用 vm fixture 提供的虚机内网IP
        ext_port = 8080
        int_port = 80
        desc = "DNAT规则创建删除测试"
        logger.info(f"使用虚机 {vm['name']} 的内网IP {private_ip} 作为DNAT私网IP")

        with allure_step_log("步骤1: 进入NAT网关详情页，创建DNAT规则"):
            vpc_page.goto_service("NAT网关")
            vpc_page.dnat_rule_create(
                nat_name=nat_name,
                ext_port=ext_port,
                subnet_cidr=subnet_cidr,
                protocol="TCP",
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
            assert "TCP" in data.get("协议", ""), \
                f"协议断言失败: 期望包含 TCP, 实际 {data.get('协议')}"
            assert private_ip in data.get("私网IP", ""), \
                f"私网IP断言失败: 期望包含 {private_ip}, 实际 {data.get('私网IP')}"
            assert desc in data.get("描述", ""), \
                f"描述断言失败: 期望包含 {desc}, 实际 {data.get('描述')}"

        with allure_step_log("步骤3: 删除DNAT规则"):
            vpc_page.dnat_rule_delete(ext_port)

        with allure_step_log("步骤4: 验证DNAT规则已删除"):
            vpc_page.assert_deleted(str(ext_port))

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






