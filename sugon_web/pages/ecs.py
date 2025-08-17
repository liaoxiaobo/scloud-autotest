import re
from sugon_web.common.base import BasePage, submenu


class EcsPage(BasePage):

    def __init__(self, page, env):
        super().__init__(page, env)

    @submenu("弹性云服务器")
    def ecs_create(
            self, 
            name,
            cluster="Autotest",
            count=1,
            flavor="ecs.c6.large",
            image_source="xstor-test",
            os_version="centos7.9",
            os_arch="64位",
            image_name="xstor-test",
            disk_size=50,
            network="Autotest",
            subnet="Autotest(10.151.146.0/24)",
            login_pwd="sugon@20",
            vnc_pwd="sugon@20"
    ):
        """创建弹性云服务器
        
        Args:
            name: 服务器名称
            cluster: 集群名称，默认为"Autotest"
            count: 创建数量，默认为1
            flavor: 计算规格，默认为"ecs.c6.large"
            image_source: 镜像源，默认为"xstor-test"
            os_version: 操作系统版本，默认为"centos7.9"
            os_arch: 操作系统位数，默认为"64位"
            image_name: 镜像名称，默认为"xstor-test"
            disk_size: 磁盘大小（GB），默认为50
            network: 网络名称，默认为"Autotest"
            subnet: 子网名称，默认为"Autotest(10.151.146.0/24)"
            login_pwd: 登录密码，默认为"sugon@20"
            vnc_pwd: VNC密码，默认为"sugon@20"
        """
        self.btn_create.click()

        # 基本信息
        self._input_name.fill(name)
        self._select_cluster(cluster)
        self._set_count(count)
        self._select_flavor(flavor)

        # 镜像配置
        self._select_image_source(image_source)
        self._select_os_version(os_version)
        self._select_os_arch(os_arch)
        self._select_image(image_name)

        # 存储配置
        self._set_disk_size(disk_size)

        # 网络配置
        self._select_network(network)
        self._select_subnet(subnet)

        # 密码配置
        self._set_passwords(login_pwd, vnc_pwd)

        # 提交创建
        self.btn_submit.click()

    @property
    def _input_name(self):
        """服务器名称输入框"""
        return self.get_by_placeholder("请输入名称").first

    def _select_cluster(self, cluster):
        """选择集群"""
        self.get_by_placeholder("请选择集群").click()
        self.locator("ul").filter(has_text=re.compile(rf"^{cluster}$")).locator("span").click()

    def _set_count(self, count):
        """设置数量"""
        count_input = self.get_by_role("spinbutton").first
        count_input.click()
        count_input.fill(str(count))

    def _select_flavor(self, flavor):
        """选择计算规格"""
        self.get_by_text("选择计算规格").first.click()
        self.get_by_role("row", name=re.compile(flavor)).get_by_role("radio").click()
        self.dialog_confirm.click()

    def _select_image_source(self, source):
        """选择镜像源"""
        self.get_by_placeholder("请选择", exact=True).nth(2).click()
        self.get_by_text(source).click()

    def _select_os_version(self, version):
        """选择操作系统版本"""
        self.get_by_placeholder("请选择操作系统版本").click()
        self.get_by_text(version).click()

    def _select_os_arch(self, arch):
        """选择操作系统位数"""
        self.get_by_placeholder("请选择操作系统位数").click()
        self.get_by_text(arch).click()

    def _select_image(self, image):
        """选择镜像"""
        self.get_by_placeholder("请选择镜像").click()
        self.get_by_title(image).click()

    def _set_disk_size(self, size):
        """设置磁盘大小"""
        disk_input = self.get_by_role("spinbutton").nth(1)
        disk_input.click()
        disk_input.fill(str(size))

    def _select_network(self, network):
        """选择网络"""
        self.get_by_role("textbox", name="请选择网络").click()
        self.get_by_text(network, exact=True).nth(4).click()

    def _select_subnet(self, subnet):
        """选择子网"""
        self.get_by_role("textbox", name="请选择子网").click()
        self.get_by_text(subnet).nth(2).click()

    def _set_passwords(self, login_pwd, vnc_pwd):
        """设置登录密码和VNC密码"""
        # 登录密码
        self.get_by_placeholder("请输入密码").fill(login_pwd)
        self.locator("div").filter(has_text=re.compile(r"^确认登录密码$")).get_by_role("textbox").fill(login_pwd)

        # VNC密码
        self.get_by_placeholder("VNC密码最长为8位").fill(vnc_pwd)
        self.locator("div").filter(has_text=re.compile(r"^确认VNC密码$")).get_by_role("textbox").fill(vnc_pwd)

    @submenu("回收站")
    def ecs_delete(self, name):
        """删除弹性云服务器
        
        Args:
            name: 服务器名称
        """
        self.click_dropdown_option(name, "删除")
        self.dialog_confirm.click()