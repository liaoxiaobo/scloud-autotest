import re

from sugon_web.common.base import submenu
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger


class AffinityGroupPage(OpsPage):

    @submenu("亲和组")
    def ecs_create_affinity_group(self, name: str, policy="亲和"):
        logger.info(f"开始创建亲和组: {name}, 策略: {policy}")
        self.btn_create.click()
        self.get_by_placeholder("请输入亲和组名称").fill(name)
        self.get_by_placeholder("请选择策略").click()
        self.locator("li").filter(has_text=re.compile(rf"^{re.escape(policy)}$")).click()
        self.dialog_confirm.click()
        logger.info(f"亲和组创建请求已提交: {name}, 策略: {policy}")

    @submenu("亲和组")
    def ecs_delete_affinity_group(self, names):
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.get_row_by_name(names).get_by_text("删除", exact=True).click()
        self.dialog_confirm.click()
        logger.info("已提交亲和组删除请求")

    @submenu("弹性云服务器")
    def ecs_bind_unbind_group(self, names, operation: str, group_name: str):
        if isinstance(names, str):
            names = [names]
        for name in names:
            self.ecs_bind_unbind_affinity_group(name, operation, group_name)
            self.assert_popup_success(f"{name}实例{operation}成功")

    def ecs_bind_unbind_affinity_group(self, name, operation: str, group_name: str):
        self.click_action(name, operation)
        self.get_by_role("dialog", name=operation).get_by_placeholder("请选择").click()
        self.get_by_role("listitem").filter(has_text=group_name).click()
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云服务器{name}{operation}{group_name}")
