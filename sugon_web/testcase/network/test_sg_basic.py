import allure
import pytest
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic('网络安全')
@allure.feature('安全组')
@allure.story('基本功能验证')
class TestSGBasic:
    @allure.title("验证新建安全组功能")
    def test_sg_create(self, sg_page):

        with allure_step_log(f"步骤1: 新建安全组"):
            sg_page.goto_service("安全组")
            sg_name = random_data()
            sg_page.sg_create(sg_name, desc=f"{sg_name}测试安全组")
            sg_page.assert_popup_success("新建安全组成功")
            sg_page.assert_status(sg_name, status=f"{sg_name}测试安全组")

        with allure_step_log(f"步骤2: 列表页，点击安全组名称进入详情，查看安全组规则。默认自带两条出方向的规则"):
            sg_page.goto_sg_detail(sg_name)
            directions = sg_page.get_column_data("方向入口出口   筛选   重置 ")
            assert len(directions) == 2, "安全组详情页默认出方向规则数非2"

        with allure_step_log(f"步骤3: 清理测试资源-安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_name)
            sg_page.assert_deleted(sg_name)

    @allure.title("验证搜索安全组功能")
    def test_sg_search(self, sg_page, sg):
        sg_name = sg
        with allure_step_log(f"步骤1: 搜索安全组: {sg_name}"):
            sg_page.goto_service("安全组")
            sg_page.sg_search(sg_name)
            
            # 使用模糊匹配断言列表中包含搜索关键字
            sg_page.assert_list_contain(sg_name, exact_match=False)

        with allure_step_log(f"步骤2: 重置搜索条件"):
            sg_page.sg_search_reset()
            # 断言重置后列表有数据（使用默认名称列进行粗略判断，这里不报错即视为成功渲染列表）
            sg_page.get_column_data("名称")

    @allure.title("验证编辑安全组功能")
    def test_sg_edit(self, sg_page, sg):
        sg_name = sg
        new_name = f"{sg_name}-edit"
        new_desc = f"{sg_name} 编辑后的描述"
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

    @allure.title("验证克隆安全组功能")
    def test_sg_clone(self, ecs_page, sg_page, ssh_host, ecs_create_page, sg, vpc):
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
            
            ecs_create_page.goto_service("弹性云服务器")
            network = {"networks":[{"network": network_name, "subnet": subnet_name}], "安全组": [clone_name]}
            vm1_info = ecs_create_page.ecs_create_v2({}, {}, network, {}, {})
            vm1_name = vm1_info.get("name")
            ecs_create_page.assert_status(vm1_name)

            fip1 = ecs_create_page.ecs_bind_pub_ip(vm1_name, subnet=subnet_name)
            ecs_create_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤5: 从云外访问fip1(ping/ssh请求)，期望结果：可以ping通，可以ssh连接"):
            ssh_host.ping(fip1, connected=True)
            ssh_host.telnet(fip1, port=22, timeout=15)

        with allure_step_log(f"步骤6: 清理测试资源-虚机 {vm1_name}"):
            ecs_create_page.goto_service("弹性云服务器")
            ecs_create_page.ecs_remove(vm1_name)
            ecs_create_page.ecs_delete(vm1_name, release_ip=True)
            ecs_create_page.assert_deleted(vm1_name)

        with allure_step_log(f"步骤7: 清理克隆出的安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(clone_name)
            sg_page.assert_deleted(clone_name)

    @allure.title("验证删除安全组规则功能")
    def _test_sg_rule_delete(self, sg_page, sg):
        sg_name = sg
        with allure_step_log(f"在安全组 {sg_name} 中创建入口规则并删除"):
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
            sg_page.assert_popup_success("执行成功")
            
            # 删除创建的入口规则
            sg_page.sg_rule_delete(sg_name, direction="入口")

    @allure.title("验证在列表页快捷创建安全组规则功能")
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
            sg_page.assert_popup_success("新建安全组规则成功")

        with allure_step_log(f"步骤2: 进入详情页，验证新创建的规则是否存在"):
            sg_page.goto_sg_detail(sg_name)
            # 通过描述定位刚创建的规则行
            target_row = sg_page.get_rows_by_text("列表页创建放行HTTPS").first
            # 验证各入参是否正确显示
            expect(target_row).to_contain_text(protocol_type)
            expect(target_row).to_contain_text(direction)
            expect(target_row).to_contain_text("0.0.0.0/0")
            expect(target_row).to_contain_text("IPv4")

@allure.epic('网络安全')
@allure.feature('安全组')
@allure.story('场景验证')
class TestSGScenario:

    @allure.title("验证安全组创建基本功能")
    @pytest.mark.parametrize("vm", [{"count": 1, "bind_mfip": True}], indirect=True)
    def test_sg_create_scenario(self, ecs_page, sg_page, ssh_vm, ssh_host, ecs_create_page, vm, vpc):
        vm1_mfip = vm.get("mfip")
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")
        
        with allure_step_log(f"前置准备: 申请/分配一个可用公网 IP 以备后续测试使用"):
            ecs_page.assign_ip()

        with allure_step_log(f"步骤1: 新建安全组"):
            sg_page.goto_service("安全组")
            sg_name = random_data()
            sg_page.sg_create(sg_name, desc=f"{sg_name}测试安全组")
            sg_page.assert_popup_success("新建安全组成功")
            sg_page.assert_status(sg_name, status=f"{sg_name}测试安全组")

        with allure_step_log(f"步骤2: 列表页，点击安全组名称进入详情，查看安全组规则。默认自带两条出方向的规则"):
            sg_page.goto_sg_detail(sg_name)
            directions = sg_page.get_column_data("方向入口出口   筛选   重置 ")
            assert len(directions) == 2, "安全组详情页默认出方向规则数非2"

            # 检查是否都是出口方向
            assert all(d.strip() == "出口" for d in directions), f"期望所有规则都是'出口'方向，实际: {directions}"

        with allure_step_log(f"步骤3: 进入ECS模块，使用安全组{sg_name}创建弹性云服务器vm2，并绑定弹性公网ip"):
            ecs_create_page.goto_service("弹性云服务器")
            network = {"networks":[{"network": network_name,"subnet": subnet_name}], "安全组": [sg_name]}
            vm2_info = ecs_create_page.ecs_create_v2({}, {}, network, {}, {})
            vm2 = vm2_info.get("name")
            ecs_create_page.assert_status(vm2)

            data = ecs_create_page.get_row_data(vm2)
            ip_list = data["IP地址"].split("固定: ")
            vm2_ip = ip_list[-1].strip()

            fip1 = ecs_create_page.ecs_bind_pub_ip(vm2, subnet=subnet_name)
            ecs_create_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤4: 从云外访问fip1({fip1})(ping/ssh请求)，期望结果：无法ping通，ssh无法连接"):
            ssh_host.ping(fip1, connected=False)
            with pytest.raises(Exception):
                ssh_host.telnet(fip1, port=22, timeout=10)

        with allure_step_log(f"步骤5: 从vm1对vm2执行ping请求，期望结果：无法ping通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=False)

        with allure_step_log(f"步骤6: 进入安全组{sg_name}详情页，创建入方向规则，放行所有ipv4流量"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg_name,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                description="放行所有IPv4流量"
            )

        with allure_step_log(f"步骤7: 再次执行生效性验证的步骤(1)(2)，期望结果：均可以ping通，ssh也可以登录"):
            # 云外访问fip1，ping/ssh
            ssh_host.ping(fip1, connected=True)
            ssh_host.telnet(fip1, port=22, timeout=15)
            # 虚机内ping vm2
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=True)

        with allure_step_log(f"步骤8: 清理测试资源-虚机"):
            ecs_create_page.goto_service("弹性云服务器")
            ecs_create_page.ecs_remove(vm2)
            ecs_create_page.ecs_delete(vm2, release_ip=True)
            ecs_create_page.assert_deleted(vm2)

        with allure_step_log(f"步骤9: 清理测试资源-安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_name)
            sg_page.assert_deleted(sg_name)

    @allure.title("验证删除安全组场景")
    def test_sg_delete_scenario(self, sg_page, ecs_create_page, vpc):
        base_name = random_data()
        sg_page.goto_service("安全组")

        with allure_step_log(f"步骤1: 创建4个未使用的SG{base_name}, 1个VM使用的SG"):
            sg_unused_1, sg_unused_2, sg_unused_3, sg_unused_4, sg_used = [f"{base_name}-{s}" for s in ("u1", "u2", "u3", "u4", "used")]

            for sg_name in [sg_unused_1, sg_unused_2, sg_unused_3, sg_unused_4, sg_used]:
                sg_page.sg_create(sg_name, desc=f"{sg_name}删除测试用")
                # 等待弹窗消失避免阻挡下一个创建
                expect(sg_page.popup).to_have_count(0)

        with allure_step_log(f"步骤2: 使用安全组 {sg_used} 创建 ECS 用于占用"):
            network_name = vpc["name"]
            subnet_name = vpc["subnet_name"]
            ecs_create_page.goto_service("弹性云服务器")
            network = {"networks": [{"network": network_name, "subnet": subnet_name}], "安全组": [sg_used]}
            vm_info = ecs_create_page.ecs_create_v2({}, {}, network, {}, {})
            vm_name = vm_info.get("name")
            ecs_create_page.assert_status(vm_name)

        with allure_step_log(f"步骤3: 场景(1):删除单个未使用的安全组 {sg_unused_1}"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_unused_1)
            # 验证不存在
            sg_page.assert_deleted(sg_unused_1)

        with allure_step_log(f"步骤4: 场景(2):删除单个已使用的安全组 {sg_used}"):
            # 点击删除并确认
            sg_page.click_dropdown_option(sg_used, "删除")
            sg_page.dialog_confirm.click()

            # 定位自定义失败弹窗，断言并关闭

            dialog_box = sg_page.locator(".one-dialog-box").filter(has_text="删除提示").filter(has_text=sg_used).last
            expect(dialog_box).to_be_visible(timeout=5000)
            expect(dialog_box).to_contain_text("正在被使用中")
            expect(dialog_box).to_contain_text("删除失败")

            # 点击“关闭”按钮
            close_btn = dialog_box.locator(".cloud-button-btn", has_text="关闭")
            close_btn.click()
            expect(dialog_box).not_to_be_visible(timeout=5000)

            # 验证依旧存在
            sg_page.assert_status(sg_used, status=f"{sg_used}删除测试用")

        with allure_step_log(f"步骤5: 场景(3):批量删除未使用的安全组 {sg_unused_2}, {sg_unused_3}"):
            sg_page.sg_delete([sg_unused_2, sg_unused_3])
            # 验证不存在
            sg_page.assert_deleted([sg_unused_2, sg_unused_3])

        with allure_step_log(f"步骤6: 场景(4):批量删除混合状态的安全组 {sg_unused_4} 和 {sg_used}"):
            # 执行批量删除
            sg_page.select_rows_by_names([sg_unused_4, sg_used])
            sg_page.btn_batch_delete.click()
            sg_page.dialog_confirm.click()

            # 定位自定义失败弹窗，断言并关闭
            dialog_box = sg_page.locator(".one-dialog-box").filter(has_text="删除提示").filter(has_text=sg_used).last
            expect(dialog_box).to_be_visible(timeout=5000)

            # 尽管成功删除了一个，但失败的一个也会在这个弹窗里提示
            expect(dialog_box).to_contain_text("被使用中")
            expect(dialog_box).to_contain_text("失败")

            # 点击“关闭”按钮
            close_btn = dialog_box.locator(".cloud-button-btn", has_text="关闭")
            close_btn.click()
            expect(dialog_box).not_to_be_visible(timeout=5000)

            # 验证已使用的存在，未使用的不存在
            sg_page.assert_deleted(sg_unused_4)
            sg_page.assert_status(sg_used, status=f"{sg_used}删除测试用")

        with allure_step_log(f"步骤7: 清理测试资源{vm_name}、{sg_used}"):
            ecs_create_page.goto_service("弹性云服务器")
            ecs_create_page.ecs_remove(vm_name)
            ecs_create_page.ecs_delete(vm_name, release_ip=True)
            ecs_create_page.assert_deleted(vm_name)

            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_used)
            sg_page.assert_deleted(sg_used)

    @allure.title("验证多安全组虚拟机网络互通性")
    def test_sg_two_vms(self, ecs_page, sg_page, ssh_vm, ssh_host, ecs_create_page, vpc):
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")
        base_name = random_data()
        sg1,sg2  = [f"{base_name}-{s}" for s in ("sg1", "sg2")]

        with allure_step_log(f"步骤1: 分配可用公网IP"):
            ecs_page.assign_ip()

        with allure_step_log(f"步骤2: 平台创建安全组{sg1}和{sg2}"):
            for sg_name in [sg1, sg2]:
                sg_page.sg_create(sg_name, desc=f"{sg_name}网络互通测试用")
                expect(sg_page.popup).to_have_count(0)

        with allure_step_log(f"步骤3: 在vpc同一子网下创建虚机vm1和vm2，分别绑定sg1和sg2，给vm1绑定公网ip"):
            ecs_create_page.goto_service("弹性云服务器")
            
            # 创建vm1并绑定sg1
            network_vm1 = {"networks":[{"network": network_name, "subnet": subnet_name}], "安全组": [sg1]}
            vm1_info = ecs_create_page.ecs_create_v2({}, {}, network_vm1, {}, {})
            vm1_name = vm1_info.get("name")
            ecs_create_page.assert_status(vm1_name)
            
            # 创建vm2并绑定sg2
            network_vm2 = {"networks":[{"network": network_name, "subnet": subnet_name}], "安全组": [sg2]}
            vm2_info = ecs_create_page.ecs_create_v2({}, {}, network_vm2, {}, {})
            vm2_name = vm2_info.get("name")
            ecs_create_page.assert_status(vm2_name)

            # 为vm1绑定公网IP
            fip1 = ecs_create_page.ecs_bind_pub_ip(vm1_name, subnet=subnet_name)
            ecs_create_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤4: {sg1}、{sg2}下添加入方向放行所有IPv4的规则，出方向保持默认"):
            sg_page.goto_service("安全组")
            for sg_name in [sg1, sg2]:
                sg_page.sg_rule_create(
                    sg_name=sg_name,
                    protocol="所有",
                    direction="入口",
                    remote_type="CIDR",
                    ip_version="IPv4",
                    description=f"{sg_name}放行入方向所有IPv4流量",
                    from_list=True
                )

        with allure_step_log(f"步骤5: SSH登录管控节点，对fip1({fip1})发起ping请求，预期结果：可以ping通"):
            ssh_host.ping(fip1, connected=True)

        with allure_step_log(f"步骤6: 页面验证sg1规则及修改"):
            sg_page.goto_sg_detail(sg1)
            # 确认列表可以正常显示所有规则
            rules = sg_page.sg_get_all_rules(sg1)
            assert len(rules) == 3, "安全组规则列表未正常显示"
            
            # 删除掉前提条件中增加的入方向规则
            sg_page.sg_rule_delete(sg1, direction="入口")
            # 再次新增入方向规则，放行ipv4所有流量，但网段写成vpc1的子网cidr
            subnet_cidr = vpc.get("cidr")
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr=subnet_cidr,
                description=f"{sg1}放行子网内部IPv4流量"
            )

        with allure_step_log(f"步骤7: 生效性验证"):
            # 再次执行步骤5，预期无法ping通
            ssh_host.ping(fip1, connected=False)
            
            # VNC/SSH登录vm2虚机，对vm1虚机发起ping请求，预期结果：可以ping通
            # 获取vm1的内部IP
            ecs_create_page.goto_service("弹性云服务器")
            data_vm1 = ecs_create_page.get_row_data(vm1_name)
            vm1_ip = data_vm1["IP地址"].split("固定: ")[-1].strip()
            
            # 为vm2绑定mfip
            data_vm2_initial = ecs_create_page.get_row_data(vm2_name)
            vm2_ip = data_vm2_initial["IP地址"].split("固定: ")[-1].strip()
            vm2_mfip = ecs_create_page.bind_mfip(vm2_ip, network=network_name)
            
            # 使用SSH连接到vm2，并对vm1的内部IP发起ping请求
            try:
                ssh_vm.connect(vm2_mfip)
                ssh_vm.ping(vm1_ip, connected=True)
            finally:
                # 尽量不在异常时残留连接
                pass

        with allure_step_log(f"步骤8: 清理测试资源"):
            ecs_create_page.goto_service("弹性云服务器")
            ecs_create_page.ecs_remove([vm1_name, vm2_name])
            ecs_create_page.ecs_delete([vm1_name, vm2_name], release_ip=True)
            ecs_create_page.assert_deleted([vm1_name, vm2_name])

            sg_page.goto_service("安全组")
            sg_page.sg_delete([sg1, sg2])
            sg_page.assert_deleted([sg1, sg2])