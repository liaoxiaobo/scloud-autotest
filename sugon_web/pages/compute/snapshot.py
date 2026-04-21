import re

from sugon_web.common.base import submenu
from sugon_web.pages.ops import OpsPage
from sugon_web.utils.logger import logger


class SnapshotPage(OpsPage):


    @submenu("快照")
    def ecss_search(self, keyword, s_type="快照名称"):
        if s_type in ["快照名称", "实例名称", "存储池"]:
            if s_type != "快照名称":
                self.get_by_placeholder("请选择").nth(2).click()
                self.locator("li").filter(has_text=s_type).locator("span").click()
            input_loc = self.get_by_placeholder(f"搜索（{s_type}）")
            input_loc.fill(keyword)
            self.get_by_text("搜索", exact=True).click()
            return input_loc
        raise ValueError(f"不支持的搜索类型: {s_type}")

    @submenu("快照")
    def ecss_delete(self, snapshot_names):
        if isinstance(snapshot_names, list):
            self.select_rows_by_names(snapshot_names)
            self.btn_batch_delete.click()
        else:
            self.click_action(snapshot_names, "删除")
        self.dialog_confirm.click()
        self.logger.info(f"云服务器快照删除请求已提交: {snapshot_names}")

    @submenu("快照")
    def ecss_edit(self, name, new_name, new_desc):
        self.click_action(name, "修改")
        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^快照名称$")).get_by_role("textbox").fill(new_name)
        dialog.locator("textarea").fill(new_desc)
        self.dialog_confirm.click()

    @submenu("快照")
    def ecss_restore(self, snapshot_name):
        self.click_action(snapshot_name, "还原快照")
        self.dialog_confirm.click()

    @submenu("快照策略")
    def ecss_policy_create(self, name, hours, enabled=False, cycle_days=1, retention_type="按数量", retention_value=1,
                           snapshot_data_disk=False):
        self.btn_create.click()
        self.get_by_label("新建策略").get_by_role("textbox").fill(name)
        if enabled:
            self.get_by_role("switch").locator("span").click()
        if hours:
            for hour in hours:
                self.locator("label").filter(has_text=f"{hour:02d}:00").locator("span").nth(1).click()
        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))
        if snapshot_data_disk:
            self.locator("form div").filter(has_text="是否快照数据卷").locator("span").nth(2).click()
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))
        self.dialog_confirm.click()
        self.logger.info(f"云服务器快照策略创建请求已提交: {name}")

    @submenu("快照策略")
    def ecss_policy_delete(self, names):
        if isinstance(names, list):
            self.select_rows_by_names(names)
            self.btn_batch_delete.click()
        else:
            self.click_action(names, "删除")
        self.dialog_confirm.click()
        self.logger.info(f"云服务器快照策略删除请求已提交: {names}")

    @submenu("快照策略")
    def ecss_policy_edit(self, name, new_name, hours=[], enabled=False, cycle_days=1, retention_type="按数量",
                         retention_value=1, snapshot_data_disk=False):
        self.click_action(name, "编辑")
        self.get_by_label("修改策略").get_by_role("textbox").fill(new_name)
        if enabled:
            self.get_by_role("switch").locator("span").click()
        if hours:
            for hour in hours:
                self.locator("label").filter(has_text=f"{hour:02d}:00").locator("span").nth(1).click()
        self.locator("form div").filter(has_text="快照周期 天").get_by_role("spinbutton").fill(str(cycle_days))
        if snapshot_data_disk:
            self.locator("form div").filter(has_text="是否快照数据盘").locator("span").nth(2).click()
        self.get_by_role("radio", name=retention_type).click()
        if retention_type != "永久保存":
            self.locator("form div").filter(has_text="保留规则按数量 按时间 天 永久保存").get_by_role("spinbutton").fill(str(retention_value))
        self.dialog_confirm.click()
        self.logger.info(f"云服务器快照策略修改请求已提交: {new_name}")

    @submenu("弹性云服务器")
    def ecs_bind_snapshot_policy(self, name: str, policy: str, auto_snapshot: bool = False):
        self.click_action(name, "绑定快照策略")
        self.get_by_label("绑定快照策略").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=policy).click()
        if auto_snapshot:
            self.get_by_role("switch").locator("span").click()
        self.dialog_confirm.click()
        logger.info(f"{name}实例绑定快照策略: {policy}成功")

    @submenu("快照策略")
    def ecss_bind_unbind_snapshot_policy(self, name: str, policy: str, bind: bool = True,
                                         vm_type: str = "弹性云服务器"):
        text = "绑定" if bind else "解绑"
        self.click_action(policy, f"{text}云服务器")
        vm_type_locs = [
            self.get_by_role("tab", name=vm_type),
            self.locator("label").filter(has_text=vm_type),
            self.get_by_role("listbox").locator("li").filter(has_text=vm_type),
            self.get_by_role("radiogroup").locator("label").filter(has_text=vm_type),
        ]
        self._find_element(vm_type_locs).click()
        search_locs = [
            self.locator("section").get_by_placeholder("搜索（名称）"),
            self.get_by_role("dialog", name="详细信息 close 详细信息").get_by_placeholder("搜索（名称）"),
            self.get_by_role("dialog", name="解绑云服务器 close 解绑云服务器").get_by_placeholder("搜索（名称）"),
            self.get_by_role("textbox", name="搜索（实例名称）"),
            self.get_by_placeholder("搜索（实例名称）"),
        ]
        self._find_element(search_locs).fill(name)
        self.get_by_role("dialog").get_by_text("搜索").click()
        vm_names = self.get_column_data("名称/ID")
        vm_names = [vm_name.split(" ")[0] for vm_name in vm_names if vm_name.startswith(name)]
        loc = self.get_by_role("dialog").locator(
            ".el-table__header-wrapper:not(.el-table__fixed-header-wrapper) .el-checkbox"
        ).first
        try:
            loc.click()
            logger.info(f"勾选成功{vm_names}")
        except Exception:
            logger.warning("勾选复选框失败")
            loc.evaluate("element => element.click()")
            logger.info(f"element.click强制勾选 {loc}")
        self.dialog_confirm.click()
        logger.info(f"快照策略: {policy} 绑定云服务器: {vm_names}")
        return vm_names

    @submenu("快照策略")
    def ecss_unbind_snapshot_policy(self, vm_name: str, policy: str, vm_type: str = "弹性云服务器"):
        self.click_action(policy, "解绑云服务器")
        self.get_by_role("radiogroup").locator("label").filter(has_text=vm_type)
        self.get_by_role("textbox", name="搜索（实例名称）").click()
        self.get_by_role("textbox", name="搜索（实例名称）").fill(vm_name)
        self.get_by_role("dialog").get_by_text("搜索").click()
        self.get_by_role("row", name="名称/ID 物理机").locator("span").nth(1).click()
        vm_names = self.get_column_data("名称/ID")
        vm_names = [name.split(" ")[0] for name in vm_names if name.startswith(vm_name)]
        self.dialog_confirm.click()
        logger.info(f"快照策略: {policy} 解绑云服务器: {vm_names}")

    @submenu("快照任务")
    def ecss_modify_snapshot_task(self, vm_name: str, policy: str):
        self.click_action(vm_name, "修改策略")
        self.get_by_label("修改策略").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=policy).click()
        self.dialog_confirm.click()
        logger.info(f"云服务器: {vm_name} 快照策略修改为: {policy}")

    @submenu("快照任务")
    def ecss_modify_en_disable_auto_snapshot(self, vm_name: str, enable: bool = False):
        enable_text = "开启" if enable else "禁用"
        self.click_action(vm_name, f"{enable_text}自动快照")
        self.dialog_confirm.click()
        logger.info(f"云服务器: {vm_name} {enable_text}自动快照成功")

    @submenu("快照任务")
    def ecss_delete_task(self, vm_name):
        if isinstance(vm_name, list):
            self.select_rows_by_names(vm_name)
            self.btn_batch_delete.click()
        else:
            self.click_action(vm_name, "删除")
        self.dialog_confirm.click()
        self.logger.info(f"云服务器快照删除请求已提交: {vm_name}")
