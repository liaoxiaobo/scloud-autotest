from sugon_web.common.playwright import expect


class ListAssertionMixin:
    """列表页断言 Mixin。

    验证列表页中的资源存在性、字段值、排序、分页等。
    属于 L2 Business / L3 Consistency 层断言。
    """

    def assert_list_contain(self, keyword, column_name="名称", exact_match=True):
        """断言列表中存在包含指定关键字的记录。

        通过 get_column_data 精确读取指定列的数据进行匹配，
        避免全局行选择器在多表格页面上的误判。

        Args:
            keyword: 要搜索的关键字（通常为资源名称）。
            column_name: 要匹配的列名，默认"名称"。
            exact_match: 是否精确匹配，默认 True。
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

        assert matched, (
            f"[ListAssertion] 列表 | 存在性校验失败 | "
            f"期望: {match_description} | 关键词: '{keyword}' | 实际列数据: {column_data}"
        )
        self.logger.info(f"断言通过: 列表包含 '{keyword}' (列: {column_name})")

    def assert_list_not_contain(self, keyword, column_name="名称", exact_match=True):
        """断言列表中不存在包含指定关键字的记录。

        通过 get_column_data 精确读取指定列的数据进行匹配，
        列不存在或为空时视为不包含。

        Args:
            keyword: 要排除的关键字。
            column_name: 要匹配的列名，默认"名称"。
            exact_match: 是否精确匹配，默认 True。
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

        assert not matched, (
            f"[ListAssertion] 列表 | 不存在性校验失败 | "
            f"期望: 不{match_description} | 关键词: '{keyword}' | 实际列数据: {column_data}"
        )
        self.logger.info(f"断言通过: 列表不包含 '{keyword}' (列: {column_name})")

    def assert_deleted(self, resource_names, timeout=300, refresh=False, refresh_interval=5):
        """断言资源已从列表中删除（不存在）。

        使用 get_by_role 精确匹配行并断言不可见，
        避免全局选择器在多表格页面上的误判。

        Args:
            resource_names: 资源名称或名称列表。
            timeout: 最长等待秒数，默认 300。
            refresh: 是否自动刷新列表等待，默认 False。
            refresh_interval: 刷新间隔秒数，默认 5。
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

                        except Exception:
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
                f"[ListAssertion] 资源 | 删除验证失败 | "
                f"期望: 已从列表删除 | 实际: 仍存在 | 资源: {', '.join(failed_resources)}"
            )

    def assert_row_contains(self, name, expected_data, timeout=300):
        """断言指定名称的行中包含预期的数据。

        Args:
            name: 行标识（通常为资源名称）。
            expected_data: 期望行中包含的文本数据。
            timeout: 最长等待秒数，默认 300。
        """
        row = self.get_row_by_name(name)
        expect(row).to_contain_text(expected_data, timeout=timeout * 1000, use_inner_text=True)
        self.logger.info(f"断言通过: 行 '{name}' 包含 '{expected_data}'")
