import re
from sugon_web.common.base import submenu, BasePage
from sugon_web.utils.logger import logger


class ImageServiceMixin(BasePage):

    @submenu("弹性云服务器")
    def ecs_create_image(self, name: str, image_name: str):
        logger.info(f"开始创建云服务器镜像: {image_name}")
        self.click_action(name, "新建镜像")
        self.locator("div").filter(has_text=re.compile(r"^镜像名称$")).get_by_role("textbox").fill(image_name)
        self.dialog_confirm.click()
        logger.info(f"云服务器镜像创建请求已提交: {image_name}")

    @submenu("镜像服务")
    def ecs_image_delete(self, image_name):
        self.click_action(image_name, "删除")
        self.dialog_confirm.click()
        logger.info(f"操作完成: 删除镜像{image_name}成功")
