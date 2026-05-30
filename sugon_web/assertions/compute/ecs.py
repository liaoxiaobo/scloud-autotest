from time import sleep

from sugon_web.common.playwright import expect


class EcsAssertionMixin:
    """ECS 业务断言 Mixin。

    验证云服务器详情信息、镜像名称、可用性等。
    属于 L2 Business 层断言。
    """

    def assert_ecs_details_info(self, names, info_items: dict, tab: str = "详情", sub_tab: str = None):
        """验证云服务器详情页面中的信息

        Args:
            names: 云服务器名称
            tab: 页签名称
            sub_tab: 子页签名称
            info_items: 需要验证的信息项字典，格式为 {"信息项名称": "期望内容"}
                       例如: {"启动顺序": "3", "启动延迟时间(秒)": "20"}
        """
        logger = self.logger

        logger.info(f"验证云服务器 {names} 的 {tab} 页签信息")
        if isinstance(names, str):
            names = [names]
        for name in names:
            self.ecs_to_details(name)

            logger.info(f"点击 {tab} 页签")
            exact = False if tab == "安全组" or tab == "事件列表" else True
            if tab == "详情":
                sleep(2)
                self.wait_for_page_ready()
            else:
                self.get_by_role("tab", name=tab, exact=exact).click()
                if sub_tab:
                    self.locator("label").filter(has_text=sub_tab).click()
            # 逐个验证信息项
            for item_name, expected_content in info_items.items():
                if tab == "详情":
                    # 定位信息项
                    info_item = self.get_by_label(tab).get_by_text(item_name, exact=True)
                    # 获取信息项的值
                    _list = ["亲和组", "硬件密码加速", "CPU QoS 优先级", "CPU QoS 上限", "NUMA 绑定", "vNUMA拓扑",
                             "CPU独占", "VNC显卡类型", "CPU模式", "声卡类型", "FsAgent", "DingAgent"]
                    if item_name in _list:
                        info_value = info_item.locator("xpath=./following-sibling::*").first
                    else:
                        info_value = info_item.locator("xpath=../following-sibling::*").first
                    # 验证信息项的值是否包含期望内容
                    assert str(expected_content) in info_value.inner_text(), \
                        f"[FieldAssertion] ECS '{name}' | {tab}页签字段 '{item_name}' 不匹配 | " \
                        f"期望: 包含 '{expected_content}' | 实际: '{info_value.inner_text()}'"
                    logger.info(
                        f"验证成功: {tab}的{item_name}包含{str(expected_content)}, 实际内容: {info_value.inner_text()}")
                else:
                    expect(self.get_by_role("cell", name=item_name).locator("div")).to_be_visible()
                    assert expected_content in self.get_row_data(item_name).values(), \
                        f"[FieldAssertion] ECS '{name}' | {tab}页签字段 '{item_name}' 不匹配 | " \
                        f"期望: 包含 '{expected_content}' | 实际: '{self.get_row_data(item_name)}'"
            logger.info(f"云服务器 {tab} 详情页面信息验证成功")
            self.goto_submenu("弹性云服务器")

    def assert_ecs_tools_installed(self, name: str):
        """验证云服务器安装工具页面第一步操作是否完成"""
        expect(self.get_by_text("进入VNC控制台")).to_be_visible(timeout=30000)

    def assert_ecs_info(self, name: str, row_name: str, exception: str):
        """验证云服务器信息
        Args:
            name: 云服务器名称
            row_name: 验证参数
            exception: 验证内容
        """
        self.logger.info(f"验证{name}云服务器{row_name}: {exception}")
        row_data = self.get_row_data(name).get(row_name)
        assert exception in row_data, (
            f"[FieldAssertion] ECS '{name}' | 字段 '{row_name}' 不包含期望值 | "
            f"期望: 包含 '{exception}' | 实际: '{row_data}'"
        )

    def assert_ecs_info_not_contains(self, name: str, row_name: str, exception: str):
        """验证云服务器信息
        Args:
            name: 云服务器名称
            row_name: 验证参数
            exception: 验证内容
        """
        self.logger.info(f"验证{name}云服务器{row_name}: {exception}")
        row_data = self.get_row_data(name).get(row_name)
        assert exception not in row_data, (
            f"[FieldAssertion] ECS '{name}' | 字段 '{row_name}' 不应包含该值 | "
            f"期望: 不包含 '{exception}' | 实际: '{row_data}'"
        )

    def assert_image_name(self, name: str, image_name: str):
        """验证云服务器镜像名称是否匹配。

        Args:
            name: 云服务器名称。
            image_name: 期望的镜像名称。
        """
        self.logger.info(f"验证{name}服务器镜像名称: {image_name}")
        actual_image = self.get_row_data(name).get("镜像名称")
        assert actual_image == image_name, (
            f"[FieldAssertion] ECS '{name}' | 镜像名称不匹配 | "
            f"期望: '{image_name}' | 实际: '{actual_image}'"
        )

    def assert_ecs_enable(self, name: str, ssh_vm, timeout=120):
        """验证云服务器可用性
        Args:
            name: 云服务器名称
            ssh_vm: 云服务器ssh对象
        """
        logger = self.logger

        logger.info(f"验证{name}云服务器可用性")
        logger.info(f"验证云服务器{name} fs-agent状态为active (running)")
        self.wait_for_update(ssh_vm, "systemctl status fs-agent", "active (running)", timeout=timeout)
        stdout = ssh_vm.run("systemctl status fs-agent", return_rc=True)
        assert stdout.get("stdout").count("active (running)") \
               and stdout.get("rc") == 0, \
               f"[BackendAssertion] ECS '{name}' | fs-agent 状态 | 期望: active (running) | 实际: 未启动"

        logger.info(f"验证云服务器{name} ding-agent服务状态为启动")
        self.wait_for_update(ssh_vm, "ps -ef | grep ding", "ding-agent", timeout=timeout)
        stdout = ssh_vm.run("ps -ef | grep ding", return_rc=True)
        assert stdout.get("stdout").count("ding-agent") \
               and stdout.get("rc") == 0, \
               f"[BackendAssertion] ECS '{name}' | ding-agent 状态 | 期望: 运行中 | 实际: 未启动"

        logger.info(f"验证云服务器{name}能ping通 100.126.255.250")
        ssh_vm.ping("100.126.255.250")

        logger.info(f"验证云服务器{name}能 curl通http://169.254.169.254:80/openstack")
        stdout = ssh_vm.run("curl http://169.254.169.254:80/openstack", return_rc=True)
        assert stdout.get("stdout").count("latest") \
               and stdout.get("rc") == 0, \
               f"[BackendAssertion] ECS '{name}' | curl 元数据服务 | 期望: 包含 'latest' | 实际: 请求失败"
