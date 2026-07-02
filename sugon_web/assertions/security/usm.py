"""云堡垒机高级版 USM 业务断言 Mixin。"""
from sugon_web.assertions.security._base import SecurityStatusAssertionMixin


class UsmAssertionMixin(SecurityStatusAssertionMixin):
    """云堡垒机高级版 USM 业务断言 Mixin。

    验证 USM 实例的服务状态与虚拟机状态收敛。
    本 Mixin 只负责纯断言，不执行授权、删除等会改变实例状态的副作用操作。
    创建后的自动授权/创建失败清理逻辑由调用方（helper/fixture）显式处理。
    属于 L3 Consistency 层断言。
    """

    def assert_usm_status(
        self,
        name: str,
        service_status: str = "运行",
        vm_status: str = "运行",
        timeout: int = 300,
    ) -> dict:
        """断言 USM 实例的服务状态与虚拟机状态。"""
        return self.assert_security_status(
            name,
            service_status=service_status,
            vm_status=vm_status,
            timeout=timeout,
            service_label="USM",
        )
