from sugon_web.common.base import submenu
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger


class LabelPage(OpsPage):

    @submenu("弹性云服务器")
    def bind_labels(self, name: str, label_names: list, bind: bool = True):
        bind_text = "绑定" if bind else "解绑"
        logger.info(f"{bind_text} 标签 {label_names} 到云服务器'{name}'")
        self.click_action(name, "标签设置")
        for label_name in label_names:
            self.get_by_label("标签设置", exact=True).get_by_text(label_name).click()
        if bind:
            self.get_by_label("标签设置", exact=True).get_by_role("button").locator(".el-icon-arrow-right").click()
        else:
            self.get_by_label("标签设置", exact=True).get_by_role("button").locator(".el-icon-arrow-left").click()
        self.assert_popup_success(f"实例{bind_text}标签成功,若数据未响应请刷新页面")
        self.dialog_close.click()
        logger.info(f"标签 {label_names} 成功{bind_text}到云服务器'{name}'")

    @submenu("标签")
    def create_label(self, name: str):
        logger.info(f"创建标签: 名称={name}, 描述={name}")
        self.btn_create.click()
        self.get_by_label("新建标签").locator("input[type=\"text\"]").fill(name)
        self.get_by_role("textbox", name="请输入描述内容").fill(name)
        self.dialog_confirm.click()
        logger.info(f"标签{name}请求提交成功")
        return name

    @submenu("标签")
    def delete_label(self, name: str):
        self.sort_by_header("创建时间", "desc")
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        logger.info(f"标签{name}删除请求提交成功")

    @submenu("标签")
    def batch_delete_label(self, names: list):
        self.sort_by_header("创建时间", "desc")
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        logger.info(f"标签{names}删除成功")

    @submenu("标签")
    def edit_label(self, name: str, new_name: str):
        self.sort_by_header("创建时间", "desc")
        self.click_action(name, "编辑")
        self.get_by_label("修改标签").locator("input[type=\"text\"]").fill(new_name)
        self.get_by_role("textbox", name="请输入描述内容").fill(new_name)
        self.dialog_confirm.click()
        self.assert_popup_success("修改标签成功")
        logger.info(f"标签{name}编辑修改为: {new_name}")

    @submenu("标签")
    def unbind_vm_from_label(self, vm_name: str, label_name: str):
        self.sort_by_header("创建时间", "desc")
        self.click_action(label_name, "查看关联资源")
        self.get_by_label("实例", exact=True).get_by_text("解绑实例标签").click()
        self.dialog_confirm.click()
        self.assert_popup_success("实例解绑标签成功")
        self.dialog_close.click()
        logger.info(f"标签页{label_name}解绑实例: {vm_name}成功")

    @submenu("标签")
    def delete_batch_unbind_label(self, names: list, label_names: list):
        self.sort_by_header("创建时间", "desc")
        for label_name in label_names:
            self.click_action(label_name, "查看关联资源")
            self.select_rows_by_names(names)
            self.get_by_text("批量解绑").click()
            self.dialog_confirm.click()
            self.get_by_label("实例", exact=True).get_by_label("Close").click()
        logger.info(f"{label_names}批量解绑云服务器: {names}成功")
