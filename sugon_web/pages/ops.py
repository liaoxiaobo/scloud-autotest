from playwright.sync_api import Page
from sugon_web.common.base import BasePage, submenu


class OpsPage(BasePage):
    def __init__(self, page: Page, env):
        super().__init__(page, env)

    # def goto_mfip_page(self):
    #     """导航到 MFIP 页面"""
    #     self.page.goto("https://172.22.3.140:30000/ops/#/sdn-mfip-list")
    #     self.page.get_by_text("网络设施").click()
    #     self.page.get_by_text("MFIP", exact=True).click()

    @submenu("MFIP")
    def mfip_create(self, project: str, network: str, ip: str):
        """创建 MFIP"""
        self.get_by_text("新建", exact=True).click()
        self.get_by_placeholder("请选择项目").click()
        self.get_by_title(project).click()
        self.get_by_placeholder("请选择网络").click()
        self.get_by_text(network).click()
        self.get_by_placeholder("请选择端口").click()
        self.get_by_text(ip, exact=True).click()
        self.get_by_text("确定").click()

    @submenu("MFIP")
    def mfip_delete(self, ip: str):
        """删除 MFIP"""
        self.click_dropdown_option(ip, "删除")
        self.dialog_confirm.click()


    @submenu("MFIP")
    def mfip_search(self, ip: str):
        """查询 MFIP"""
        self.get_by_role("textbox", name="请选择").nth(1).click()
        self.get_by_text("固定IP", exact=True).click()
        self.search(ip)