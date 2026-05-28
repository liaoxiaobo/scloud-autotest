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

