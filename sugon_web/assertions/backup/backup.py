from sugon_web.common.components.navigation import submenu
from sugon_web.common.playwright import expect

from sugon_web.assertions.base.format import fmt_assertion_error

class BackupAssertionMixin:
    """备份服务业务断言 Mixin。

    验证备份任务存在性、详情信息、数据状态、恢复任务详情等。
    属于 L2 Business 层断言。
    """

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
        self.logger.info(f"验证备份任务不存在: {task_name}")
        self.assert_deleted(task_name)

    def assert_backup_policy_details(self, name, policy_infos: dict, tab="详情"):
        """验证备份任务详情页面信息

        Args:
            name: 备份任务称
            policy_infos: 需要验证的信息项字典
        """
        self.backup_to_details(name)
        if tab == "详情":
            # 等待"基本信息"标题出现，确保详情页面已加载
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

        self.logger.info(f"备份任务{name} 详情信息 验证成功")

    def assert_backup_data_status(self, server_name: str, status):
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
            assert status in actual_status, fmt_assertion_error(
                "StatusAssertion",
                f"备份数据 '{server_name}'",
                "状态不匹配",
                expected=f"包含 '{status}'",
                actual=f"'{actual_status}'",
            )

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
