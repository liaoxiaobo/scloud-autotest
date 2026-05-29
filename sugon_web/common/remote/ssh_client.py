import time
from typing import TypedDict

from paramiko import (
    AuthenticationException,
    AutoAddPolicy,
    ChannelException,
    Ed25519Key,
    RSAKey,
    SSHClient,
    SSHException,
)

from sugon_web.utils.logger import logger


class SSHResult(TypedDict, total=False):
    """SSH 命令执行结果。"""

    stdout: str
    stderr: str
    rc: int


def _create_ssh_client(host, port, username, pwd, pkey, transport=None, timeout=300, interval=5):
    """
    创建并返回一个 SSH 客户端连接，支持通过跳板机（可选）和重试机制。

    :param host: 目标主机的 IP 地址或域名。
    :param port: 目标主机的 SSH 端口。
    :param username: SSH 登录用户名。
    :param pwd: SSH 登录密码。如果使用私钥认证，此参数可以为空。
    :param pkey: 私钥文件路径，用于私钥认证。如果使用密码认证，此参数可以为空。
    :param transport: 跳板机的 Transport 对象，用于通过跳板机连接目标主机。默认为 None，表示不使用跳板机。
    :param timeout: 最大超时时间（单位：秒），默认 300 秒。
    :param interval: 每次重试之间的等待时间（以秒为单位）。

    :return: 已成功连接的 SSH 客户端对象。
    """
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())

    if pkey:
        try:
            pkey = RSAKey.from_private_key_file(pkey)
        except SSHException:
            pkey = Ed25519Key.from_private_key_file(pkey)
        pwd = None

    start_time = time.time()
    while True:
        try:
            sock = transport.open_channel("direct-tcpip", (host, port), ("", 0)) if transport else None
            client.connect(
                hostname=host,
                port=port,
                password=pwd,
                username=username,
                pkey=pkey,
                sock=sock,
            )
            return client
        except (AuthenticationException, EOFError, ChannelException) as exc:
            if isinstance(exc, ChannelException):
                logger.warning(f"SSH会话连接建立失败 {host}")
            if isinstance(exc, AuthenticationException):
                logger.warning(f"SSH会话认证失败 {host}")
            if isinstance(exc, EOFError):
                logger.warning(f"SSH会话连接异常终止 {host}")
            client.close()

            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                logger.error(f"{timeout}秒内无法成功SSH连接虚机，请排查虚机是否正常启动、密码注入是否异常")
                raise exc

            time.sleep(interval)


