import time
from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from sugon_web.common.types import ResourceNames


class AssertionsMixin:
    """页面断言 Mixin。

    提供弹窗消息断言、列表内容校验、资源状态等待、删除验证等能力。
    设计为与 ElementsMixin、TablesMixin、WaitsMixin 组合使用。
    """

    def assert_popup_success(self, text: str | None = None, timeout: int = 10) -> None:
        """断言顶部成功弹窗出现并消失。

        通过检查弹窗 CSS 类名（el-message--success）判断类型。
        text 参数使用包含匹配（to_contain_text），不需要与弹窗文本完全一致。

        Args:
            text: 期望弹窗中包含的文本片段（可选，包含匹配）
            timeout: 等待弹窗出现的超时时间（秒）
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        popup_text = popup.inner_text().strip()
        is_success = popup.evaluate(
            "element => element.parentElement.classList.contains('el-message--success')"
        )

        if not is_success:
            raise AssertionError(f"预期操作成功，但实际失败。弹窗文本: {popup_text}")

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)

    def assert_popup_error(self, text: str | None = None, timeout: int = 5) -> None:
        """断言顶部错误弹窗出现并消失。

        通过检查弹窗 CSS 类名（el-message--error）判断类型。
        text 参数使用包含匹配（to_contain_text），不需要与弹窗文本完全一致。

        Args:
            text: 期望弹窗中包含的文本片段（可选，包含匹配）
            timeout: 等待弹窗出现的超时时间（秒）
        """
        timeout_ms = timeout * 1000
        popup = self.popup
        expect(popup).to_be_visible(timeout=timeout_ms)

        popup_text = popup.inner_text().strip()
        is_error = popup.evaluate(
            "element => element.parentElement.classList.contains('el-message--error')"
        )

        if not is_error:
            raise AssertionError(f"预期操作失败，但实际成功或其他状态。弹窗文本: {popup_text}")

        if text:
            expect(popup).to_contain_text(text)

        expect(popup).not_to_be_visible(timeout=timeout_ms)

    def assert_list_contain(self, keyword: str, column_name: str = "名称", exact_match: bool = True) -> None:
        """
        公共方法: 验证指定列中是否包含特定关键字

        Args:
            keyword: 关键字
            column_name: 列名，默认为"名称"
            exact_match: 匹配模式（True为精准匹配，False为模糊匹配）

        Raises:
            AssertionError: 当没有找到匹配项时抛出异常
        """
        self.logger.info(f"检查列 '{column_name}' 中是否包含关键字 '{keyword}'")

        column_data = self.get_column_data(column_name)

        if not column_data:
            self.logger.warning(f"列 '{column_name}' 没有数据或不存在")
            assert False, f"列 '{column_name}' 没有数据或不存在"

        if exact_match:
            matched = any(keyword == item for item in column_data)
            match_description = "包含与关键词完全相等的数据"
        else:
            matched = all(keyword in item for item in column_data)
            match_description = "包含关键词的数据"

        assert matched, f"验证失败：{match_description}。关键词: '{keyword}'，实际列数据: {column_data}"

    def assert_list_not_contain(self, keyword: str, column_name: str = "名称", exact_match: bool = True) -> None:
        """
        公共方法: 验证指定列中不包含特定关键字

        Args:
            keyword: 关键字
            column_name: 列名，默认为"名称"
            exact_match: 匹配模式（True为精准匹配，False为模糊匹配）

        Raises:
            AssertionError: 当找到匹配项时抛出异常
        """
        self.logger.info(f"检查列 '{column_name}' 中是否不包含关键字 '{keyword}'")

        try:
            column_data = self.get_column_data(column_name)
        except Exception:
            self.logger.info(f"列 '{column_name}' 不存在或无数据，视为不包含关键字 '{keyword}'")
            return

        if not column_data:
            self.logger.info(f"列 '{column_name}' 为空，视为不包含关键字 '{keyword}'")
            return

        if exact_match:
            matched = any(keyword == item for item in column_data)
            match_description = "包含与关键词完全相等的数据"
        else:
            matched = any(keyword in item for item in column_data)
            match_description = "包含关键词的数据"

        assert not matched, f"验证失败：预期不{match_description}。关键词: '{keyword}'，实际列数据: {column_data}"

    def assert_status(self, names: "ResourceNames", status: str = '运行', timeout: int = 300, refresh: bool = False, refresh_interval: int = 5) -> None:
        """
        公共方法：验证页面表格中指定资源的状态是否符合预期，支持单个和批量资源

        Args:
            names: 资源名称（字符串）或资源名称列表（列表）
            status: 期望状态（字符串），所有资源都将使用此状态进行验证
            timeout: 超时时间（秒）
            refresh: 是否需要定期刷新页面，默认为False
            refresh_interval: 刷新间隔时间（秒），默认为5秒，仅在refresh=True时有效
        """
        if isinstance(names, str):
            names = [names]

        failed_resources = []

        for name in names:
            try:
                if not refresh:
                    timeout_ms = timeout * 1000
                    self.wait_for_page_ready()
                    target_row = self.get_row_by_name(name)
                    expect(target_row).to_contain_text(status, timeout=timeout_ms, use_inner_text=True)
                    self.logger.info(f"资源状态验证成功: {name} -> {status}")
                else:
                    start_time = time.time()
                    current_status = "未知"
                    first_check = True

                    while time.time() - start_time < timeout:
                        try:
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查状态: {name}")
                                except Exception as refresh_error:
                                    self.logger.warning(f"刷新页面失败，将继续检查状态: {refresh_error}")

                            first_check = False

                            target_row = self.get_row_by_name(name)
                            current_status = target_row.inner_text()

                            if status in current_status:
                                self.logger.info(f"资源状态验证成功: {name} -> {status}")
                                break

                        except Exception as e:
                            self.logger.debug(f"检查状态时出错: {e}")

                        time.sleep(refresh_interval)
                    else:
                        failed_resources.append(
                            f"{name} (期望状态: {status}, 当前状态: {current_status})")

            except Exception as e:
                self.logger.error(f"资源状态验证失败: {name} -> {status}, 错误: {e}")
                failed_resources.append(f"{name} (期望状态: {status}, 错误: {str(e)})")

        if failed_resources:
            raise AssertionError(f"以下资源状态验证失败: {'; '.join(failed_resources)}")

    def assert_deleted(self, resource_names: "ResourceNames", timeout: int = 300, refresh: bool = False, refresh_interval: int = 5) -> None:
        """
        公共方法：断言资源已从列表中删除（通过表格行不可见来判断），支持单个和批量资源

        Args:
            resource_names: 资源名称（字符串）或资源名称列表（列表）
            timeout: 超时时间（秒）
            refresh: 是否需要定期刷新页面，默认为False
            refresh_interval: 刷新间隔时间（秒），默认为5秒，仅在refresh=True时有效
        """
        if isinstance(resource_names, str):
            resource_names = [resource_names]

        failed_resources = []

        for resource_name in resource_names:
            try:
                if not refresh:
                    timeout_ms = timeout * 1000
                    resource_row = self.get_by_role("row", name=resource_name, exact=True)
                    expect(resource_row).not_to_be_visible(timeout=timeout_ms)
                    self.logger.info(f"资源从列表中删除成功: {resource_name}")
                else:
                    start_time = time.time()
                    first_check = True

                    while time.time() - start_time < timeout:
                        try:
                            if not first_check:
                                try:
                                    self.btn_refresh.click()
                                    self.wait_for_page_ready()
                                    self.logger.debug(f"页面已刷新，继续检查删除状态: {resource_name}")
                                except Exception as refresh_error:
                                    self.logger.warning(f"刷新页面失败，将继续检查删除状态: {refresh_error}")

                            first_check = False

                            resource_row = self.get_by_role("row", name=resource_name, exact=True)

                            if not resource_row.is_visible():
                                self.logger.info(f"资源从列表中删除成功: {resource_name}")
                                break

                        except Exception as e:
                            self.logger.info(f"资源从列表中删除成功: {resource_name}")
                            break

                        time.sleep(refresh_interval)
                    else:
                        failed_resources.append(resource_name)

            except Exception as e:
                self.logger.error(f"资源删除验证失败: {resource_name}, 错误: {e}")
                failed_resources.append(resource_name)

        if failed_resources:
            raise AssertionError(
                f"以下资源删除验证失败（可能仍然存在于列表中）: {', '.join(failed_resources)}"
            )
