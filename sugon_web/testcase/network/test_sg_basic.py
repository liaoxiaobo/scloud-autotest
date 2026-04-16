import allure
import pytest
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data


@allure.epic('网络服务')
@allure.feature('网络安全-安全组')
@allure.story('基本功能验证')
class TestSGBasic:
    @allure.title("安全组-创建和删除")
    def test_sg_create(self, sg_page):

        with allure_step_log(f"步骤1: 新建安全组"):
            sg_page.goto_service("安全组")
            sg_name = random_data()
            sg_page.sg_create(sg_name, desc=f"{sg_name}测试安全组")
            sg_page.assert_status(sg_name, status=f"{sg_name}测试安全组")

        with allure_step_log(f"步骤2: 列表页，点击安全组名称进入详情，查看安全组规则。默认自带两条出方向的规则"):
            sg_page.goto_sg_detail(sg_name)
            directions = sg_page.get_column_data("方向入口出口   筛选   重置 ")
            assert len(directions) == 2, "安全组详情页默认出方向规则数非2"

        with allure_step_log(f"步骤3: 清理测试资源-安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_name)
            sg_page.assert_deleted(sg_name)

    @allure.title("安全组-搜索和重置")
    def test_sg_search(self, sg_page, sg):
        sg_name = sg
        with allure_step_log(f"步骤1: 搜索安全组: {sg_name}"):
            sg_page.goto_service("安全组")
            sg_page.sg_search(sg_name)
            
            # 使用模糊匹配断言列表中包含搜索关键字
            sg_page.assert_list_contain(sg_name, exact_match=False)

        with allure_step_log(f"步骤2: 重置搜索条件"):
            sg_page.sg_search_reset()
            assert sg_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("安全组-修改名称和描述")
    def test_sg_edit(self, sg_page, sg):
        sg_name = sg
        new_name = f"{sg_name}-edit"
        new_desc = f"巨长描述: {sg_name}{random_data('string', 100)}"
        orig_desc = f"{sg_name}测试安全组"

        with allure_step_log(f"步骤1: 编辑安全组名称和描述: {sg_name} -> {new_name}"):
            sg_page.sg_edit(sg_name, new_name=new_name, new_desc=new_desc)
            sg_page.assert_popup_success(f"{new_name}安全组修改成功")
            # 搜索后验证修改是否成功
            sg_page.sg_search(new_name)
            sg_page.assert_list_contain(new_name, exact_match=False)

        with allure_step_log(f"步骤2: 恢复安全组名称和描述: {new_name} -> {sg_name}"):
            sg_page.sg_search_reset()
            sg_page.sg_edit(new_name, new_name=sg_name, new_desc=orig_desc)
            sg_page.assert_popup_success(f"{sg_name}安全组修改成功")
            sg_page.sg_search(sg_name)
            sg_page.assert_list_contain(sg_name, exact_match=False)
            sg_page.sg_search_reset()

    @allure.title("安全组-克隆")
    def test_sg_clone(self, ecs_page, sg_page, ssh_host, sg, vpc):
        sg_name = sg
        clone_name = f"{sg_name}-clone"

        with allure_step_log(f"前置准备: 申请/分配一个可用公网 IP 以备后续测试使用"):
            ecs_page.assign_ip()

        with allure_step_log(f"步骤1: 原安全组 {sg_name} 添加放行所有IPv4的入方向规则"):
            sg_page.sg_rule_create(
                sg_name=sg_name,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                description="放行所有IPv4流量"
            )

        with allure_step_log(f"步骤2: 克隆安全组 {sg_name} 为 {clone_name}"):
            sg_page.sg_clone(sg_name, clone_name=clone_name, clone_desc=f"{clone_name}安全组")
            sg_page.assert_popup_success("克隆安全组成功")
            sg_page.assert_status(clone_name, status=f"{clone_name}安全组")

        with allure_step_log(f"步骤3: 验证克隆的{clone_name}安全组规则与原始安全组 {sg_name} 的规则完全相同"):
            # 获取原安全组规则
            orig_rules = sg_page.sg_get_all_rules(sg_name)

            # 获取克隆安全组规则
            clone_rules = sg_page.sg_get_all_rules(clone_name)

            # 断言规则数量和内容完全一致
            assert len(orig_rules) == len(clone_rules), f"规则数量不一致: 原 {len(orig_rules)} 条 vs 克隆 {len(clone_rules)} 条"
            for i in range(len(orig_rules)):
                assert orig_rules[i] == clone_rules[i], f"第{i+1}条规则不一致:\n原:{orig_rules[i]}\n克隆:{clone_rules[i]}"

        with allure_step_log(f"步骤4: 进入ECS模块，使用安全组 {clone_name} 创建云服务器vm1，并绑定弹性公网ip:fip1"):
            network_name = vpc["name"]
            subnet_name = vpc["subnet_name"]
            
            ecs_page.goto_service("弹性云服务器")
            network = {"networks":[{"network": network_name, "subnet": subnet_name}], "security_groups": [clone_name]}
            vm1_info = ecs_page.ecs_create({}, {}, network, {}, {})
            vm1_name = vm1_info.get("name")
            ecs_page.assert_status(vm1_name)

            fip1 = ecs_page.ecs_bind_pub_ip(vm1_name, subnet=subnet_name)
            ecs_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤5: 从云外访问fip1(ping/ssh请求)，期望结果：可以ping通，可以ssh连接"):
            ssh_host.ping(fip1, connected=True)
            ssh_host.telnet(fip1, port=22, timeout=15)

        with allure_step_log(f"步骤6: 清理测试资源-虚机 {vm1_name}"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(vm1_name)
            ecs_page.ecs_delete(vm1_name, release_ip=True)
            ecs_page.assert_deleted(vm1_name)

        with allure_step_log(f"步骤7: 清理克隆出的安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(clone_name)
            sg_page.assert_deleted(clone_name)

    @allure.title("安全组规则-删除")
    def _test_sg_rule_delete(self, sg_page, sg):
        sg_name = sg
        with allure_step_log(f"步骤1: 在安全组 {sg_name} 中创建入口规则并删除"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg_name,
                protocol="选择常用协议",
                protocol_type="HTTP",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description="放行HTTP"
            )
            
            # 删除创建的入口规则
            sg_page.sg_rule_delete(sg_name, direction="入口")

    @allure.title("安全组规则-列表页快捷创建")
    def test_sg_rule_create_from_list(self, sg_page, sg):
        sg_name = sg
        protocol_type = "HTTPS"
        direction = "入口"
        
        with allure_step_log(f"步骤1: 在列表页直接为安全组 {sg_name} 创建入方向规则"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg_name,
                protocol="选择常用协议",
                protocol_type=protocol_type,
                direction=direction,
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description="列表页创建放行HTTPS",
                from_list=True
            )

        with allure_step_log(f"步骤2: 进入详情页，验证新创建的规则是否存在"):
            sg_page.goto_sg_detail(sg_name)
            # 通过描述定位刚创建的规则行
            target_row = sg_page.get_rows_by_text("列表页创建放行HTTPS").first
            # 验证各入参是否正确显示
            expect(target_row).to_contain_text(protocol_type)
            expect(target_row).to_contain_text(direction)
            expect(target_row).to_contain_text("0.0.0.0/0")
            expect(target_row).to_contain_text("IPv4")

    @allure.title("安全组规则-创建场景")
    @pytest.mark.parametrize("scenario", load_data("test_sg_rule_create_scenarios", "test_sg.yaml"))
    def test_sg_rule_create_scenarios(self, sg_page, sg, scenario):
        sg_name = sg

        allure.dynamic.title(f"安全组规则-创建场景（{scenario['desc']}）")
        with allure_step_log(f"步骤1: 为安全组 {sg_name} 创建规则: {scenario['desc']}"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg_name,
                protocol=scenario.get("protocol"),
                protocol_type=scenario.get("protocol_type"),
                protocol_code=scenario.get("protocol_code"),
                port_type=scenario.get("port_type"),
                port=scenario.get("port"),
                direction=scenario.get("direction"),
                remote_type=scenario.get("remote_type"),
                ip_version=scenario.get("ip_version"),
                remote_sg=scenario.get("remote_sg"),
                cidr=scenario.get("cidr"),
                description=scenario["desc"]
            )

        with allure_step_log(f"步骤2: 验证规则"):
            sg_page.goto_sg_detail(sg_name)
            target_row = sg_page.get_rows_by_text(scenario["desc"]).first
            expect(target_row).to_be_visible()
            row_data = sg_page.get_row_data_by_locator(target_row)
            # 验证方向
            direction_key = next((k for k in row_data.keys() if "方向" in k), None)
            if direction_key:
                assert scenario.get("direction") in row_data[direction_key], f"方向不匹配，期望: {scenario.get('direction')}, 实际: {row_data[direction_key]}"
                
            # 验证以太网类型
            eth_type_key = next((k for k in row_data.keys() if "以太网类型" in k), None)
            if eth_type_key:
                assert scenario.get("ip_version") in row_data[eth_type_key], f"以太网类型不匹配，期望: {scenario.get('ip_version')}, 实际: {row_data[eth_type_key]}"
                
            # 验证IP协议
            protocol_key = next((k for k in row_data.keys() if "IP协议" in k or "协议" in k), None)
            if protocol_key:
                p_type = scenario.get("protocol_type") or scenario.get("protocol_code")
                if p_type:
                    icmp_val = "icmpv6" if scenario.get("ip_version") == "IPv6" else "icmp"
                    # 定义协议显示映射字典，提升代码可读性
                    protocol_map = {
                        f"{scenario.get('protocol_code')}": "VRRP",
                        "所有ICMP协议": icmp_val,
                        "HTTP": "tcp", "HTTPS": "tcp", "MYSQL": "tcp", "定制TCP协议": "tcp",
                        "DNS": "udp", "定制UDP协议": "udp"
                    }
                    expected_p = protocol_map.get(p_type, p_type.lower())
                    assert expected_p in row_data[protocol_key], f"IP协议不匹配，期望: {expected_p}, 实际: {row_data[protocol_key]}"
                    
            # 验证端口范围
            port_key = next((k for k in row_data.keys() if "端口范围" in k), None)
            if port_key and scenario.get("port"):
                assert str(scenario.get("port")) in row_data[port_key], f"端口不匹配，期望: {scenario.get('port')}, 实际: {row_data[port_key]}"
                
            # 验证远端
            if scenario.get("remote_type") == "CIDR":
                remote_ip_key = next((k for k in row_data.keys() if "远端IP前缀" in k), None)
                if remote_ip_key:
                    assert scenario.get("cidr") in row_data[remote_ip_key], f"远端IP前缀不匹配，期望: {scenario.get('cidr')}, 实际: {row_data[remote_ip_key]}"
            elif scenario.get("remote_type") == "安全组":
                remote_sg_key = next((k for k in row_data.keys() if "远端安全组" in k), None)
                if remote_sg_key:
                    assert scenario.get("remote_sg") in row_data[remote_sg_key], f"远端安全组不匹配，期望: {scenario.get('remote_sg')}, 实际: {row_data[remote_sg_key]}"