class SSHClientBase:
    """纯 SSH 传输层，负责连接、命令执行、文件传输和连接释放。"""

    def __init__(self):
        self.connections = {}
        self.jumphost_client = None
        self.ssh_client = None

    def _set_jumphost(self, host, port=22, username="root", pwd=None, pkey=None):
        """
        设置并连接到跳板机。

        :param host: 跳板机的 IP 或域名。
        :param port: 跳板机的 SSH 端口，默认为 22。
        :param username: SSH 登录用户名，默认为 'root'。
        :param pwd: SSH 登录密码，默认为 None。
        :param pkey: 私钥文件路径，默认为 None。
        """
        self.jumphost_client = _create_ssh_client(host, port, username, pwd, pkey)
        logger.info(f"Connected successfully to jumphost {host}")

    def _check_connection(self) -> bool:
        """检查 SSH 连接是否仍然有效。"""
        try:
            output = self.run("hostname", timeout=15)
            return bool(output)
        except (SSHException, EOFError):
            return False

    def connect(self, host, port=22, username="root", pwd="admin1234@sugon", pkey=None, use_jumphost=True):
        """
        连接到指定的远程主机，并将 SSH 客户端实例保存在 ssh_client 中。

        :param host: 目标主机的 IP 或域名。
        :param port: 目标主机的 SSH 端口，默认为 22。
        :param username: SSH 登录用户名，默认为 'root'。
        :param pwd: SSH 登录密码，默认为 None。
        :param pkey: 私钥文件路径，默认为 None。
        :param use_jumphost: 是否通过跳板机连接，默认为 True。
        """
        if host in self.connections:
            self.ssh_client = self.connections[host]
            if not self._check_connection():
                logger.info(f"Close the invalid connection to server {host}")
                self.ssh_client.close()
                self.connections.pop(host)
            else:
                logger.info(f"Reusing connection to server {host}")
                return

        if use_jumphost and self.jumphost_client:
            transport = self.jumphost_client.get_transport()
            self.ssh_client = _create_ssh_client(host, port, username, pwd, pkey, transport=transport)
        else:
            self.ssh_client = _create_ssh_client(host, port, username, pwd, pkey)
        self.connections[host] = self.ssh_client
        logger.info(f"Connected successfully to server {host}")

    def run(
        self,
        cmd: str,
        return_stdout: bool = True,
        return_stderr: bool = False,
        return_rc: bool = False,
        check_rc: bool = False,
        timeout: int | None = None,
        get_pty: bool = False,
        wait_for_exit: bool = True,
    ) -> str | SSHResult | None:
        """
        在远程主机上执行命令并返回执行结果。

        该方法基于 Paramiko 的 ``exec_command`` 实现。默认会等待远程命令退出，
        并在等待期间持续读取标准输出和标准错误，以降低大输出场景下因 channel
        缓冲区未及时消费而导致阻塞的风险。
        """
        if not self.ssh_client:
            logger.error("Connection not established. Call connect() first.")
            return None
        if check_rc and not wait_for_exit:
            raise ValueError("check_rc=True requires wait_for_exit=True")

        logger.info(f"Executing command: {cmd}")
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=timeout, get_pty=get_pty)
        channel = stdout.channel
        stdout_chunks = []
        stderr_chunks = []
        start_time = time.time()
        rc = 0
        stdout_content = ""
        stderr_content = ""

        try:
            if not wait_for_exit:
                stdin.close()
                deadline = time.time() + 1

                while time.time() < deadline:
                    while channel.recv_ready():
                        stdout_chunks.append(channel.recv(65535))
                    while channel.recv_stderr_ready():
                        stderr_chunks.append(channel.recv_stderr(65535))
                    if channel.exit_status_ready():
                        break
                    time.sleep(1)

                rc = channel.recv_exit_status() if channel.exit_status_ready() else 0
                stdout_content = b"".join(stdout_chunks).decode(errors="replace")
                stderr_content = b"".join(stderr_chunks).decode(errors="replace")
                logger.info("后台命令已提交，不等待执行完成")
            else:
                while True:
                    while channel.recv_ready():
                        stdout_chunks.append(channel.recv(65535))
                    while channel.recv_stderr_ready():
                        stderr_chunks.append(channel.recv_stderr(65535))

                    if channel.exit_status_ready():
                        while channel.recv_ready():
                            stdout_chunks.append(channel.recv(65535))
                        while channel.recv_stderr_ready():
                            stderr_chunks.append(channel.recv_stderr(65535))
                        rc = channel.recv_exit_status()
                        break

                    if timeout is not None and time.time() - start_time > timeout:
                        channel.close()
                        raise TimeoutError(f"Command timed out after {timeout} seconds: {cmd}")

                    time.sleep(0.1)

                stdout_content = b"".join(stdout_chunks).decode(errors="replace")
                stderr_content = b"".join(stderr_chunks).decode(errors="replace")
        finally:
            stdin.close()
            stdout.close()
            stderr.close()

        logger.info(f"Command exited with return code {rc}")
        logger.info("Command output: \n%s", stdout_content)
        if stderr_content:
            logger.warning(f"Command error output: \n%s", stderr_content)

        if check_rc and rc != 0:
            error_message = f"Command failed with return code {rc}: {stderr_content}"
            logger.error(error_message)
            raise RuntimeError(error_message)

        result = {}
        if return_stdout:
            result["stdout"] = stdout_content.rstrip("\n")
        if return_stderr:
            result["stderr"] = stderr_content.rstrip("\n")
        if return_rc:
            result["rc"] = rc
        if len(result) == 1:
            return result["stdout"]
        return result

    def get_file(self, remotepath, localpath):
        """
        从远程主机下载文件到本地。

        :param remotepath: 远程主机上的文件路径。
        :param localpath: 本地保存文件的路径。
        """
        with self.ssh_client.open_sftp() as sftp:
            sftp.get(remotepath, localpath)

    def put_file(self, localpath, remotepath):
        """
        将本地文件上传到远程主机。

        :param localpath: 本地文件路径。
        :param remotepath: 远程主机上的文件路径。
        """
        with self.ssh_client.open_sftp() as sftp:
            sftp.put(localpath, remotepath)

    def close(self):
        """关闭所有 SSH 连接。"""
        for client in self.connections.values():
            client.close()
        self.connections.clear()
        self.ssh_client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

