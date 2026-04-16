import allure
import pytest
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data

@allure.epic('网络服务')
@allure.feature('网络安全-安全组')
@allure.story('场景验证')
class TestSGScenario:

    @allure.title("验证安全组创建基本功能")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "bind_mfip": True}], indirect=True)
    def test_sg_create_scenario(self, eip, ecs_page, sg_page, ssh_vm, ssh_host, vm, vpc):
        vm1_mfip = vm.get("mfip")
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")

        with allure_step_log(f"前置准备: 使用 fixture 预分配的公网 IP {eip} 供后续绑定使用"):
            assert eip, "未获取到可用公网IP"

        with allure_step_log(f"步骤1: 新建安全组"):
            sg_page.goto_service("安全组")
            sg_name = random_data()
            sg_page.sg_create(sg_name, desc=f"{sg_name}测试安全组")
            sg_page.assert_status(sg_name, status=f"{sg_name}测试安全组")

        with allure_step_log(f"步骤2: 列表页，点击安全组名称进入详情，查看安全组规则。默认自带两条出方向的规则"):
            sg_page.goto_sg_detail(sg_name)
            directions = sg_page.get_column_data("方向入口出口   筛选   重置 ")
            assert len(directions) == 2, "安全组详情页默认出方向规则数非2"

            # 检查是否都是出口方向
            assert all(d.strip() == "出口" for d in directions), f"期望所有规则都是'出口'方向，实际: {directions}"

        with allure_step_log(f"步骤3: 进入ECS模块，使用安全组{sg_name}创建弹性云服务器vm2，并绑定弹性公网ip"):
            ecs_page.goto_service("弹性云服务器")
            network = {"networks":[{"network": network_name,"subnet": subnet_name}], "security_groups": [sg_name]}
            vm2_info = ecs_page.ecs_create({}, {}, network, {}, {})
            vm2 = vm2_info.get("name")
            ecs_page.assert_status(vm2)

            data = ecs_page.get_row_data(vm2)
            ip_list = data["IP地址"].split("固定: ")
            vm2_ip = ip_list[-1].strip()

            fip1 = ecs_page.ecs_bind_pub_ip(vm2, subnet=subnet_name)
            ecs_page.assert_popup_success("执行成功")

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
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(vm2)
            ecs_page.ecs_delete(vm2, release_ip=True)
            ecs_page.assert_deleted(vm2)

        with allure_step_log(f"步骤9: 清理测试资源-安全组"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_name)
            sg_page.assert_deleted(sg_name)

    @allure.title("验证删除安全组场景")
    def test_sg_delete_scenario(self, sg_page, ecs_page, vpc):
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
            ecs_page.goto_service("弹性云服务器")
            network = {"networks": [{"network": network_name, "subnet": subnet_name}], "security_groups": [sg_used]}
            vm_info = ecs_page.ecs_create({}, {}, network, {}, {})
            vm_name = vm_info.get("name")
            ecs_page.assert_status(vm_name)

        with allure_step_log(f"步骤3: 场景(1):删除单个未使用的安全组 {sg_unused_1}"):
            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_unused_1)
            # 验证不存在
            sg_page.assert_deleted(sg_unused_1)

        with allure_step_log(f"步骤4: 场景(2):删除单个已使用的安全组 {sg_used}"):
            # 点击删除并确认
            sg_page.click_action(sg_used, "删除")
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
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(vm_name)
            ecs_page.ecs_delete(vm_name, release_ip=True)
            ecs_page.assert_deleted(vm_name)

            sg_page.goto_service("安全组")
            sg_page.sg_delete(sg_used)
            sg_page.assert_deleted(sg_used)

    @allure.title("验证入方向规则-cidr类型")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_sg_two_vms(self, eip, sg, sg_page, ssh_vm, ssh_host, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        vm2 = vm["vms"][1]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")

        with allure_step_log(f"步骤1: 为虚机 {vm1['name']} 绑定公网IP"):
            assert eip, "未获取到可用公网IP"
            fip1 = ecs_page.ecs_bind_pub_ip(vm1["name"], subnet=subnet_name)
            ecs_page.assert_popup_success("执行成功")

        with allure_step_log(f"步骤2: {sg1}、{sg2}下添加入方向放行所有IPv4的规则，出方向保持默认"):
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

        with allure_step_log(f"步骤3: SSH登录管控节点，对fip1({fip1})发起ping请求，预期结果：可以ping通"):
            ssh_host.ping(fip1, connected=True)

        with allure_step_log(f"步骤4: 页面验证sg1规则及修改"):
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

        with allure_step_log(f"步骤5: 生效性验证"):
            # 再次执行步骤2，预期无法ping通
            ssh_host.ping(fip1, connected=False)

            # VNC/SSH登录vm2虚机，对vm1虚机发起ping请求，预期结果：可以ping通
            vm2_mfip = ecs_page.bind_mfip(vm2["ip"], network=network_name)

            # 使用SSH连接到vm2，并对vm1的内部IP发起ping请求
            try:
                ssh_vm.connect(vm2_mfip)
                ssh_vm.ping(vm1["ip"], connected=True)
            finally:
                # 尽量不在异常时残留连接
                pass

    @allure.title("创建入方向规则-远程安全组类型")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_sg_inter_binding(self, eip, sg, sg_page, ssh_vm, ssh_host, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        vm2 = vm["vms"][1]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")

        with allure_step_log(f"步骤1: sg2({sg2})放行所有IPv4；sg1({sg1})保持默认"):
            sg_page.goto_service("安全组")
            # sg2 添加入方向放行所有
            sg_page.sg_rule_create(
                sg_name=sg2,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description=f"{sg2}初始化规则",
                from_list=True
            )

        with allure_step_log(f"步骤2: 进入sg1({sg1})详情页，验证规则列表显示"):
            sg_page.goto_sg_detail(sg1)
            rules = sg_page.sg_get_all_rules()
            # 默认两条出口规则
            assert len(rules) == 2, f"sg1 默认规则数量非2，实际: {len(rules)}"
            assert all(r["方向"] == "出口" for r in rules), "sg1 默认规则方向非全部出口"

        with allure_step_log(f"步骤3: 为sg1({sg1})新增入方向规则，放行IPv4所有流量，远程选择安全组sg2({sg2})"):
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="入口",
                remote_type="安全组",
                ip_version="IPv4",
                remote_sg=sg2,
                description=f"放行来自{sg2}的流量"
            )

        with allure_step_log("步骤4: SSH登录管控节点，对fip1发起ping请求，预期结果：无法ping通"):
            # 给vm1绑定公网IP
            ecs_page.goto_service("弹性云服务器")
            assert eip, "未获取到可用公网IP"
            fip1 = ecs_page.ecs_bind_pub_ip(vm1["name"], subnet=subnet_name)

            ssh_host.ping(fip1, connected=False)

        with allure_step_log("步骤5: 登录vm2虚机，对vm1虚机发起ping请求，预期结果：可以ping通"):
            # 为vm2绑定mfip用于管理执行
            vm2_mfip = ecs_page.bind_mfip(vm2["ip"], network=network_name)

            ssh_vm.connect(vm2_mfip)
            ssh_vm.ping(vm1["ip"], connected=True)

        with allure_step_log(f"步骤6: 更新sg1({sg1})规则。删除跨组规则，改为放行所有IPv4流量(CIDR空)"):
            sg_page.goto_service("安全组")
            sg_page.goto_sg_detail(sg1)
            # 删除步骤2创建的入方向规则
            sg_page.sg_rule_delete(sg1, direction="入口")

            # 新增 CIDR 为空的规则
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="",  # CIDR 保持为空
                description="放行所有CIDR流量"
            )

        with allure_step_log("步骤7: SSH登录管控节点，对fip1发起ping请求，预期结果：可以ping通"):
            ssh_host.ping(fip1, connected=True)

            # 使用SSH连接到vm2，并对vm1的内部IP发起ping请求
            try:
                ssh_vm.connect(vm2_mfip)
                ssh_vm.ping(vm1["ip"], connected=True)
            finally:
                # 尽量不在异常时残留连接
                pass

    @allure.title("验证安全组规则添加与删除后的连通性")
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
    def test_sg_rule_visibility(self, eip, sg, sg_page, ssh_host, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        sg1 = vm["sgs"][0]
        subnet_name = vpc.get("subnet_name")

        with allure_step_log(f"步骤1: sg1({sg1})下添加入方向放行所有ipv4的规则"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description="放行入方向所有IPv4流量",
                from_list=True
            )

        with allure_step_log(f"步骤2: 进入sg1详情页，安全组规则tab页，确认列表可以正常显示所有规则"):
            sg_page.goto_sg_detail(sg1)
            rules = sg_page.sg_get_all_rules()
            # 默认2条出口 + 1条新加入口 = 3条
            assert len(rules) == 3, f"sg1 规则数量非3，实际: {len(rules)}"

            directions = [r["方向"] for r in rules]
            assert "入口" in directions, "sg1 规则列表未包含入口规则"
            assert "出口" in directions, "sg1 规则列表未包含出口规则"

        with allure_step_log("步骤3: SSH登录管控节点，对fip1发起ping请求，预期结果：可以ping通"):
            # 给vm1绑定公网IP (FIP)
            ecs_page.goto_service("弹性云服务器")
            assert eip, "未获取到可用公网IP"
            fip1 = ecs_page.ecs_bind_pub_ip(vm1["name"], subnet=subnet_name)
            ecs_page.assert_popup_success("执行成功")

            ssh_host.ping(fip1, connected=True)

        with allure_step_log("步骤4: 进入sg1详情页，删除掉步骤0中增加的入方向规则"):
            sg_page.goto_service("安全组")
            sg_page.goto_sg_detail(sg1)
            # 删除方向为“入口”的规则
            sg_page.sg_rule_delete(sg1, direction="入口")
            # 确认删除成功弹窗

        with allure_step_log("步骤5: SSH登录管控节点，对fip1发起ping请求，预期结果：无法ping通"):
            ssh_host.ping(fip1, connected=False)

    @allure.title("验证出方向规则-cidr类型")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_sg_egress_rule_logic(self, sg, sg_page, ssh_vm, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        vm2 = vm["vms"][1]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")

        with allure_step_log(f"步骤1: {sg1}、{sg2}下添加入方向放行所有ipv4的规则"):
            sg_page.goto_service("安全组")
            for sg_name in [sg1, sg2]:
                sg_page.sg_rule_create(
                    sg_name=sg_name,
                    protocol="所有",
                    direction="入口",
                    remote_type="CIDR",
                    ip_version="IPv4",
                    cidr="0.0.0.0/0",
                    description="放行入方向所有IPv4流量",
                    from_list=True
                )

        with allure_step_log(f"步骤2: VNC登录vm1虚机，对vm2发起ping请求，预期结果：可以ping通"):
            vm1_mfip = ecs_page.bind_mfip(vm1["ip"], network=network_name)
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=True)

        with allure_step_log(f"步骤3: 进入sg1详情页，确认列表可以正常显示所有规则"):
            sg_page.goto_service("安全组")
            sg_page.goto_sg_detail(sg1)
            rules = sg_page.sg_get_all_rules()
            # 默认2条出口 + 1条新加入口 = 3条
            assert len(rules) == 3, f"sg1 规则数量非3，实际: {len(rules)}"

        with allure_step_log(f"步骤4: 删除sg1下所有的出方向规则"):
            # 取出口规则数量
            egress_rules = [r for r in rules if r["方向"] == "出口"]
            for _ in range(len(egress_rules)):
                sg_page.sg_rule_delete(sg1, direction="出口")

        with allure_step_log(f"步骤5: 再次新增出方向规则, 放行ipv4所有流量, 但网段写成非vpc1的子网cidr"):
            # 使用一个无关的CIDR
            dummy_cidr = "172.172.172.0/24" if "172.172.172" not in vpc["cidr"] else "173.173.173.0/24"
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="出口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr=dummy_cidr,
                description="放行非业务子网的出口流量"
            )

        with allure_step_log(f"步骤6: vm1再次ping vm2, 预期无法ping通"):
            # 刷新连接或重新执行
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=False)

        with allure_step_log(f"步骤7: 登录vm2, ping vm1, 预期结果：可以ping通"):
            vm2_mfip = ecs_page.bind_mfip(vm2["ip"], network=network_name)
            ssh_vm.connect(vm2_mfip)
            ssh_vm.ping(vm1["ip"], connected=True)

    @allure.title("验证出方向规则-远程安全组类型")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_sg_egress_inter_binding(self, sg, sg_page, ssh_vm, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        vm2 = vm["vms"][1]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")

        with allure_step_log(f"步骤1: {sg1}、{sg2}下添加入方向放行所有ipv4的规则"):
            sg_page.goto_service("安全组")
            for sg_name in [sg1, sg2]:
                sg_page.sg_rule_create(
                    sg_name=sg_name,
                    protocol="所有",
                    direction="入口",
                    remote_type="CIDR",
                    ip_version="IPv4",
                    cidr="0.0.0.0/0",
                    description="放行入方向所有IPv4流量",
                    from_list=True
                )

        with allure_step_log(f"步骤2: 删除{sg1}下所有的出方向规则"):
            sg_page.goto_sg_detail(sg1)
            # 获取当前规则并过滤出出口规则
            rules = sg_page.sg_get_all_rules()
            egress_rules = [r for r in rules if r["方向"] == "出口"]
            for _ in range(len(egress_rules)):
                sg_page.sg_rule_delete(sg1, direction="出口")

        with allure_step_log(f"步骤3: 新增出方向规则，放行ipv4所有流量，但远程字段选择安全组default（非sg2）"):
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="出口",
                remote_type="安全组",
                ip_version="IPv4",
                remote_sg="default",
                description="出方向绑定非对端安全组"
            )

        with allure_step_log(f"步骤4: VNC登录vm1虚机，对vm2虚机发起ping请求，预期结果：无法ping通"):
            vm1_mfip = ecs_page.bind_mfip(vm1["ip"], network=network_name)
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=False)

        with allure_step_log(f"步骤5: 进入sg1详情页，删除原有出方向规则，新增一条出方向规则，远程选择安全组sg2"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_delete_all_by_direction(sg1, "出口")

            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="出口",
                remote_type="安全组",
                ip_version="IPv4",
                remote_sg=sg2,
                description=f"出方向绑定对端安全组{sg2}"
            )

        with allure_step_log(f"步骤6: VNC登录vm1虚机，对vm2虚机发起ping请求，预期结果：可以ping通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=True)

        with allure_step_log(f"步骤7: 进入sg1详情页，删除原有出方向规则，新增一条出方向规则，远程字段修改为CIDR，网段保持为空"):
            sg_page.goto_service("安全组")
            sg_page.goto_sg_detail(sg1)
            sg_page.sg_rule_delete(sg1, direction="出口")

            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="出口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="",  # CIDR保持为空，代表所有IPv4
                description="出方向放行所有CIDR"
            )

        with allure_step_log(f"步骤8: VNC登录vm1虚机，对vm2虚机发起ping请求，预期结果：可以ping通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=True)

    @allure.title("验证出方向规则-默认规则删除")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 2}}], indirect=True)
    def test_sg_default_egress_deletion(self, sg, sg_page, ssh_vm, ecs_page, vpc, vm):
        vm1 = vm["vms"][0]
        vm2 = vm["vms"][1]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")

        with allure_step_log(f"步骤1: {sg1}、{sg2}下添加入方向放行所有ipv4的规则"):
            sg_page.goto_service("安全组")
            for sg_name in [sg1, sg2]:
                sg_page.sg_rule_create(
                    sg_name=sg_name,
                    protocol="所有",
                    direction="入口",
                    remote_type="CIDR",
                    ip_version="IPv4",
                    cidr="0.0.0.0/0",
                    description="放行入方向所有IPv4流量",
                    from_list=True
                )

        with allure_step_log(f"步骤2: vm1 ping vm2, 预期可以ping通"):
            vm1_mfip = ecs_page.bind_mfip(vm1["ip"], network=network_name)
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=True)

        with allure_step_log(f"步骤3: 删除掉{sg1}安全下出方向规则"):
            sg_page.goto_service("安全组")
            sg_page.goto_sg_detail(sg1)
            # 获取当前所有规则，过滤出出口规则进行删除
            rules = sg_page.sg_get_all_rules()
            egress_rules = [r for r in rules if r["方向"] == "出口"]
            for _ in range(len(egress_rules)):
                sg_page.sg_rule_delete(sg1, direction="出口")

        with allure_step_log(f"步骤4: vm1 ping vm2, 预期无法ping通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2["ip"], connected=False)

    @allure.title("验证云服务器详情页自定义安全组规则绑定与生效性")
    @pytest.mark.parametrize("sg", [2], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}}], indirect=True)
    def test_sg_vm_binding_connectivity(self, sg, ecs_page, sg_page, ssh_vm, vpc, vm):
        vm1 = vm["vms"][0]
        sg1, sg2 = vm["sgs"]
        network_name = vpc.get("name")
        subnet_name = vpc.get("subnet_name")

        with allure_step_log(f"步骤1: sg1({sg1})放行所有IPv4"):
            sg_page.goto_service("安全组")
            sg_page.sg_rule_create(
                sg_name=sg1,
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                cidr="0.0.0.0/0",
                description="放行入方向所有IPv4流量",
                from_list=True
            )

        with allure_step_log(f"步骤2: 使用vm1同一vpc创建虚机vm2，并绑定安全组sg2"):
            ecs_page.goto_service("弹性云服务器")
            network_vm1 = {"networks": [{"network": network_name, "subnet": subnet_name}], "security_groups": [sg2]}
            vm1_info = ecs_page.ecs_create({"name": f"{random_data()}-vm2"}, {}, network_vm1, {}, {})
            vm2_name = vm1_info.get("name")
            ecs_page.assert_status(vm2_name)
            vm2_ip = ecs_page.get_row_data(vm2_name)["IP地址"].split("固定: ")[1].strip()

        with allure_step_log(f"步骤3: 进入虚机vm2详情页，验证安全组信息"):
            ecs_page.ecs_to_sg_tab(vm2_name)
            # 验证显示绑定 sg1
            expect(ecs_page.get_by_text(sg2, exact=True)).to_be_visible()

        with allure_step_log(f"步骤4: vm1 ping vm2,预期无法ping通"):
            vm1_mfip = ecs_page.bind_mfip(vm1["ip"], network=network_name)
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=False)

        with allure_step_log(f"步骤5: 在vm2的安全组页签下，创建入方向规则，放行ipv4所有流量"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_to_sg_tab(vm2_name)
            # 在自定义安全组下创建规则
            ecs_page.ecs_create_custom_sg_rule(
                protocol="所有",
                direction="入口",
                remote_type="CIDR",
                ip_version="IPv4",
                description="详情页创建自定义规则"
            )

        with allure_step_log(f"步骤6: 再次从vm1对vm2发起ping请求，预期：可以ping通"):
            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=True)

        with allure_step_log(f"步骤7: 删除刚才创建的入方向规则，验证不通"):
            # 在详情页中删除
            ecs_page.ecs_delete_custom_sg_rule(description="详情页创建自定义规则")

            # 记录此时如果不通需要一些时间生效
            ecs_page.page.wait_for_timeout(2000)

            ssh_vm.connect(vm1_mfip)
            ssh_vm.ping(vm2_ip, connected=False)

        with allure_step_log("清理资源: 删除手动创建的 vm2"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.ecs_remove(vm2_name)
            ecs_page.ecs_delete(vm2_name, release_ip=True)
            ecs_page.assert_deleted(vm2_name)

    @allure.title("验证云服务器详情页自定义安全组页面功能")
    def test_sg_vm_detail_management(self, ecs_page, sg_page, vpc):
        base_name = random_data()
        sg1, sg2, sg3 = [f"{base_name}-sg{_}" for _ in range(3)]
        
        with allure_step_log(f"步骤1: 创建安全组 {sg1}, {sg2}, {sg3}"):
            sg_page.goto_service("安全组")
            sg_page.sg_create(sg1, desc="测试虚机详情页管理安全组")
            sg_page.sg_rule_create(sg1, direction="入口", remote_type="CIDR", from_list=True)
            
            # 创建额外的安全组用于多选测试
            [sg_page.sg_create(sg, desc=f"{sg}多选测试") for sg in [sg2, sg3]]

        with allure_step_log(f"步骤2: 使用安全组 {sg1} 创建虚机 vm1"):
            network_name = vpc.get("name")
            subnet_name = vpc.get("subnet_name")
            ecs_page.goto_service("弹性云服务器")
            network = {"networks": [{"network": network_name, "subnet": subnet_name}], "security_groups": [sg1]}
            vm_info = ecs_page.ecs_create({}, {}, network, {}, {})
            vm_name = vm_info.get("name")
            ecs_page.assert_status(vm_name)

        try:
            with allure_step_log(f"步骤3: 进入虚机详情安全组tab，验证初始状态"):
                # 验证 sg1 在绑定列表中
                ecs_page.ecs_to_sg_tab(vm_name)
                bound_sgs = ecs_page.ecs_get_bound_security_groups()
                assert any(sg1 in s for s in bound_sgs), f"期望 {sg1} 在绑定列表中, 实际: {bound_sgs}"
                
                # 验证自定义规则下为空
                ecs_page.ecs_to_sg_tab(vm_name)
                protocol_header = next((h for h in ecs_page.table_headers if "协议" in h), "协议")
                rules = ecs_page.get_column_data(protocol_header)
                assert len(rules) == 0, f"期望初始自定义规则为空, 实际: {rules}"

                # 验证 sg1 下规则显示正确
                ecs_page.ecs_to_sg_tab(vm_name, sub_tab=sg1)
                protocol_header = next((h for h in ecs_page.table_headers if "协议" in h), "协议")
                rules = ecs_page.get_column_data(protocol_header)
                assert any("any" in r for r in rules), f"sg1 规则显示不正确, 实际: {rules}"

            with allure_step_log(f"步骤4: 点击设置安全组按钮，选择多个安全组 {sg2}, {sg3}"):
                ecs_page.ecs_set_security_groups([sg2, sg3], bind=True)
                # 验证绑定成功
                bound_sgs = ecs_page.ecs_get_bound_security_groups()
                assert any(sg2 in s for s in bound_sgs), f"sg2 绑定验证失败: {bound_sgs}"
                assert any(sg3 in s for s in bound_sgs), f"sg3 绑定验证失败: {bound_sgs}"

            with allure_step_log(f"步骤5: 取消选中安全组 {sg2}, {sg3}"):
                ecs_page.ecs_set_security_groups([sg2, sg3], bind=False)
                # 验证取消成功
                bound_sgs = ecs_page.ecs_get_bound_security_groups()
                assert not any(sg2 in s for s in bound_sgs), f"sg2 解绑验证失败: {bound_sgs}"
                assert not any(sg3 in s for s in bound_sgs), f"sg3 解绑验证失败: {bound_sgs}"

            with allure_step_log(f"步骤6: 自定义安全组下创建规则并验证"):
                ecs_page.ecs_to_sg_tab(vm_name)
                desc = f"{vm_name}-自定义安全组"
                ecs_page.ecs_create_custom_sg_rule(protocol="所有", direction="入口", description=desc)
                # 获取规则列表并断言
                rules = ecs_page.get_row_data(desc)
                assert desc in rules.get("描述", ""), f"自定义安全组创建规则验证失败: {rules}"

            with allure_step_log(f"步骤7: 验证安全组列表不显示该自定义安全组"):
                sg_page.goto_service("安全组")
                # 自定义安全组不搜素到
                sg_page.sg_search("自定义安全组")
                names = sg_page.get_column_data("名称")
                assert len(names) == 0, f"在列表中发现了意外的自定义安全组: {names}"

        finally:
            with allure_step_log("步骤8: 删除虚机和安全组"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.ecs_remove(vm_name)
                ecs_page.ecs_delete(vm_name, release_ip=True)
                ecs_page.assert_deleted(vm_name, refresh=True)

                sg_page.goto_service("安全组")
                sg_page.sg_delete([sg1, sg2, sg3])