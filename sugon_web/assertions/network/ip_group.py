from sugon_web.common.playwright import expect


class IpGroupAssertionMixin:
    """IP地址组业务断言 Mixin。

    验证IP地址组详情页基本信息等。
    属于 L2 Business 层断言。
    """

    def assert_ip_group_detail_basic_info(self, name=None, desc=None):
        """校验IP地址组详情页基本信息区域。

        Args:
            name: 期望的名称，为 None 时不校验。
            desc: 期望的描述，为 None 时不校验。
        """
        detail_root = self.locator("#detail_container, #cloud-container-content").first
        expect(detail_root).to_be_visible(timeout=5000)
        if name is not None:
            expect(detail_root).to_contain_text(name)
        if desc is not None:
            expect(detail_root).to_contain_text(desc)
