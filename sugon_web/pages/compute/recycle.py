from sugon_web.common.base import submenu
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger


class RecyclePage(OpsPage):

    @submenu("回收站")
    def ecs_delete(self, names, secure=False, delete_volume: bool = False, release_ip: bool = False):
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            delete_option = "安全删除" if secure else "删除"
            self.click_action(names, delete_option)
        if delete_volume:
            self.locator("label").filter(has_text="删除云服务器挂载的数据盘").locator("span").nth(1).click()
            logger.info(f"已选择删除云服务器{names}挂载的数据盘")
        if release_ip:
            self.locator("label").filter(has_text="释放云服务器绑定的公网IP").locator("span").nth(1).click()
            logger.info(f"已选择释放云服务器{names}绑定的公网IP")
        self.dialog_confirm.click()

    @submenu("回收站")
    def ecs_recover_delete(self, name: str, delete_volume: bool = False, release_ip: bool = False):
        logger.info(f"开始安全删除云服务器: {name}")
        self.click_action(name, "删除")
        if delete_volume:
            self.locator("label").filter(has_text="删除云服务器挂载的数据盘").locator("span").nth(1).click()
            logger.info(f"已选择删除云服务器{name}挂载的数据盘")
        if release_ip:
            self.locator("label").filter(has_text="释放云服务器绑定的公网IP").locator("span").nth(1).click()
            logger.info(f"已选择释放云服务器{name}绑定的公网IP")
        self.get_by_label("删除", exact=True).get_by_text("确定").click()
        logger.info(f"云服务器安全删除请求已提交: {name}")

    @submenu("回收站")
    def ecs_recover_batch_delete(self, names, secure=False):
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            delete_option = "安全删除" if secure else "删除"
            self.click_action(names, delete_option)
        self.dialog_confirm.click()
        logger.info(f"{names}删除请求已提交")
        self.wait_for_page_ready()
