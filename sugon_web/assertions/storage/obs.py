import re

from sugon_web.common.playwright import expect


class ObsAssertionMixin:
    """对象存储业务断言 Mixin。

    验证 OBS 页面上的业务专属元素状态与内容。
    """

    def assert_form_project_displayed(self, expected_name="默认项目"):
        """断言创建桶表单中业务属性模块显示的项目名称。

        Args:
            expected_name: 期望显示的项目名称。
        """
        self.page.wait_for_timeout(1500)
        # 方式1：通过业务属性模块内的文本直接定位
        business_attr = self.page.locator(".form-container-item").filter(
            has_text=re.compile(r"业务属性")
        )
        if business_attr.count() > 0:
            project_text = business_attr.first.get_by_text(expected_name, exact=True).first
            if project_text.count() > 0:
                try:
                    expect(project_text).to_be_visible(timeout=5000)
                    return
                except Exception:
                    pass

        # 方式2：直接在页面范围内查找（用 .first 避开多元素 strict mode）
        project_locator = self.page.get_by_text(expected_name, exact=True).first
        expect(project_locator).to_be_visible(timeout=5000)

    def assert_object_list_contain(self, name):
        """断言对象列表中包含指定对象。

        Args:
            name: 对象名称。
        """
        self.assert_list_contain(name)

    def assert_credential_status(self, ak, expected_status="停用"):
        """断言指定访问密钥的状态为期望值。

        Args:
            ak: Access Key ID
            expected_status: 期望状态，"启用" 或 "停用"
        """
        row_data = self.get_row_data(ak)
        actual_status = row_data.get("状态", "")
        assert expected_status in actual_status, (
            f"[StatusAssertion] 访问密钥 {ak} | 状态不匹配 | "
            f"期望: {expected_status} | 实际: {actual_status}"
        )
