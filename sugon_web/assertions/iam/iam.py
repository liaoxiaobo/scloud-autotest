"""IAM 统一身份认证断言 Mixin。"""

from playwright.sync_api import expect
from sugon_web.utils.logger import logger


class IamAssertionMixin:
    """IAM 统一身份认证断言 Mixin。

    提供组织树存在性、配额显示值等 IAM 页面特有的断言能力。
    """

    def assert_org_in_tree(self, org_name: str, timeout: int = 30):
        """验证组织结构树中存在指定名称的组织节点。

        Args:
            org_name: 期望存在的组织名称
            timeout: 最长等待时间（秒），默认 30（考虑后端异步同步延迟）
        """
        tree = self.page.locator("#iam-department")
        try:
            expect(tree).to_be_visible(timeout=30000)
        except Exception:
            logger.warning("IAM：组织树组件未加载，尝试刷新页面")
            self.page.reload()
            self.wait_for_page_ready()
            self.page.wait_for_timeout(5000)
            expect(tree).to_be_visible(timeout=30000)

        node = tree.locator(".depart_name").filter(has_text=org_name)
        found = False
        for _ in range(timeout):
            if node.count() > 0:
                found = True
                break
            self.page.wait_for_timeout(1000)
        if not found:
            raise AssertionError(
                f"[ListAssertion] 组织树 | 组织 '{org_name}' 存在性校验失败 | "
                f"期望: 存在 | 实际: 未找到"
            )
        logger.info(f"组织结构树中已确认存在组织 {org_name}")

    def assert_quota_value(self, service_name: str, metric_name: str, expected_value: str):
        """验证组织配额页面中指定服务的指标显示值。

        Args:
            service_name: 服务名称，如"云服务器ECS"
            metric_name: 指标名称，如"cpu使用量(个)"
            expected_value: 预期显示值，如"0/1"
        """
        tab_container = self.page.locator("#tabContainer")
        expect(tab_container.first).to_be_visible(timeout=15000)

        service_card = None
        for _ in range(10):
            tab_items = tab_container.locator(".tab-item").all()
            for item in tab_items:
                title_el = item.locator(".sub-title")
                if title_el.count() > 0:
                    title_text = title_el.first.inner_text().strip()
                    if service_name == title_text or service_name in title_text or title_text in service_name:
                        service_card = item
                        break
            if service_card is not None:
                break
            self.page.wait_for_timeout(1500)
        if service_card is None:
            all_titles = [
                item.locator(".sub-title").first.inner_text().strip()
                for item in tab_container.locator(".tab-item").all()
                if item.locator(".sub-title").count() > 0
            ]
            raise AssertionError(
                f"[ListAssertion] 配额页面 | 服务 '{service_name}' 存在性校验失败 | "
                f"期望: 存在 | 实际: 未找到，当前页面有: {all_titles}"
            )

        metric_item = service_card.locator(".item-name").filter(has_text=metric_name)
        for _ in range(5):
            if metric_item.count() > 0:
                break
            self.page.wait_for_timeout(1000)
        if metric_item.count() == 0:
            raise AssertionError(
                f"[FieldAssertion] 配额-{service_name} | 指标 '{metric_name}' 存在性校验失败 | "
                f"期望: 存在 | 实际: 未找到"
            )

        value_el = metric_item.first.locator("xpath=../..").locator(".item-value")
        actual_value = value_el.first.inner_text().strip()
        assert expected_value in actual_value, (
            f"[FieldAssertion] 配额-{service_name} | 指标 '{metric_name}' 值不匹配 | "
            f"期望: 包含 '{expected_value}' | 实际: '{actual_value}'"
        )
        logger.info(f"验证配额 {service_name}-{metric_name} 显示为 {actual_value}")
