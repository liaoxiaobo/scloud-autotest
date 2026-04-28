from sugon_web.common.playwright import expect


class DrawerSelectMixin:
    """抽屉类资源选择组件的通用交互。"""

    def _select_from_named_drawer(
        self,
        drawer_title: str,
        item_name: str,
        reset_first: bool = False,
        open_drawer: bool = True,
    ):
        """在指定抽屉中搜索并按名称精确选择资源。"""
        if open_drawer:
            self.get_by_text(drawer_title).first.click()
            self.page.wait_for_load_state("domcontentloaded")

        drawer = self.locator(f"div[role='dialog'][aria-label='{drawer_title}']:visible")
        expect(drawer).to_be_visible()

        if reset_first:
            reset_btn = drawer.locator(".cloud-table-header-right").get_by_text("重置", exact=True)
            if reset_btn.count() > 0 and reset_btn.first.is_visible():
                reset_btn.first.click()

        search_input = drawer.locator(".cloud-table-header-right input[placeholder='搜索（名称）']")
        if search_input.count() > 0:
            search_input.fill(item_name)
            drawer.locator(".cloud-table-header-right").get_by_text("搜索", exact=True).click()
            self.wait_for_page_ready()

        row = drawer.locator(
            "xpath=.//div[contains(@class,'el-table__body-wrapper')]//tr[.//td[2]//*[normalize-space(text())="
            f"'{item_name}'] or .//td[2][normalize-space(.)='{item_name}']]"
        ).first
        expect(row).to_be_visible(timeout=5000)

        select_locators = [
            drawer.locator(".el-table__fixed .el-radio__inner:visible").first,
            drawer.locator(".el-table__fixed label[role='radio']:visible").first,
            row.locator(".el-radio__inner"),
            row.locator("label[role='radio']"),
            row.get_by_role("radio"),
            row.locator("td").nth(1),
            row,
        ]
        confirm_btn = drawer.get_by_text("确定", exact=True)
        last_error = None

        for select_locator in select_locators:
            if select_locator.count() == 0:
                continue
            try:
                select_locator.click(force=True)
                self.page.wait_for_timeout(300)
                confirm_btn.click()
                try:
                    expect(drawer).not_to_be_visible(timeout=3000)
                    return
                except AssertionError:
                    last_error = AssertionError(f"{drawer_title} 抽屉未关闭，继续尝试其他选择节点")
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise AssertionError(f"未找到 {drawer_title} 中的 {item_name} 可选节点")
