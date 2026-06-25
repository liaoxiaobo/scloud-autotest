"""
【职责】远端操作统一入口，组合 SSH 传输层、SCLI 后端查询与云平台辅助操作，供 fixture 和测试用例做后端验证。

【层级】Fixture 层；被 testcase/conftest.py 以 fixture 形式提供，测试类和 fixtures 直接调用。

【接口】
- 继承 SSHClientBase 的 connect、run、get_file、put_file、close 等方法。
- 继承 ScliMixin 的 guest_show、volume_show、wait_resource_deleted、assert_resource_created、glance_image_create 等方法。
- 继承 CloudOpsMixin 的 find_mfip、ping、mount_disk、create_file、run_sql 等方法。

【示例】
from sugon_web.common.remote.ssh import SSH

def test_backend(ssh_host):
    ssh_host.connect(host="172.22.1.190", username="root", pwd="admin1234@sugon")
    info = ssh_host.guest_show("vm-01")
    assert info.get("status") == "ACTIVE"
"""

from sugon_web.common.remote.cloud_ops import CloudOpsMixin
from sugon_web.common.remote.scli import ScliMixin
from sugon_web.common.remote.ssh_client import SSHClientBase


class SSH(CloudOpsMixin, ScliMixin, SSHClientBase):
    """
    远端操作统一入口。

    - ``SSHClientBase``：连接、命令执行、文件传输等纯 SSH 传输能力。
    - ``ScliMixin``：SCLI 表格解析、资源后端查询和资源删除等待。
    - ``CloudOpsMixin``：云平台、虚机、网络和环境辅助操作。
    """

    pass


__all__ = ["SSH"]

