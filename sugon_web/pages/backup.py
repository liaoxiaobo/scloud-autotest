import re
import time
from time import sleep
import pytest
from playwright.sync_api import expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config
from sugon_web.utils.logger import logger


class BackUpPage(BasePage):

    @submenu("任务")
    def create_backup_task(
            self,
            task_name: str,
            server_names: list,
            policy: dict = None,
            **kwargs
    ):
        """创建备份任务
        Args:
            task_name: 任务名称
            server_names: 云服务器名称列表
            policy: 备份策略配置字典
            **kwargs: 其他参数
        """
        policy = policy or {}

        # 点击新建备份任务按钮
        self.get_by_text("新建备份任务").click()

        # 搜索选择添加服务器
        self._add_servers(server_names)
        self._click_next_step()

        # 配置备份策略
        policy_type = policy.get("策略类型", "自定义策略")
        time_policy = policy.get("时间策略", {})
        speed_policy = policy.get("限速策略", {})
        storage_policy = policy.get("存储策略", {})
        retention_policy = policy.get("保留策略", {})
        thread_policy = policy.get("高级策略", {})

        self._backup_policy(
            policy_type,
            time_policy,
            speed_policy,
            storage_policy,
            retention_policy,
            thread_policy
        )
        self.get_by_text("下一步").click()

        # 设置任务名称，点击立即创建
        self._set_task_name_create(task_name)

    def _add_servers(self, server_names):
        """添加云服务器

        Args:
            server_names: 云服务器名称
        """
        if isinstance(server_names, str):
            server_names = [server_names]

        for server_name in server_names:
            locs = [
                self.get_by_label("dialog").get_by_text("重置"),
                self.get_by_text("重置", exact=True).first
            ]
            self._find_element(locs, "重置元素").click()
            self._search_and_select_server(server_name)

            locs = [
                self.get_by_text("》"),
                self.locator(".transferButton > div > .cloud-button-btn").first
            ]
            self._find_element(locs, "》元素").click()

    def _remove_servers(self, server_names: list):
        """移除云服务器
        Args:
            server_names: 云服务器名称
        """
        if isinstance(server_names, str):
            server_names = [server_names]

        for server_name in server_names:
            self.locator(".rightTransfer").locator("label").filter(has_text=f"运行 {server_name}").click()
        locs = [
            self.get_by_text("《"),
            self.locator(".transferButton > div > .cloud-button-btn").nth(1)
        ]
        self._find_element(locs, "《元素").click()

    def _search_and_select_server(self, server_name: str):
        """搜索并选择云服务器

        Args:
            server_name: 云服务器名称
        """

        # 输入服务器名称搜索
        self.get_by_placeholder("请输入云服务器名称搜索").click()
        self.get_by_placeholder("请输入云服务器名称搜索").fill(server_name)
        # 点击搜索按钮
        locs = [
            self.get_by_label("dialog").get_by_text("搜索"),
            self.get_by_text("搜索", exact=True),
        ]
        self._find_element(locs, "搜索按钮").click()
        # 选择服务器（勾选复选框）
        self.locator(".leftTransfer").locator("label").filter(has_text=f"运行 {server_name} ID:").click()
        logger.info(f"搜索云服务器: {server_name}")

    def _click_next_step(self):
        """点击下一步按钮"""

        self.get_by_text("下一步").click()

        logger.info("点击下一步")

    def _backup_policy(
            self,
            policy_type: str = "自定义策略",
            time_policy: dict = None,
            speed_policy: dict = None,
            storage_policy: dict = None,
            retention_policy: dict = None,
            thread_policy: dict = None
    ):
        """配置备份策略
        根据传入的策略配置，智能比较当前值并修改发生变化的策略项。
        Args:
            policy_type: 策略类型，如"自定义策略"
            time_policy: 时间策略配置字典
            speed_policy: 限速策略配置字典
            storage_policy: 存储策略配置字典
            retention_policy: 保留策略配置字典
            thread_policy: 高级策略配置字典
        """
        # 选择策略类型
        self._select_backup_policy(policy_type)

        if policy_type == "自定义策略":
            # 处理时间策略
            if time_policy:
                self._process_time_policy(time_policy)

            # 处理限速策略
            if speed_policy:
                self._process_speed_policy(speed_policy)

            # 处理存储策略
            if storage_policy:
                self._process_storage_policy(storage_policy)

            # 处理保留策略
            if retention_policy:
                self._process_retention_policy(retention_policy)

            # 处理高级策略
            if thread_policy:
                self._process_advanced_policy(thread_policy)
        logger.info("备份策略配置完成")

    def _set_task_name_create(self, task_name: str):
        """设置任务名称并创建
        Args:
            task_name: 任务名称
        """
        self.get_by_placeholder("请输入任务名称").fill(task_name)
        self.btn_submit.click()
        logger.info(f"备份任务{task_name}已提交")

    def _select_backup_policy(self, policy_type: str):
        """选择策略

        Args:
            policy_type: 策略类型，如"自定义策略"
        """
        # 选择策略类型
        locs = [
            self.locator("div").filter(has_text=re.compile(r"^选择策略$")).get_by_placeholder("请选择"),
            self.get_by_text("选择策略").locator("xpath=./following-sibling::div//input"),
            self.locator("#cloud-container-content").get_by_placeholder("请选择", exact=True)
        ]
        self._find_element(locs, "选择策略").click()
        self.locator("li").filter(has_text=policy_type).click()

    def _cycle_policy(self, cycle: dict, container=None):
        """配置时间策略

        Args:
            cycle: 时间策略配置字典
        """
        try:
            # 根据键名判断场景类型
            use_dialog = "备份周期" not in cycle.keys()  # 限速策略使用dialog，备份任务不使用dialog
            cycle_key = "周期" if use_dialog else "备份周期"
            time_key = "时间" if use_dialog else "备份时间"
            frequency_key = "频率" if use_dialog else "备份频率"
            cycle_type = cycle.get(cycle_key)

            locs = [
                container.get_by_role("radio", name=cycle_type),
                container.locator("div").filter(has_text=re.compile(rf"^{cycle_type}$")).nth(1),
            ]
            loc = self._find_element(locs, element_name=f"{cycle_type}元素")
            loc.click()

            # 根据周期类型选择具体配置
            if cycle_type == "周":
                # 选择星期 - 根据场景选择定位方式
                days_of_week = cycle.get(time_key)

                week_interval = cycle.get(frequency_key, "每周")
                self._select_frequency(week_interval, container)

                # 第一步：取消所有已选中的星期
                if days_of_week:
                    # 获取所有checkbox
                    all_checkboxes = container.locator(".el-checkbox")
                    count = all_checkboxes.count()
                    for i in range(count):
                        checkbox = all_checkboxes.nth(i)
                        if checkbox.is_checked():
                            # 使用 filter 和 re.compile 来匹配星期文本
                            weekday_text = checkbox.filter(
                                has_text=re.compile(r"星期[一二三四五六日]")).inner_text() if checkbox.filter(
                                has_text=re.compile(r"星期[一二三四五六日]")).count() > 0 else ""
                            # 如果不在目标列表中，取消选中
                            if weekday_text not in days_of_week:
                                checkbox.click()

                # 第二步：只选中传入的星期
                for day in days_of_week:
                    if use_dialog:
                        # 限速策略场景：在dialog容器内
                        locs = [container.get_by_text(day)]
                    else:
                        # 备份任务场景：在container内定位
                        locs = [container.locator(".el-checkbox").get_by_text(day)]
                    fin_loc = self._find_element(locs, element_name=f"{day}元素")
                    if not fin_loc.is_checked():
                        fin_loc.click()

                # 选择循环间隔

                logger.info(f"时间策略配置完成: 周期= {week_interval}, 循环间隔={days_of_week}")

            elif cycle_type == "月":
                month_interval = cycle.get(frequency_key, "每月")
                month_days = cycle.get(time_key, [])
                if isinstance(month_days, (str, int)):
                    month_days = [str(month_days)]
                else:
                    month_days = [str(day) for day in month_days]

                self._select_frequency(month_interval, container)

                date_content = container.locator(".date-content:visible").first
                if date_content.count() == 0:
                    date_content = container.locator(".date-content").first

                # 第一步：取消所有不在目标日期内的已选中项
                day_items = date_content.locator(".date-item")
                for i in range(day_items.count()):
                    day_item = day_items.nth(i)
                    day_text = day_item.inner_text().strip()
                    day_class = day_item.get_attribute("class") or ""
                    if "selected" in day_class and day_text not in month_days:
                        day_item.click()

                # 第二步：选中目标日期
                for month_day in month_days:
                    day_item = date_content.locator(".date-item").filter(has_text=re.compile(rf"^\s*{re.escape(month_day)}\s*$")).first
                    day_class = day_item.get_attribute("class") or ""
                    if "selected" not in day_class:
                        day_item.click()

                logger.info(f"时间策略配置完成: 周期= {month_interval}, 循环间隔={month_days}")

            elif cycle_type == "天":
                logger.info(f"时间策略配置完成: 周期={cycle_type}")

            else:
                raise ValueError(f"不支持的周期类型: {cycle_type}")

        except Exception as e:
            logger.error(f"配置时间策略失败: {e}")
            raise

    def _set_time_policy(self, execution_time: str = "02:00:00", container=None):
        """设置时间策略
        Args:
            execution_time: 执行时间
        """
        container = container if container else self
        container.get_by_placeholder("选择时间").last.click()
        container.get_by_placeholder("选择时间").last.fill(execution_time)
        container.get_by_placeholder("选择时间").last.press("Enter")
        logger.info(f"时间配置完成: 时间={execution_time}")

    def _select_frequency(self, frequency: str, base_container=None):
        """选择频率

        Args:
            frequency: 频率，如"每周"、"每2周"等
            base_container: 基础容器（根据场景可能是dialog或container）
        """
        container = base_container if base_container else self
        # 定位输入框
        loc = container.get_by_text("频率").locator("xpath=./following-sibling::div//input")

        # 检查当前选中项是否与传入的频率一致
        try:
            # 获取当前输入框的值（显示的文本）
            current_value = loc.input_value()

            # 如果当前值与目标值一致，无需修改
            if current_value == frequency:
                logger.info(f"频率已是目标值: {frequency}，无需修改")
                return
        except Exception:
            # 如果无法获取当前值，继续执行选择操作
            pass

        # 点击下拉框打开选项
        loc.click()

        # 查找并点击目标频率选项
        self.locator("li").filter(has_text=frequency).last.click()

        logger.info(f"频率修改为: {frequency}")

    def _select_speed_limit_type(self, limit_type: str):
        """选择限速方式
        Args:
            limit_type: 限速方式 按策略限速/永久限速
        """
        self.get_by_placeholder("请选择限速方式").click()
        self.locator("li").filter(has_text=limit_type).click()

    # 设置开始结束时间
    def _set_time_range(self, start_time: str, end_time: str):
        """设置开始、结束时间
        Args:
            start_time: 开始时间
            end_time: 结束时间
        """
        start_loc = self.get_by_text("开始时间").locator("xpath=./following-sibling::div//input")
        start_loc.clear()
        start_loc.fill(start_time)
        start_loc.press("Enter")

        end_loc = self.get_by_text("结束时间").locator("xpath=./following-sibling::div//input")
        end_loc.clear()
        end_loc.fill(end_time)
        end_loc.press("Enter")
        logger.info(f"时间配置完成: 开始时间={start_time}, 结束时间={end_time}")

    # 设置限速大小
    def _set_speed_limit_size(self, speed: str, unit: str = "KiB/s"):
        """设置限速大小（增强版）

        Args:
            speed: 限速大小（字符串或数字）
            unit: 限速单位（"KiB/s" 或 "MiB/s"）

        Raises:
            ValueError: 当 MiB/s 单位且速度大于1000时抛出异常
        """
        # 转换为浮点数
        try:
            speed_value = float(speed)
        except (ValueError, TypeError):
            raise ValueError(f"速度值无效: {speed}")

        # 规则1: 如果传入的unit是"KiB/s"且speed大于1000，转换为MiB/s
        if unit == "KiB/s" and speed_value > 1000:
            logger.info(f"速度 {speed} KiB/s 大于1000，自动转换为 MiB/s")
            unit = "MiB/s"
            # 速度除以1024
            converted_speed = speed_value / 1024
            # 如果是整数，不显示小数；否则保留两位小数
            if converted_speed == int(converted_speed):
                speed_value = int(converted_speed)
            else:
                speed_value = round(converted_speed, 2)
            logger.info(f"转换后速度: {speed_value} {unit}")

        # 规则2: 如果unit是"MiB/s"，speed不允许大于1000
        elif unit == "MiB/s" and speed_value > 1000:
            raise ValueError(f"MiB/s 单位下速度不允许大于1000，当前值: {speed_value}")

        # 选择单位
        self.locator("span").filter(has_text="KiB/s MiB/s").locator("i").click()
        self.locator("li").filter(has_text=unit).click()

        # 填充速度值
        self.get_by_label("限速策略").get_by_role("spinbutton").fill(str(speed_value))

        logger.info(f"限速大小设置完成: {speed_value} {unit}")

    def _process_time_policy(self, time_policy: dict):
        """处理时间策略配置

        Args:
            time_policy: 时间策略配置字典
        """
        backup_method = time_policy.get("备份方式") or "一次性备份"

        # 获取当前备份方式（如果存在）
        current_method = self._get_cur_backup_method()

        # 只修改备份方式发生变化的情况
        if current_method and current_method != backup_method:
            locs = [
                self.locator("div").filter(has_text=re.compile(r"^备份方式$")).get_by_placeholder("请选择"),
                self.get_by_text("备份方式").locator("xpath=./following-sibling::div//input")
            ]
            self._find_element(locs, "备份方式").click()

            self.locator("li").filter(has_text=backup_method).click()
            logger.info(f"修改备份方式: {current_method} -> {backup_method}")

        # 根据备份方式处理配置
        if backup_method == "周期性备份":
            policy_infos = time_policy.get("时间策略信息")
            # 取消勾选已存在的备份类型
            for i in ["全量备份", "增量备份"]:
                loc = self.locator(f".el-checkbox:has-text('{i}')")
                if loc.is_checked():
                    loc.click()

            if policy_infos:
                for policy_info in policy_infos:
                    backup_type = policy_info.get("备份类型")
                    type_loc = self.locator(f".el-checkbox:has-text('{backup_type}')")
                    # type_loc = self.get_by_text("备份类型").locator("xpath=./following-sibling::div//label").filter(has_text=backup_type)
                    logger.info(f"修改备份类型: {backup_type}")
                    if not type_loc.is_checked():
                        type_loc.click()
                    card_loc = self.get_by_text(backup_type).last.locator("xpath=./following-sibling::div")
                    if policy_info:
                        self._cycle_policy(policy_info, container=card_loc)
                    # 设置执行时间
                    self._set_time_policy(policy_info.get("执行时间"), container=card_loc)

    def _process_speed_policy(self, speed_policy: dict):
        """处理限速策略配置

        Args:
            speed_policy: 限速策略配置字典
        """

        limit_type = speed_policy.get("限速方式")
        cycle_info = speed_policy.get("时间策略信息")
        start_time = speed_policy.get("开始时间")
        end_time = speed_policy.get("结束时间")
        speed = speed_policy.get("限速大小")
        unit = speed_policy.get("单位")
        # 删除已有的限速策略
        try:
            locs = [
                self.get_by_title("删除"),
                self.get_by_role("img", name="删除")
            ]
            self._find_element(locs, "删除").click()
        except Exception as e:
            logger.info(f"尝试删除已存在的限速策略失败")

        # 点击设置限速策略
        self.get_by_text("设置限速策略").click()

        # 获取当前限速方式
        current_limit_type = self._get_cur_limit_type()

        # 只修改限速方式发生变化的情况
        if current_limit_type and current_limit_type != limit_type:
            logger.info(f"修改限速方式: {current_limit_type} -> {limit_type}")
            self._select_speed_limit_type(limit_type)

        # 处理时间限速策略
        if limit_type != "永久限速":
            if cycle_info:
                base_loc = self.get_by_label("限速策略")
                self._cycle_policy(cycle_info, base_loc)
                self._set_time_range(start_time, end_time)

        # 设置限速大小
        self._set_speed_limit_size(speed, unit)

        self.dialog_confirm.click()

    def _process_storage_policy(self, storage_policy: dict):
        """处理存储策略配置

        Args:
            storage_policy: 存储策略配置字典
        """
        deduplication = storage_policy.get("重复数据删除")
        compression = storage_policy.get("压缩存储")
        encryption = storage_policy.get("数据加密")

        # 获取当前存储策略值
        cur_dedup = self._get_cur_check_status("重复数据删除")
        cur_compression = self._get_cur_check_status("压缩存储")
        cur_encryption = self._get_cur_check_status("数据加密")
        loc = "xpath=./following-sibling::div//span"

        # 只修改发生变化的配置项
        if cur_dedup and cur_dedup != deduplication:
            self.get_by_text("重复数据删除", exact=True).locator(loc).click()
            logger.info(f"修改重复数据删除: {cur_dedup} -> {deduplication}")

        if cur_compression and cur_compression != compression:
            self.get_by_text("压缩存储", exact=True).locator(loc).click()
            logger.info(f"修改压缩存储: {cur_compression} -> {compression}")

        if cur_encryption and cur_encryption != encryption:
            self.get_by_text("数据加密", exact=True).locator(loc).click()
            logger.info(f"修改数据加密: {cur_encryption} -> {encryption}")

        logger.info(f"存储策略配置完成: 重复数据删除={deduplication}, 压缩存储={compression}, 数据加密={encryption}")

    def _process_retention_policy(self, retention_policy: dict):
        """处理保留策略配置

        Args:
            retention_policy: 保留策略配置字典
        """
        retention_type = retention_policy.get("数据保留方式")
        retention_value = retention_policy.get("保留数")

        # 获取当前保留策略值
        current_type = self._get_cur_retention_type()
        current_value = self._get_cur_num_value(f"保留{current_type}")
        # 只修改发生变化的配置项
        if retention_type and current_type != retention_type:
            self.get_by_placeholder("请选择数据保留方式").click()
            self.locator("li").filter(has_text=retention_type).click()
            logger.info(f"修改保留类型: {current_type} -> {retention_type}")

        if retention_value and current_value != retention_value:
            # 只有当保留类型为"个数"或"天数"时，才处理保留数值
            if retention_type in ["个数", "天数"]:
                # 比较并修改保留数量
                if not current_value or current_value != retention_value:
                    # 定位对应的输入框
                    self.get_by_text(f"保留{retention_type}").locator("xpath=./following-sibling::div/div/div/input").fill(retention_value)
                    logger.info(f"修改保留数量: {current_value} -> {retention_value}")
        logger.info(f"保留策略配置完成: 类型={retention_type}, 数值={retention_value}")

    def _process_advanced_policy(self, thread_policy: dict):
        """处理高级策略配置

        Args:
            thread_policy: 高级策略配置字典
        """
        retain = thread_policy.get("快照保留")
        count = thread_policy.get("线程数")

        # 获取当前高级配置值
        cur_retain = self._get_cur_check_status("快照保留")
        cur_count = self._get_cur_num_value("线程数量")

        # 只修改发生变化的配置项
        if cur_retain and cur_retain != retain:
            locs = [
                self.get_by_text("快照保留", exact=True).locator("xpath=./following-sibling::div/div"), # 修改策略
                self.get_by_text("快照保留", exact=True).locator("xpath=../following-sibling::div/div"), # 新建
            ]
            self._find_element(locs, "快照保留").click()
            logger.info(f"修改快照保留: {cur_retain} -> {retain}")

        if cur_count and cur_count != count:
            locs = [
                self.get_by_text("线程数量", exact=True).locator("xpath=./following-sibling::div//input"), # 修改策略
                self.get_by_text("线程数量", exact=True).locator("xpath=../following-sibling::div//input") # 新建备份任务
            ]
            self._find_element(locs, "线程数量").fill(count)
            logger.info(f"修改线程数: {cur_count} -> {count}")
            logger.info(f"高级策略配置完成: 快照保留 {retain}, 线程数 {count}")

    # 获取当前策略值
    def _get_cur_backup_method(self) -> str:
        """获取当前备份方式
        Returns:
            当前备份方式文本
        """
        try:
            return self.get_by_text("备份方式").locator("xpath=./following-sibling::div//input").input_value()
        except:
            return ""

    def _get_cur_limit_type(self) -> str:
        """获取当前限速方式
        Returns:
            当前限速方式文本
        """
        try:
            return self.get_by_placeholder("请选择限速方式").input_value()
        except:
            return ""

    def _get_cur_check_status(self, policy_name: str) -> str:
        """获取el-switch的当前状态
        Args:
            policy_name: 策略名称，如"重复数据删除"、"压缩存储"、"数据加密"
        Returns:
            当前策略值（"开启"或"关闭"）
        """
        try:
            # 查找策略所在的容器
            policy_container = self.get_by_text(policy_name, exact=True)
            # 获取当前状态（开启或关闭）
            locs = [
                policy_container.locator("xpath=./following-sibling::div/div"), # 修改策略
                policy_container.locator("xpath=../following-sibling::div/div"), # 新建
            ]
            status_element = self._find_element(locs, "快照保留")
            for status_element in status_element.all():
                if "is-checked" in status_element.get_attribute("class"):
                    return "开启"
                else:
                    return "关闭"
        except:
            return ""

    def _get_cur_retention_type(self) -> str:
        """获取当前保留类型
        Returns:
            当前保留类型文本
        """
        try:
            return self.get_by_text("数据保留方式").locator("xpath=./following-sibling::div//input").input_value()
        except:
            return ""

    def _get_cur_num_value(self, label_text: str) -> str:
        """获取数字输入框的值

        Args:
            label_text: label文本，如"线程数量"、"保留个数"

        Returns:
            当前数值
        """
        locs = [
            # self.get_by_label(label_text).get_by_role("spinbutton"),
            # self.get_by_label(label_text).locator("input[role='spinbutton']"),
            self.locator("form div").filter(has_text=label_text).get_by_role("spinbutton"),
            self.get_by_text(label_text).locator("xpath=./following::input[@role='spinbutton']")
        ]
        input_element = self._find_element(locs, "数字输入框")

        try:
            value = input_element.input_value()
        except:
            value = input_element.get_attribute("aria-valuenow")

        return value

    @submenu("备份任务")
    def delete_backup_task(self, task_name: str):
        """删除备份任务

        Args:
            task_name: 备份任务名称
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_action(task_name, "删除")
        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()
        logger.info(f"备份任务删除请求已提交: {task_name}")

    def assert_backup_task_exists(self, task_name: str):
        """断言备份任务存在

        Args:
            task_name: 备份任务名称
        """
        self.assert_list_contain(task_name, "任务名")

    def assert_backup_task_not_exists(self, task_name: str):
        """断言备份任务不存在

        Args:
            task_name: 备份任务名称
        """
        logger.info(f"验证备份任务不存在: {task_name}")
        self.assert_deleted(task_name)

    @submenu("任务")
    def backup_remove(self, names):
        """删除备份资源，支持单个和批量操作

        Args:
            names: 备份任务名称（字符串）或备份任务列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击更多操作按钮
            self.get_by_role("button", name="更多操作 ").click()

            # 点击批量删除选项
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成

    @submenu("任务")
    def backup_to_details(self, name: str):
        """进入备份任务详情页面

        Args:
            name: 备份任务名称
        """

        # 点击备份任务的详情链接
        self.get_by_role("cell", name=name).locator("span").click()

        logger.info(f"成功进入备份任务{name}详情页")

    def backup_back_to_list(self):
        """返回备份任务列表页
        """

        self.locator(".el-icon-back").click()

    def assert_backup_policy_details(self, name, policy_infos: dict, tab="详情"):
        """验证备份任务详情页面信息

        Args:
            name: 备份任务称
            policy_infos: 需要验证的信息项字典
        """
        self.backup_to_details(name)
        if tab == "详情":
            # 等待“基本信息”标题出现，确保详情页面已加载
            self.locator(".detail-page-title").filter(has_text="基本信息").wait_for(state="visible", timeout=5000)
            infos = self.policy_to_assert_dict(policy_infos)
            self.logger.info(f"infos: {infos}")
            # 逐个验证信息项
            for k, v in infos.items():
                label_loc = self.get_by_text(k, exact=True)
                if k in ["备份方式", "限速策略"]:
                    loc = label_loc.locator("xpath=../following-sibling::div")
                    expect(loc).to_contain_text(v)
                    self.logger.info(f"验证成功 {k}: {v}")
                else:
                    for i, policy_text in enumerate(v):
                        loc = label_loc.locator(f"xpath=../following-sibling::div/div/div[{i + 1}]")
                        # if k in ["存储策略", "保留策略", "高级配置"]:
                        #     expect(loc).to_contain_text(policy_text.strip(": ")[-1])
                        expect(loc).to_contain_text(policy_text)
                        self.logger.info(f"验证成功 {k}[{i}]: {policy_text}")
        else:
            self.get_by_role("tab", name=tab).click()
            self.locator(".el-tab-pane:not([aria-hidden='true']) .el-table__row").first.wait_for(state="visible", timeout=5000)
            for k, v in policy_infos.items():
                self.assert_list_contain(v, k)

        logger.info(f"备份任务{name} 详情信息 验证成功")

    def policy_to_assert_dict(self, original_policy):
        """转换备份信息字典格式, 用于断言

        Args:
            original_policy: 原始备份信息字典
        Returns:
            转换后的字典，格式为:
                {
                    '备份方式': '周期性备份',
                    '时间策略': '增量备份（每3周,星期一、星期三、星期五 01:00:00 开始）',
                    '限速策略': '限速策略（每周,每周,星期一、星期三 00:00:00开始, 08:00:00结束; 限速大小10.000 KiB/s'
                }
        """
        result = {}

        # 处理时间策略
        if '时间策略' in original_policy:
            time_policy = original_policy['时间策略']
            result['备份方式'] = time_policy.get('备份方式', '')

            policy_info_list = time_policy.get('时间策略信息', [])
            if policy_info_list:
                time_policies = []  # 用于存储所有时间策略字典

                for i in range(len(policy_info_list)):
                    info = policy_info_list[i]
                    backup_type = info.get('备份类型', '')
                    backup_cycle = info.get('备份周期', '')
                    backup_frequency = info.get('备份频率', '')
                    backup_days = info.get('备份时间', [])
                    exec_time = info.get('执行时间', '')

                    # 确保 backup_days 是列表类型
                    if backup_days and isinstance(backup_days, list):
                        if "星期" not in backup_days[0]:
                            days_str = '号、'.join(backup_days)
                        else:
                            days_str = '、'.join(backup_days)
                    else:
                        days_str = str(backup_days) if backup_days else ''

                    # 构建单个时间策略字符串
                    if "月" in backup_cycle:
                        single_policy_str = f"{backup_type}（{backup_frequency},{days_str}号 {exec_time} 开始）"
                    elif "周" in backup_cycle:
                        days_str = days_str.replace("星期天", "星期日")
                        single_policy_str = f"{backup_type}（{backup_frequency},{days_str} {exec_time} 开始）"
                    elif "天" in backup_cycle:
                        single_policy_str = f"{backup_type}（每天 {exec_time} 开始）"
                    else:
                        raise Exception(f"未知的备份频率: {backup_frequency}")
                    time_policies.append(single_policy_str)  # 添加到列表

                result['时间策略'] = time_policies

        # 处理限速策略
        if '限速策略' in original_policy:
            speed_policy = original_policy['限速策略']
            speed_limit_mode = speed_policy.get('限速方式', '')
            speed_size = speed_policy.get('限速大小')
            speed_unit = speed_policy.get('单位')

            # 格式化限速大小，处理小数位数
            try:
                speed_size_float = float(speed_size)
                # 规则1: 如果传入的unit是"KiB/s"且speed大于1000，转换为MiB/s
                if speed_unit == "KiB/s" and speed_size_float > 1000:
                    logger.info(f"限速大小 {speed_size} KiB/s 大于1000，自动转换为 MiB/s")
                    speed_unit = "MiB/s"
                    # 速度除以1024
                    converted_speed = speed_size_float / 1024
                    # 如果是整数，不显示小数；否则保留两位小数
                    if converted_speed == int(converted_speed):
                        speed_size_float = int(converted_speed)
                    else:
                        speed_size_float = round(converted_speed, 2)
                    logger.info(f"转换后限速大小: {speed_size_float} {speed_unit}")
                # 格式化为保留3位小数，不足3位用0补齐，超过3位四舍五入
                speed_size_formatted = f"{speed_size_float:.3f} {speed_unit}"
            except (ValueError, TypeError):
                # 如果转换失败，保持原样并添加 .000
                speed_size_formatted = f"{speed_size}.000 {speed_unit}"

            # 获取时间策略信息
            if speed_limit_mode != "永久限速":
                speed_time_info = speed_policy.get('时间策略信息')
                speed_period = speed_time_info.get('周期')
                speed_frequency = speed_time_info.get('频率')
                speed_days = speed_time_info.get('时间')
                speed_start = speed_policy.get('开始时间')
                speed_end = speed_policy.get('结束时间')
                # 安全处理：确保 speed_days 是列表类型
                if speed_days and isinstance(speed_days, list):
                    if "星期" not in speed_days[0]:
                        days_str = '号、'.join(speed_days)
                    else:
                        days_str = '、'.join(speed_days)
                else:
                    days_str = str(speed_days) if speed_days else ''
                if "月" in speed_period:
                    single_policy_str = f"（{speed_frequency},{days_str}号 {speed_start}开始, {speed_end}结束; 限速大小{speed_size_formatted}）"
                elif "周" in speed_period:
                    if "星期天" in speed_days:
                        days_str = days_str.replace("星期天", "星期日")
                    single_policy_str = f"（{speed_frequency},{days_str} {speed_start}开始, {speed_end}结束; 限速大小{speed_size_formatted}）"
                elif "天" in speed_period:
                    single_policy_str = f"（ 每{speed_period} {speed_start}开始, {speed_end}结束; 限速大小{speed_size_formatted}）"
                else:
                    raise Exception(f"未知的备份频率: {speed_period}")
            else:
                single_policy_str = f"（永久限速 限速大小{speed_size_formatted}）"
            speed_policy_str = f"限速策略{single_policy_str}"
            result['限速策略'] = speed_policy_str

        # 处理存储策略
        if '存储策略' in original_policy:
            storage_policy = original_policy['存储策略']
            storage_strategy = [
                f"重复数据删除：{storage_policy.get('重复数据删除', '')}", # 页面字体为使用”：“
                f"压缩存储：{storage_policy.get('压缩存储', '')}",
                f"数据加密：{storage_policy.get('数据加密', '')}"
            ]
            result['存储策略'] = storage_strategy

        # 处理保留策略
        if '保留策略' in original_policy:
            retention_policy = original_policy['保留策略']
            retention_mode = retention_policy.get('数据保留方式', '')
            retention_count = retention_policy.get('保留数', '10')
            # 根据保留方式确定单位
            if retention_mode == '个数':
                unit = '个'
            elif retention_mode == '天数':
                unit = '天'
            elif retention_mode == '月数':
                unit = '月'
            else:
                unit = '个'
            retention_strategy = [
                f"数据保留方式：{retention_mode}",
                f"数据保留：{retention_count}\n（单位：{unit}）"
            ]
            result['保留策略'] = retention_strategy

        # 处理高级策略
        if '高级策略' in original_policy:
            advanced_policy = original_policy['高级策略']
            snapshot_retention = advanced_policy.get('快照保留', '开启')
            thread_count = advanced_policy.get('线程数', "3")
            # 转换快照保留为"是/否"
            snapshot_retention_str = '是' if snapshot_retention == '开启' else '否'
            # 转换线程数格式
            try:
                thread_count_int = int(thread_count)
                thread_count_str = f"{thread_count_int}个"
            except (ValueError, TypeError):
                thread_count_str = f"{thread_count}个"

            advanced_config = [
                f"快照保留：{snapshot_retention_str}",
                f"线程数量：{thread_count_str}"
            ]
            result['高级配置'] = advanced_config

        return result


    @submenu("任务")
    def backup_start_stop(self, name: str, operation: str):
        """启动/停止备份任务

        Args:
            name: 备份任务名称
            operation: 操作类型，启动/停止
        """
        # 使用BasePage中的通用下拉菜单选项点击方法
        self.click_action(name, operation)
        # 断言弹窗成功
        self.assert_popup_success(f"{operation}备份任务成功")

        self.logger.info(f"成功{operation}备份任务{name}")

    @submenu("任务")
    def backup_edit_name(self, name: str, new_name: str):
        """修改名称

        Args:
            name: 备份任务名称
            new_name: 新名称
        """

        # 使用BasePage中的通用下拉菜单选项点击方法
        if self.get_row_data(name).get("状态") == "已启动":
            self.backup_start_stop(name, "停止")

        self.click_action(name, "修改名称")

        self.get_by_label("修改名称").get_by_role("textbox").fill(new_name)

        self.dialog_confirm.click()

        # 等待详情页面加载完成
        self.logger.info(f"操作完成: 修改名称 {name} 为 {new_name}")

    @submenu("任务")
    def backup_edit_vm(self, name: str, vms: list, attach: bool=True, vm_type: str="弹性云服务器"):
        """修改名称

        Args:
            name: 备份任务名称
            vms: 虚机名称列表
            attach: 添加虚机
            vm_type: 虚机类型
        """

        # 使用BasePage中的通用下拉菜单选项点击方法
        if self.get_row_data(name).get("状态") == "已启动":
            self.backup_start_stop(name, "停止")
        self.click_action(name, "管理云服务器")

        # 选择虚机类型
        if vm_type != "弹性云服务器":
            self.get_by_placeholder("请选择").nth(3).click()
            self.locator("li").filter(has_text=vm_type).nth(2).click()

        # 添加/删除虚机
        if attach:
            self._add_servers(vms)
        else:
            self._remove_servers(vms)

        # 确认
        self.dialog_confirm.click()

        self.logger.info(f"操作完成: {name}管理云服务器{'添加' if attach else '删除'}云服务器{vms}成功")

    @submenu("任务")
    def backup_edit_policy(self, name: str, policy: dict):
        """修改策略

        Args:
            name: 策略名称
            policy: 策略信息
        """
        if self.get_row_data(name).get("状态") == "已启动":
            self.backup_start_stop(name, "停止")
        self.click_action(name, "修改策略")
        # 配置备份策略
        policy_type = policy.get("策略类型", "自定义策略")
        time_policy = policy.get("时间策略", {})
        speed_policy = policy.get("限速策略", {})
        storage_policy = policy.get("存储策略", {})
        retention_policy = policy.get("保留策略", {})
        thread_policy = policy.get("高级策略", {})

        self._backup_policy(
            policy_type,
            time_policy,
            speed_policy,
            storage_policy,
            retention_policy,
            thread_policy
        )
        self.get_by_text("确认修改").click()

    def backup_get_cur_target(self, name: str) -> str:
        """获取当前迁移目标

        Args:
            name: 迁移任务名称
        """
        self.backup_to_details(name)
        cur_target = self.get_by_text("目标节点").locator("xpath=../following-sibling::div/span").inner_text()
        self.backup_back_to_list()
        return cur_target

    @submenu("任务")
    def backup_migrate(self, name: str, method: str = "自动", target: str = None):
        """
        备份任务迁移
        Args:m
            name: 备份任务名称
            method: 迁移方式
            target: 目标项目
        """
        self.click_action(name, "迁移")
        if method != "自动":
            self.get_by_role("radio", name=method).click()
            self.get_by_placeholder("请选择迁移节点").click()
            self.locator("li").filter(has_text=target).click()
        self.dialog_confirm.click()
        logger.info(f"操作完成: 备份任务{name} {method}迁移 {target}")

    @submenu("任务")
    def exec_backup(self, name: str, method: str):
        """
        执行增量备份
        Args:
            name: 备份任务名称
            method: 执行方式: 全量备份/增量备份
        """

        if self.get_row_data(name).get("状态") != "已启动":
            self.backup_start_stop(name, "启动")
            self.assert_status(name, "已启动")
        self.click_action(name, method)
        logger.info(f"操作完成: 备份任务{name} {method}")

    @submenu("任务")
    def backup_reset_task(self, name: str):
        """
        重置备份任务
        Args:
            name: 备份任务名称
        """
        if self.get_row_data(name).get("状态") != "备份中":
            pytest.skip(f"备份任务{name}状态不是备份中，无法重置")

        self.click_action(name, "重置任务")

    def _click_batch_operation_option(self, operation: str):
        """点击批量操作选项

        Args:
            operation: 操作类型
        """
        try:
            operation_btn = self.get_by_role("button", name="更多操作")
            dropdown_id = operation_btn.evaluate("element => element.getAttribute('aria-controls')")
            if dropdown_id:
                specific_dropdown = self.page.locator(f"#{dropdown_id}")
                batch_option = specific_dropdown.get_by_text(operation, exact=True)
                if batch_option.is_visible() and batch_option.is_enabled():
                    batch_option.click()
                    return
                else:
                    raise Exception(f"{operation}选项不可见或不可用")
            else:
                raise Exception("未找到aria-controls属性")
        except Exception as e:
            # 方法2: 备用方案 - 找到最后一个可见的下拉菜单
            logger.warning(f"主要方法失败，使用备用方案: {e}")
            dropdown_menus = self.page.locator('[id^="dropdown-menu-"]')

            # 从后往前遍历，找到最后一个可见的下拉菜单
            for i in range(dropdown_menus.count() - 1, -1, -1):
                menu = dropdown_menus.nth(i)
                if menu.is_visible():
                    option = menu.get_by_text(operation, exact=True)
                    if option.count() > 0 and option.is_visible() and option.is_enabled():
                        option.click()
                        return
            raise Exception(f"所有方法都失败，未找到可用的{operation}选项")

    @submenu("任务")
    def backup_batch_operation(self, names: list, operation: str):
        """
        批量操作
        Args:
            names: 备份任务名称
            operation: 操作类型
        """
        self.select_rows_by_names(names)
        self.get_by_role("button", name="更多操作").click()
        self._click_batch_operation_option(operation)
        if operation == "删除":
            self.dialog_confirm.click()
        logger.info(f"操作完成: 批量操作{operation}备份任务{names}")

    def backup_search(self, keyword):
        """
        备份任务名称
        Args:
            keyword: 搜索关键字
        """
        locs = [
            self.get_by_role("textbox", name="搜索（备份任务名称）"), # 备份任务搜索
            self.get_by_role("textbox", name="搜索（任务名称）"), # 恢复任务/回收 搜索
        ]
        self._find_element(locs, "搜索框").fill(keyword)
        self._btn_search.click()

    @submenu("回收")
    def backup_delete(self, names):
        """删除回收中的备份资源，支持单个和批量操作

        Args:
            names: 备份名称（字符串）或备份名称列表（列表）
        """
        if isinstance(names, list):
            # 批量操作模式
            self.select_rows_by_names(names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(names, "删除")

        # 使用BasePage中的通用确认按钮
        self.dialog_confirm.click()

        # 等待操作完成

    @submenu("回收")
    def backup_recovery(self, name):
        """恢复回收中的备份资源，支持单个

        Args:
            name: 备份名称（字符串）或备份名称列表（列表）
        """

        self.click_action(name, "恢复")

        self.assert_popup_success(f"{name}任务找回成功")
        logger.info(f"恢复备份资源请求已提交: {name}")

    @submenu("备份数据")
    def backup_data_search(self, keyword, s_type: str = None):
        """
        搜索实例的备份数据
        Args:
            keyword: 搜索关键字
            s_type: 备份数据状态
        """

        if s_type:
            self.get_by_placeholder("请选择").click()
            self.get_by_text(s_type).click()
        self.get_by_placeholder("按实例名搜索").fill(keyword)
        self._btn_search.click()

    def _get_tree_item(self, server_name: str):
        """获取虚机的备份数据节点"""
        # 改进定位器：确保定位到包含服务器名称的树节点
        tree_item = self.get_by_role("treeitem", name=re.compile(rf".*{re.escape(server_name)}")).first
        child_nodes = tree_item.locator(".el-tree-node__children .custom-tree-node")
        self._ensure_tree_item_expanded(tree_item, child_nodes, server_name)
        return child_nodes

    def _ensure_tree_item_expanded(self, tree_item, child_nodes, server_name: str):
        """确保树节点已展开并且子节点已经加载出来"""
        for attempt in range(3):
            class_attr = tree_item.get_attribute("class") or ""
            child_count = child_nodes.count()
            if "is-expanded" in class_attr and child_count > 0:
                if attempt > 0:
                    logger.info(f"备份数据节点展开成功: {server_name}，共找到 {child_count} 个子节点")
                else:
                    logger.debug(f"备份数据节点已展开，跳过点击: {server_name}")
                return

            if "is-expanded" in class_attr:
                self.page.wait_for_timeout(500)
                continue

            expand_icon = tree_item.locator(".el-tree-node__expand-icon").first
            expand_icon_class = expand_icon.get_attribute("class") or ""
            if expand_icon.is_visible() and "is-leaf" not in expand_icon_class:
                expand_icon.click(force=True)
            else:
                tree_item.locator(".el-tree-node__content").first.click(force=True)
            self.page.wait_for_timeout(500)

        logger.warning(f"备份数据节点可能未完全展开: {server_name}，当前找到 {child_nodes.count()} 个子节点")

    def _is_tree_node_checked(self, child_node) -> bool:
        """判断树节点是否已勾选"""
        tree_item = child_node.locator("xpath=ancestor::*[@role='treeitem'][1]")
        if (tree_item.get_attribute("aria-checked") or "").lower() == "true":
            return True

        checked_locators = [
            tree_item.locator(".el-checkbox__input.is-checked").first,
            tree_item.locator("label.is-checked").first,
            tree_item.locator("input[type='checkbox']:checked").first,
        ]
        return any(locator.count() > 0 for locator in checked_locators)

    def _click_tree_node_checkbox(self, child_node, node_text: str) -> bool:
        """勾选树节点，兼容不同 DOM 结构"""
        if self._is_tree_node_checked(child_node):
            logger.info(f"备份数据节点已处于勾选状态: {node_text}")
            return True

        tree_item = child_node.locator("xpath=ancestor::*[@role='treeitem'][1]")
        candidates = [
            ("同级label", child_node.locator("xpath=../label").first),
            ("同级checkbox", child_node.locator("xpath=../label//span[contains(@class,'el-checkbox__inner')]").first),
            ("树节点label", tree_item.locator(".el-tree-node__content label.el-checkbox").first),
            ("树节点checkbox", tree_item.locator(".el-tree-node__content .el-checkbox__inner").first),
        ]

        for name, checkbox in candidates:
            if checkbox.count() == 0:
                continue

            try:
                checkbox.scroll_into_view_if_needed()
            except Exception:
                pass

            try:
                if not checkbox.is_visible():
                    continue
                checkbox.click(force=True)
                self.page.wait_for_timeout(300)
            except Exception as exc:
                logger.debug(f"勾选备份数据节点失败，定位器[{name}]，节点: {node_text}，原因: {exc}")
                continue

            if self._is_tree_node_checked(child_node):
                logger.info(f"勾选备份数据节点成功，定位器[{name}]，节点: {node_text}")
                return True

        logger.warning(f"未能勾选备份数据节点: {node_text}")
        return False

    def get_backup_data(self, server_name: str):
        """获取虚机的备份数据

        Args:
            server_name: 云服务器名称
        """
        backup_data = []
        self.backup_data_search(server_name)
        child_nodes = self._get_tree_item(server_name)
        count = child_nodes.count()
        if count == 0:
            raise Exception(f"未找到 {server_name} 的备份数据")
        elif count >= 1:
            logger.info(f"找到 {count} 个备份数据节点, 选用最后一个节点")
            child_node = child_nodes.last
            node_text = child_node.inner_text()
            text = node_text.split("\n")[0]
            backup_data.append(text)
        return backup_data

    @submenu("备份数据")
    def backup_data_delete(self, server_name: str, backup_data: str = None):
        """删除备份数据

        Args:
            server_name: 云服务器名称
            backup_data: 备份数据标识（如时间或名称），用于选择具体的备份点
        """
        # 搜索并选择要恢复的备份实例
        self.backup_data_search(server_name)
        if backup_data:
            child_nodes = self._get_tree_item(server_name)
            count = child_nodes.count()
            logger.info(f"找到 {count} 个备份数据节点")

            if count == 0:
                raise Exception(f"未找到 {server_name} 的备份数据")

            for i in range(count):
                child_node = child_nodes.nth(i)
                node_text = child_node.inner_text().split("\n")[0].strip()
                logger.info(f"检查备份数据节点[{i}]: {node_text}")

                # 检查是否匹配（使用完整文本）
                if backup_data not in node_text:
                    continue

                # 找到目标节点，点击勾选
                if self._click_tree_node_checkbox(child_node, node_text):
                    logger.info(f"已选择备份数据节点: {node_text}")
                    break
            else:
                raise Exception(f"未找到可勾选的匹配备份数据: {backup_data}")
        else:
            checkbox = self.get_by_role("treeitem").filter(has_text=server_name).locator("label span").nth(1)
            checkbox.click(force=True)
            logger.info(f"已选择全部备份数据节点: {server_name}")
        time.sleep(1) # 等待删除按钮状态变为可点击
        self.locator(".cloud-button .cloud-button-btn").filter(has_text="删除").click()
        self.dialog_confirm.click()

    def assert_backup_data(self, server_name: str, status):
        """
        断言备份数据状态
        Args:
            server_name: 实例名称
            status: 备份数据状态, 支持单个或列表
        """
        self.backup_data_search(server_name)

        self.get_by_text(server_name).click()

        # self.get_by_role("group").locator(".custom-tree-node").filter(has_text=f"{server_name}_{time.strftime('%Y%m%d%H%M')}").inner_text()
        # 获取最后一个节点, 一般情况是最后一个节点是最新的备份数据
        actual_status = self.get_by_role("group").locator(".custom-tree-node").filter(has_text=f"{server_name}").last.inner_text()
        if isinstance(status, str):
            status = [status]

        for status in status:
            assert status in actual_status, f"备份数据状态不匹配，预期: {status}, 实际: {actual_status}"


    @submenu("恢复任务")
    def create_resume_task(
            self,
            source_vm: str,
            re_vm: str,
            re_task: str,
            project: str = "默认项目",
            data: dict = None,
            **kwargs
    ):
        """创建恢复任务

        Args:
            source_vm: 备份数据来源的虚机
            re_vm: 恢复虚机
            re_task: 恢复任务名称
            project: 恢复至项目，默认"默认项目"
            data: 恢复任务数据字典，包含中文键：
                - 备份数据: 备份数据标识（可选），用于选择具体的备份点
                - 恢复配置: 恢复配置字典，按页面模块划分（中文键）：
                    - 恢复至项目: 项目名称
                    - 基本设置: 实例名称、集群
                    - 网络设置: 网络、子网
                    - 存储配置: 云硬盘模式
                    - 规格配置: 规格
                    - 管理配置: 登录密码、VNC密码
                    - 恢复方式: 限速大小、限速单位、线程数量（可选）
            **kwargs: 其他参数，用于覆盖data中的配置
        """
        # 设置默认数据
        data = data or {}

        # 从字典中使用中文键获取值，kwargs可覆盖
        backup_data = kwargs.get("backup_data") or data.get("备份数据")
        resume_config = kwargs.get("resume_config") or data.get("恢复配置", {})
        re_method = kwargs.get("re_method") or data.get("恢复方式", {})
        basic_settings = resume_config.get("基本设置", {})

        # 点击新建恢复任务按钮
        self.get_by_text("新建恢复任务").click()

        # 第一步: 搜索并选择要恢复的实例
        self._search_and_select_backup_server(source_vm, backup_data)
        self._click_next_step()

        # 第二步:
        # (1) 配置恢复类型
        resume_type = resume_config.get("恢复类型", "新建资源")
        if resume_type != "新建资源":
            self._select_backup_type(resume_type)

        # (2) 配置恢复至项目
        resume_project = (
            resume_config.get("恢复至项目")
            or basic_settings.get("项目")
            or kwargs.get("project")
            or project
        )

        if resume_type == "新建资源":
            self._config_resume_project(resume_project)

            # (3) 配置基本设置（实例名称、集群）
            self._config_basic_settings(re_vm, basic_settings)

            # (4) 配置网络设置（网络、子网）
            network_settings = resume_config.get("网络设置", {})
            self._config_network_settings(network_settings)

            # (5) 配置存储配置（云硬盘模式）
            storage_settings = resume_config.get("存储配置", {"存储类型": Config.get('stor'), "云硬盘模式": "精简置备"})
            if storage_settings:
                self._config_storage_settings(storage_settings)

            # (6) 配置规格配置
            flavor_settings = resume_config.get("规格配置", {})
            self._config_flavor_settings(flavor_settings)

            # (7) 配置管理配置（登录密码、VNC密码）
            management_settings = resume_config.get("管理配置", {})
            self._config_management_settings(management_settings)

        self._click_next_step()

        # 第四步: 恢复方式（限速、线程数）
        if re_method:
            self._config_advanced_settings(re_method)

        self._click_next_step()

        # 第五步: 设置任务名称并创建
        self._set_resume_task_name(re_task)
        logger.info(f"恢复任务{re_task}已提交")

    def _select_backup_type(self, backup_type: str):
        """选择备份类型

        Args:
            backup_type: 备份类型
        """
        loc = self.get_by_role("radio", name=f"{backup_type} 󦕟")
        if loc.is_enabled() and not loc.is_checked():
            loc.click()
        logger.info(f"选择备份类型: {backup_type}")

    def _config_resume_project(self, project: str = "默认项目"):
        """配置恢复至项目"""
        self.get_by_placeholder("请选择项目").click()
        locs = [
            self.locator("li").filter(has_text=re.compile(rf"^{re.escape(project)}$")).first,
            self.get_by_role("listitem").filter(has_text=project).first,
            self.get_by_text(project, exact=True).last
        ]
        self._find_element(locs, "恢复至项目").click()
        logger.info(f"选择恢复至项目: {project}")

    def _config_basic_settings(self, re_vm: str, config: dict):
        """配置基本设置

        Args:
            config: 基本设置字典
                - 实例名称: 恢复后的实例名称
                - 集群: 集群名称
        """
        cluster = config.get("集群", "Autotest")

        # 选择集群
        self.get_by_placeholder("请选择集群").click()
        locs = [
            self.get_by_text("Autotest", exact=True).nth(1),
            self.locator("li").filter(has_text=re.compile(rf"^{cluster}$")).nth(1)
        ]
        self._find_element(locs, "集群").click()
        logger.info(f"选择集群: {cluster}")

        # 填写实例名称
        self.get_by_placeholder("请输入名称").fill(re_vm)
        logger.info(f"设置实例名称: {re_vm}")

    def _config_network_settings(self, config: dict):
        """配置网络设置

        Args:
            config: 网络设置字典
                - 网络: 网络名称
                - 子网: 子网名称
        """
        # 使用中文键从字典获取值
        network = config.get("网络", "Autotest")
        subnet = config.get("子网", "Autotest(1")
        allocation_mode = config.get("分配模式", {"方式": "自动分配"})
        # 选择网络
        self.get_by_placeholder("请选择网络").click()
        locs = [
            self.get_by_text("Autotest", exact=True).nth(1),
            self.locator("li").filter(has_text=re.compile(rf"^{network}$")).nth(1)
        ]
        self._find_element(locs, "网络").click()

        # 选择子网
        self.get_by_placeholder("请选择子网").click()
        self.locator("li").filter(has_text=subnet).click()

        # 选择分配模式
        text = None

        allocation_type = allocation_mode.get("方式")
        if allocation_mode and allocation_type != "自动分配":
            ip_type = allocation_mode.get("IP类型")
            ip = allocation_mode.get("IP")
            mac = allocation_mode.get("MAC")

            # 选择分配模式
            self.get_by_placeholder("请选择分配模式").click()
            self.locator("li").filter(has_text=allocation_type).click()

            # 选择ip分配模式
            self.get_by_role("radio", name=ip_type).click()
            if allocation_type == "手动输入":
                self.get_by_placeholder("请输入IP地址").fill(ip)
            else:
                self.get_by_label("手动分配").locator("form div").filter(has_text="IP快速选择 手动输入").get_by_placeholder("请选择").click()
                self.locator("li").filter(has_text=ip).click()

            # 填写mac
            if mac:
                locs = [
                    self.get_by_placeholder("请按照6c:88:14:dd:25:59的格式输入"),
                    self.get_by_text("MAC", exact=True).locator("xpath=./following-sibling::div//input")
                ]
                self._find_element(locs, "MAC").fill(mac)
            # 点击确定
            self.get_by_label("手动分配").get_by_text("确定").click()
            text = f"ip分配方式: {ip_type},ip: {ip},mac: {mac}"

        # 分配公网ip
        pub_net = config.get("分配公网IP", None)
        if pub_net:
            self.get_by_text("分配公网IP:").click()
            self.get_by_placeholder("请选择公网IP").click()
            self.locator("li").filter(has_text=pub_net).click()

        # 设置安全组
        security_group = config.get("安全组", None)
        if security_group and security_group != "default":
            locs = [
                self.get_by_placeholder("请选择安全组"),
                self.locator("div").filter(has_text=re.compile(r"^default$")).nth(1),
                self.locator("#cloud-container-content").get_by_text("安全组").locator("xpath=../following-sibling::div/div")
            ]
            self._find_element(locs, "安全组").click()
            self.locator("li").filter(has_text=security_group).click()

        logger.info(f"已配置网络: {network},子网: {subnet},分配模式: {allocation_mode.get('方式') }{text},分配公网ip: {pub_net},安全组: {security_group}")

    def _config_storage_settings(self, config: dict):
        """配置存储配置

        Args:
            config: 存储配置字典
                - 存储类型: "xstor" "ustor"等
                - 云硬盘模式: "精简置备" 或 "厚置备"
        """
        # 当前实现: 默认全部盘存储类型一致，数据盘云硬盘模式一致
        disk_type = config.get("存储类型")
        disk_mode = config.get("云硬盘模式")

        # 获取所有数据盘行
        disk_rows = self.locator(".form-box").filter(has_text="存储配置").locator(".el-table__body-wrapper tbody tr")
        count = disk_rows.count()

        for i in range(count):
            row = disk_rows.nth(i)
            row_text = row.inner_text()

            # 提取磁盘名称
            disk_name_match = re.search(r'[sv]d[a-z]', row_text, re.IGNORECASE)
            if not disk_name_match:
                continue
            disk_name = disk_name_match.group().lower()

            # 点击存储类型下拉框
            type_select = row.get_by_placeholder("请选择").first
            current_type = type_select.input_value()
            if disk_type in current_type:
                logger.info(f"磁盘 {disk_name} 存储类型已是 {current_type}")
            else:
                if type_select.is_visible():
                    type_select.click()
                    self.locator("li").filter(has_text=disk_type).last.click()
                    logger.info(f"设置磁盘 {disk_name} 存储类型为: {disk_type}")

            # 系统盘（vda/sda）不修改云硬盘模式，数据盘需要修改
            if disk_name not in ["vda", "sda"]:
                # 点击云硬盘模式下拉框
                mode_select = row.get_by_placeholder("请选择").nth(1)
                current_mode = mode_select.input_value()
                if disk_mode in current_mode:
                    logger.info(f"磁盘 {disk_name} 云硬盘模式已是 {current_mode}")
                else:
                    if mode_select.is_visible():
                        mode_select.click()
                        self.get_by_text(disk_mode).nth(2).click()
                        logger.info(f"设置磁盘 {disk_name} 云硬盘模式为: {disk_mode}")

        logger.info(f"存储配置完成: {disk_type}, {disk_mode}")

    def _config_flavor_settings(self, config: dict):
        """配置规格配置

        Args:
            config: 规格配置字典
                - 规格: 规格名称，如"ecs.c6.Autotest"
        """
        # 使用中文键从字典获取值
        flavor = config.get("规格", "ecs.c6.Autotest")
        flavor_type = flavor.split(".")[1][0]
        # 搜索并选择规格
        self.search(flavor)
        if flavor_type == "c":
            finally_type = "计算型"
            self.get_by_text(finally_type).click()
        elif flavor_type == "m":
            finally_type = "内存型"
            self.get_by_text(finally_type).click()
        elif flavor_type == "s":
            finally_type = "通用型"
            self.get_by_text(finally_type).click()
        else:
            logger.error(f"未知的规格类型: {flavor}")
        logger.info(f"规格类型分类: {finally_type}")

        # 选择指定规格
        locs = [
            self.get_by_role("row", name=re.compile(f".*{flavor}.*")).get_by_role("radio"),
            self.get_by_role("row").filter(has_text=re.compile(rf"{re.escape(flavor)}")).get_by_role("radio").first
        ]
        self._find_element(locs, "规格").click()
        logger.info(f"已选择规格类型: {flavor}")

    def _config_management_settings(self, config: dict):
        """配置管理配置

        Args:
            config: 管理配置字典
                - 登录密码: 登录密码
                - VNC密码: VNC密码
        """
        login_type = config.get("登录方式", "密码登录")
        login_password = config.get("登录密码", "admin1234@sugon")
        vnc_password = config.get("VNC密码", "sugon@20")
        login_key = config.get("密钥对", None)

        # 选择登录方式
        self.get_by_role("radio", name=login_type).click()

        # 填写密码/选择密钥对
        if login_type == "密钥对登录":
            if not login_key:
                raise ValueError("密钥对登录需要提供login_key参数")
            self._set_login_key(login_key)

        elif login_type == "密码+密钥对":
            self._set_login_pwd(login_password)
            self._set_login_key(login_key)

        else:
            self._set_login_pwd(login_password)

        # 设置VNC密码
        if vnc_password:
            self.get_by_placeholder("VNC密码最长为8位").fill(vnc_password)
            locs = [
                self.locator("input[type=\"password\"]").last,
                self.get_by_text("确认VNC密码").locator("xpath=./following-sibling::div//input"),
            ]
            self._find_element(locs, "确认VNC密码").fill(vnc_password)

        logger.info("管理配置完成")

    def _set_login_pwd(self, login_pwd):
        """设置登录密码"""
        self.get_by_placeholder("请输入密码").fill(login_pwd)
        locs = [
            self.locator("input[type=\"password\"]").nth(1),
            self.get_by_text("确认登录密码").locator("xpath=./following-sibling::div//input"),
            self.locator("div").filter(has_text=re.compile(r"^确认登录密码$")).get_by_role("textbox")
        ]
        self._find_element(locs, "确认登录密码").fill(login_pwd)
        logger.info(f"已设置登录密码")

    def _set_login_key(self, login_key):
        """设置密钥对"""
        locs = [
            self.locator("form div").filter(
                has_text="管理配置 登录方式 密码登录 密钥对登录 密码+密钥对 密钥对 whq001whq002sr001 VNC密码 随机生成")
            .get_by_placeholder("请选择"),
            self.get_by_text("密钥对", exact=True).locator("xpath=../following-sibling::div//input")
        ]
        self._find_element(locs, "密钥对").click()
        self.locator("li").filter(has_text=login_key).click()
        logger.info(f"已选择密钥对: {login_key}")

    def _config_advanced_settings(self, config: dict):
        """配置高级配置（可选）

        Args:
            config: 高级配置字典
                - 限速大小: 限速大小
                - 限速单位: 限速单位，如"MiB/s"
                - 线程数量: 线程数量
        """
        speed_limit = config.get("速度")
        speed_unit = config.get("单位", "MiB/s")
        thread_count = config.get("线程数量")

        # 配置限速策略
        # 转换为浮点数
        try:
            speed_limit = float(speed_limit)
        except (ValueError, TypeError):
            raise ValueError(f"速度值无效: {speed_limit}")
        speed_value = speed_limit

        # 规则1: 如果传入的unit是"KiB/s"且speed大于1000，转换为MiB/s
        if speed_unit == "KiB/s" and speed_limit > 1000:
            logger.info(f"速度 {speed_limit} KiB/s 大于1000，自动转换为 MiB/s")
            speed_unit = "MiB/s"
            # 速度除以1024
            converted_speed = speed_limit / 1024
            # 如果是整数，不显示小数；否则保留两位小数
            if converted_speed == int(converted_speed):
                speed_value = int(converted_speed)
            else:
                speed_value = round(converted_speed, 2)
            logger.info(f"转换后速度: {speed_value} {speed_unit}")

        # 规则2: 如果unit是"MiB/s"，speed不允许大于1000
        elif speed_unit == "MiB/s" and speed_limit > 100:
            raise ValueError(f"MiB/s 单位下速度不允许大于100，当前值: {speed_limit}")
        time.sleep(1) # 等待下一步的页面加载完成(无loading状态)
        if speed_unit:
            self.locator("#cloud-container-content").get_by_role("textbox").click()
            self.get_by_text("MiB/s").click()
            logger.info(f"设置限速单位: {speed_unit}")
        if speed_value:
            locs = [
                self.locator("form div").filter(has_text="限速策略 速度").get_by_role("spinbutton"),
                self.locator("form div").filter(has_text="限速策略 速度 KiB/s MiB/s").get_by_role("spinbutton"),
                self.get_by_text("速度").locator("xpath=../following-sibling::div/div//input")
            ]
            self._find_element(locs, "速度").fill(str(speed_value))
            logger.info(f"设置限速大小: {speed_value}")

        # 配置线程数量
        if thread_count:
            locs = [
                self.get_by_text("线程数量").locator("xpath=../following-sibling::div//input"),
                self.locator("form div").filter(has_text="高级策略 线程数量").get_by_role("spinbutton")
            ]
            thread_input = self._find_element(locs, "线程数量")
            thread_input.fill(thread_count)
            logger.info(f"设置线程数量: {thread_count}")

    def _search_and_select_backup_server(self, server_name: str, backup_data: str = None):
        """搜索并选择要恢复的备份实例

        Args:
            server_name: 云服务器名称
            backup_data: 备份数据标识（如时间或名称），用于选择具体的备份点
        """
        # 输入实例名搜索
        self.get_by_placeholder("按实例名搜索").fill(server_name)
        self._btn_search.click()
        logger.info(f"搜索备份实例: {server_name}")

        # 获取所有子节点
        child_nodes = self._get_tree_item(server_name)
        count = child_nodes.count()
        logger.info(f"找到 {count} 个备份数据节点")

        if count == 0:
            raise Exception(f"未找到 {server_name} 的备份数据")

        # 确定遍历范围
        if backup_data:
            # 传入了backup_data，从头到尾查找匹配的
            indices = range(count)
            target_desc = f"匹配'{backup_data}'"
        else:
            # 没传入backup_data，从尾到头找最后一个可勾选的
            indices = range(count - 1, -1, -1)
            target_desc = "最后一个可勾选"

        for i in indices:
            child_node = child_nodes.nth(i)
            # 处理节点文本，去除图标字符和空格
            node_text = child_node.inner_text().split("\n")[0].strip()
            logger.info(f"检查备份数据节点[{i}]: {node_text}")

            # 如果传入了backup_data，检查是否匹配
            if backup_data and backup_data not in node_text:
                continue

            # 找到目标节点，点击勾选
            if self._click_tree_node_checkbox(child_node, node_text):
                logger.info(f"选择{target_desc}备份数据，节点[{i}]: {node_text}")
                return

        # 没找到
        if backup_data:
            raise Exception(f"未找到可勾选的匹配备份数据: {backup_data}")
        else:
            raise Exception(f"未找到可勾选的备份数据，共检查 {count} 个节点")

    def _set_resume_task_name(self, task_name: str):
        """设置恢复任务名称并提交创建"""
        self.get_by_placeholder("请输入任务名称").fill(task_name)
        self.get_by_text("立即创建").click()

    @submenu("恢复任务")
    def delete_resume_task(self, task_names):
        """删除恢复任务"""
        if isinstance(task_names, list):
            # 批量操作模式
            self.select_rows_by_names(task_names)

            # 点击批量删除按钮
            self.btn_batch_delete.click()
        else:
            # 单个操作模式
            self.click_action(task_names, "删除")
        self.dialog_confirm.click()

    @submenu("恢复任务")
    def assert_resume_task_details(self, name, details: dict, tab="详情"):
        """
        验证恢复任务详情
        Args:
            name: 恢复任务名称
            details: 恢复任务配置字典
        """
        self.get_by_role("cell", name=name).locator("span").click()
        if tab == "详情":
            if "速度" in details and "单位" in details:
                speed_value = float(details["速度"])
                unit = details["单位"]
                new_details = details.copy()
                del new_details["速度"]
                del new_details["单位"]

                # 格式化为保留3位小数
                new_details["限速策略"] = f"{speed_value:.3f} {unit}"
                details = new_details
            for k, v in details.items():
                label_loc = self.get_by_text(k, exact=True)
                loc = label_loc.locator("xpath=../following-sibling::div/span")
                expect(loc).to_contain_text(v)
                self.logger.info(f"验证成功 {k}: {v}")
        else:
            self.get_by_role("tab", name=tab).click()
            for k, v in details.items():
                # if k in ["恢复进度", "执行结果"]:
                #     self.assert_column_all_match(v, k)
                # else:
                self.assert_list_contain(v, k)
                self.logger.info(f"验证成功 {k}: {v}")
