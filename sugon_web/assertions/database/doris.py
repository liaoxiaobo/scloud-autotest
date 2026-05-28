class DorisAssertionMixin:
    """Doris 数据库业务断言 Mixin。

    验证数据库列表中存在性等。
    属于 L2 Business 层断言。
    """

    def assert_database_exist(self, db_name: str):
        """验证 Doris 数据库列表中存在指定前缀的数据库。

        注意：调用此方法前需要已经在数据库 Tab 页面。

        Args:
            db_name: 数据库名前缀。
        """
        self.logger.info(f"检查是否存在以前缀 '{db_name}' 开头的数据库")

        # 等待页面加载完成

        # 定位所有数据库名称
        db_elements = self.locator("span.key-name")

        # 等待至少出现一个数据库（避免 count 瞬时为 0）
        db_elements.first.wait_for(state="visible", timeout=30000)

        # 提取所有数据库名称
        db_list = []
        for i in range(db_elements.count()):
            db_text = db_elements.nth(i).inner_text().strip()
            db_list.append(db_text)
            self.logger.debug(f"第{i + 1}个数据库: {db_text}")

        self.logger.info(f"获取到的数据库列表共 {len(db_list)} 个: {db_list}")

        # 前缀匹配
        matched_dbs = [db for db in db_list if db.startswith(db_name)]

        if matched_dbs:
            self.logger.info(f"匹配到数据库（前缀匹配）: {matched_dbs}")
        else:
            assert False, (
                f"[ListAssertion] Doris 数据库列表 | 不存在性校验失败 | "
                f"期望: 存在以 '{db_name}' 开头的数据库 | "
                f"实际: 未找到 | 数据库列表: {db_list}"
            )
