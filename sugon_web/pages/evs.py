from sugon_web.common.base import BasePage, submenu
import re

class EvsPage(BasePage):

    def __init__(self, page, env):
        super().__init__(page, env)

    @submenu("云硬盘")
    def evs_create(
        self,
        name,
        count=1,
        size=30,
        empty=True,
        image_name="xstor-test",
        volume_type="xstor-type",
        desc=""
    ):
        """创建云硬盘
    
        Args:
            name: 云硬盘名称
            count: 创建数量，默认为1
            size: 云硬盘大小（GB），默认为30GB
            empty: 是否创建空白云硬盘，默认True
            image_name: 镜像名称，默认为"xstor-test"
            volume_type: 云硬盘类型，默认为"xstor-type"
            desc: 云硬盘描述信息，默认为空
        """
        self.btn_create.click()
        self._input_name.fill(name)

        if count != 1:
            self._set_count(count)
        if not empty:
            self._select_image_source()
        self._select_volume_type(volume_type)
        if not empty:
            self._select_image(image_name)

        self._input_size.fill(str(size))
        self._input_desc.fill(desc)
        self.dialog_confirm.click()

    @property
    def _input_name(self):
        """云硬盘名称输入框"""
        return self.locator("div").filter(has_text=re.compile(r"^云硬盘名称$")).get_by_role("textbox")

    @property
    def _input_desc(self):
        """描述输入框"""
        return self.locator("textarea")

    @property
    def _input_size(self):
        """输入云硬盘大小"""
        return self.get_by_label("slider between 1 and").get_by_role("spinbutton")

    def _set_count(self, count):
        """设置云硬盘数量"""
        self.get_by_label("数量").fill(str(count))

    def _select_image_source(self):
        """选择云硬盘来源为镜像"""
        self.get_by_role("dialog", name="dialog").get_by_placeholder("请选择", exact=True).click()
        self.locator("li").filter(has_text=re.compile(r"^镜像$")).click()

    def _select_volume_type(self, name):
        """选择云硬盘类型"""
        self.get_by_placeholder("请选择类型").click()
        self.locator("li").filter(has_text=re.compile(fr"^{name}$")).click()

    def _select_image(self, name):
        """选择镜像"""
        self.locator("div:nth-child(6) > .el-form-item__content > .el-select > .el-input").click()
        self.get_by_text(name, exact=True).click()
        # self.get_by_role("listitem").filter(has_text=f"{name}").click()  #  存在包含name的字符串时，无法定位到元素
        # self.get_by_role("listitem").filter(has_text=re.compile(fr"^{name}$")).click()

    def _select_mode(self, mode):
        """选择云硬盘模式"""
        self.get_by_placeholder("请选择模式").click()
        self.locator("li").filter(has_text=re.compile(fr"^{mode}$")).click()

    @submenu("云硬盘")
    def evs_remove(self, name):
        """回收云硬盘资源
        
        Args:
            name: 云硬盘名称
        """
        self.click_dropdown_option(name, "删除")
        self.locator("div:nth-child(2) > div > .cloud-button-btn > span").click()

    @submenu("回收站")
    def evs_delete(self, name):
        """删除指定名称的云硬盘资源
        
        Args:
            name: 云硬盘名称
        """
        self.click_dropdown_option(name, "删除")
        self.get_by_text("确定").nth(2).click()

    @submenu("快照")
    def evss_delete(self, name):
        """删除指定名称的云硬盘快照资源
        
        Args:
            name: 快照名称
        """
        self.click_dropdown_option(name, "删除")
        self.get_by_text("确定", exact=True).nth(1).click()

    @submenu("云硬盘")
    def evs_modify(self, name, new_name, new_desc):
        """修改指定云硬盘的名称和描述
        
        Args:
            name: 原云硬盘名称
            new_name: 新的云硬盘名称
            new_desc: 新的描述信息
        """
        self.click_dropdown_option(name, "修改")
        self._fill_modify_form(new_name, new_desc)
        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_clone(self, source_name, clone_name):
        """克隆指定云硬盘
        
        Args:
            source_name: 源云硬盘名称
            clone_name: 克隆后的云硬盘名称
        """
        self.click_dropdown_option(source_name, "克隆")
        self._fill_clone_form(clone_name)
        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_expand(self, name, new_size):
        """扩容指定云硬盘
        
        Args:
            name: 云硬盘名称
            new_size: 扩容后的大小（GB）
        """
        self.click_dropdown_option(name, "扩容")
        self._fill_expand_form(new_size)
        self.dialog_confirm.click()

    @submenu("云硬盘")
    def evs_add_snapshot(self, volume_name, snapshot_name, desc):
        """给指定云硬盘添加快照
        
        Args:
            volume_name: 云硬盘名称
            snapshot_name: 快照名称
            desc: 快照描述
        """
        self.click_dropdown_option(volume_name, "添加快照")
        self._fill_snapshot_form(snapshot_name, desc)
        self.dialog_confirm.click()

    def _fill_modify_form(self, new_name, new_desc):
        """填写修改表单"""
        dialog = self.get_by_role("dialog")
        dialog.locator('input[type="text"]').click()
        dialog.locator('input[type="text"]').fill(new_name)
        dialog.locator("textarea").click()
        dialog.locator("textarea").fill(new_desc)

    def _fill_clone_form(self, clone_name):
        """填写克隆表单"""
        dialog = self.get_by_role("dialog")
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.click()
        name_input.fill(clone_name)

    def _fill_expand_form(self, new_size):
        """填写扩容表单"""
        dialog = self.get_by_label("扩容")
        size_input = dialog.get_by_role("spinbutton")
        size_input.click()
        size_input.fill(str(new_size))

    def _fill_snapshot_form(self, snapshot_name, desc):
        """填写快照表单"""
        dialog = self.get_by_role("dialog")
        # 填写快照名称
        name_input = dialog.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox")
        name_input.click()
        name_input.fill(snapshot_name)
        # 填写描述
        desc_input = dialog.locator("textarea")
        desc_input.click()
        desc_input.fill(desc)

