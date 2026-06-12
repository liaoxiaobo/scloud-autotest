import pytest
from sugon_web.pages.network import VpcPage

class TestSimple:
    def test_simple_nav(self, page):
        print(f"\n=== After fixture - URL: {page.url} ===")
        # 接受 index 或 console-page（无弹窗）作为已登录状态
        assert "/#/index" in page.url or "/#/console-page" in page.url, f"Expected logged-in page, got {page.url}"

        vpc_page = VpcPage(page)
        vpc_page.goto_service("虚拟私有云")
        print(f"=== After goto_service - URL: {page.url} ===")
        # 8.0.6.0 中 VPC 页面 URL 可能为 /vpc/#/vpc-network-list
        assert "/vpc/" in page.url or "/#/vpc" in page.url, f"Expected vpc page, got {page.url}"
