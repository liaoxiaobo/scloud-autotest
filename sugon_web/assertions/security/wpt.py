"""网页防篡改 WPT 业务断言 Mixin。"""
from sugon_web.assertions.security._base import SecurityStatusAssertionMixin


class WptAssertionMixin(SecurityStatusAssertionMixin):
    """网页防篡改 WPT 业务断言 Mixin。

    验证 WPT 实例的服务状态与虚拟机状态收敛。
    """

    def assert_wpt_status(
        self,
        name: str,
        service_status: str = "运行",
        vm_status: str = "运行",
        timeout: int = 300,
    ) -> dict:
        """断言 WPT 实例的服务状态与虚拟机状态。"""
        return self.assert_security_status(
            name,
            service_status=service_status,
            vm_status=vm_status,
            timeout=timeout,
            service_label="WPT",
        )
