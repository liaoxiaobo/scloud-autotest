import threading
import time
from paramiko import SSHClient, AutoAddPolicy, RSAKey, SSHException, AuthenticationException, ChannelException, Ed25519Key
from sugon_web.utils.util import get_file_abspath
from sugon_web.utils.logger import logger


def _create_ssh_client(host, port, username, pwd, pkey, transport=None, timeout=300, interval=5):
    """
    创建并返回一个 SSH 客户端连接，支持通过跳板机（可选）和重试机制。

    :param host: 目标主机的 IP 地址或域名。
    :param port: 目标主机的 SSH 端口。
    :param username: SSH 登录用户名。
    :param pwd: SSH 登录密码。如果使用私钥认证，此参数可以为空。
    :param pkey: 私钥文件路径，用于私钥认证。如果使用密码认证，此参数可以为空。
    :param transport: 跳板机的 Transport 对象，用于通过跳板机连接目标主机。默认为 None，表示不使用跳板机。
    :param timeout: 最大超时时间（单位：秒），默认 180 秒
    :param interval: 每次重试之间的等待时间（以秒为单位）。

    :return: 已成功连接的 SSH 客户端对象。

    :raises AuthenticationException: 当身份验证失败时抛出。
    :raises EOFError: 当连接终止时抛出。
    :raises ChannelException: 当建立连接出现异常时抛出。
    """
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    # 动态选择私钥类型
    if pkey:
        try:
            pkey = RSAKey.from_private_key_file(pkey)
        except SSHException:
            pkey = Ed25519Key.from_private_key_file(pkey)
        pwd = None

    start_time = time.time()
    while True:
        try:
            # 如果提供了 transport，通过跳板机创建连接隧道
            sock = transport.open_channel("direct-tcpip", (host, port), ('', 0)) if transport else None
            client.connect(hostname=host,
                           port=port,
                           password=pwd,
                           username=username,
                           pkey=pkey,
                           sock=sock)
            return client
        except (AuthenticationException, EOFError, ChannelException) as e:
            # 记录登陆失败日志，并及时关闭异常Connection
            if isinstance(e, ChannelException):
                logger.warning(f"SSH会话连接建立失败 {host}")
            if isinstance(e, AuthenticationException):
                logger.warning(f"SSH会话认证失败 {host}")
            if isinstance(e, EOFError):
                logger.warning(f"SSH会话连接异常终止 {host}")
            client.close()

            # 检查时间是否超时
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                logger.error(f"{timeout}秒内无法成功SSH连接虚机，请排查虚机是否正常启动、密码注入是否异常")
                raise e  # 超时后抛出最后捕获的异常

            time.sleep(interval)


class SSH:

    def __init__(self):
        """
        初始化 SSH 客户端管理类实例。
        """
        self.connections = {}
        self.jumphost_client = None
        # self.ssh_client = None
        # self.sftp_client = None

    def _set_jumphost(self, host, port=22, username='root', pwd=None, pkey=None):
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
        """
        检查 SSH 连接是否仍然有效。
        """
        try:
            # 使用 run 方法执行简单命令来测试连接
            output = self.run('hostname')
            return bool(output)
        except (SSHException, EOFError):
            return False

    def connect(self, host, port=22, username='root', pwd="admin1234@sugon", pkey=None, use_jumphost=True):
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
            if not self._check_connection():    # 检查连接是否仍然有效
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
        # self.sftp_client = self.ssh_client.open_sftp()  # 初始化共享 SFTP 会话
        logger.info(f"Connected successfully to server {host}")

    def run(self, cmd, return_stdout=True, return_stderr=False, return_rc=False, check_rc=False, timeout=None,
            get_pty=False):
        """
        在远程服务器上执行命令，并根据参数返回命令的标准输出、标准错误输出和返回码。

        :param cmd: 要执行的命令（字符串）
        :param return_stdout: 是否返回标准输出（默认True）
        :param return_stderr: 是否返回标准错误输出（默认False）
        :param return_rc: 是否返回命令的返回码（默认False）
        :param check_rc: 是否检查返回码
        :param timeout: 命令执行的超时时间（秒），默认为None表示不设超时
        :param get_pty: 是否分配伪终端
        :return: 一个包含标准输出、标准错误和返回码的字典，或在命令失败时返回错误信息
        """
        if not self.ssh_client:  # 确保在执行命令之前已经成功连接
            logger.error("Connection not established. Call connect() first.")
            return None
        logger.info(f"Executing command: {cmd}")
        stdin, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=timeout, get_pty=get_pty)
        rc = stdout.channel.recv_exit_status()
        stdout_content = stdout.read().decode()
        stderr_content = stderr.read().decode()
        logger.info(f"Command exited with return code {rc}")
        logger.info("Command output: \n%s", stdout_content)
        if stderr_content:
            logger.warning(f"Command error output: \n%s", stderr_content)

        stdin.close()
        stdout.close()
        stderr.close()

        if check_rc and rc != 0:
            error_message = f"Command failed with return code {rc}: {stderr_content}"
            logger.error(error_message)
            raise RuntimeError(error_message)

        result = {}
        if return_stdout:
            result['stdout'] = stdout_content.rstrip('\n')  # 去掉字符串末尾换行
        if return_stderr:
            result['stderr'] = stderr_content.rstrip('\n')
        if return_rc:
            result['rc'] = rc
        if len(result) == 1:
            return result['stdout']
        return result

    def get_file(self, remotepath, localpath):
        """
        从远程主机下载文件到本地。

        :param remotepath: 远程主机上的文件路径。
        :param localpath: 本地保存文件的路径。
        """
        # self.sftp_client.get(remotepath, localpath)
        with self.ssh_client.open_sftp() as sftp:
            sftp.get(remotepath, localpath)

    def put_file(self, localpath, remotepath):
        """
        将本地文件上传到远程主机。

        :param localpath: 本地文件路径。
        :param remotepath: 远程主机上的文件路径。
        """
        # self.sftp_client.put(localpath, remotepath)
        with self.ssh_client.open_sftp() as sftp:
            sftp.put(localpath, remotepath)

    def close(self):
        """
        关闭所有 SSH 连接和 SFTP 会话。
        """
        # if self.sftp_client:
        #     self.sftp_client.close()
        for client in self.connections.values():
            client.close()
        self.connections.clear()

    def __enter__(self):
        """
        进入上下文管理器时会自动调用，通常返回类的实例本身，使得可以在 with 块中使用该实例。
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文管理器时自动调用，负责清理操作，比如关闭 SSH 连接
        """
        self.close()

    def telnet(self, host, port=22, timeout=300):
        """
        检测服务器端口是否连通

        :param host: 服务器地址
        :param port: 端口号，默认为22
        :param timeout: 超时时间（秒），默认为300
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            stdout = self.run(f'echo quit | timeout --signal=9 2 telnet {host} {port}')
            if f"Connected to {host}" in stdout:
                return
            time.sleep(5)
        raise Exception(f"Telnet to {host}:{port} timed out")

    def _get_host(self):
        """获取集群的节点ip"""
        d = {
            'master': self.run("sudo kubectl get no -owide | grep master | awk '{print $6}'").split('\n'),
            'host': self.run("sudo kubectl get no -owide|grep -v backup | awk 'NR>1' |awk '{print $6}'").split('\n')
        }
        return d

    def _set_alias(self):
        """设置alias命令，仅适用于物理环境节点"""
        name = "/root/admin-openrc.sh"
        for path in ["/home/scloudadmin/.bashrc", "/root/.bashrc"]:
            if not self.run(f'cat {path} |grep {name}'):
                self.run(f"echo 'source {name}' | sudo tee -a {path}")
                aliases = """
                alias k='kubectl'
                alias kk='kubectl -n kube-system'
                alias ko='kubectl -n openstack'
                alias km='kubectl -n micro-service'
                alias os='openstack'
                alias kolla='cd /var/lib/docker/volumes/kolla_logs/_data'
                """
                self.run(f"echo \"{aliases}\" | sudo tee -a {path}")
                self.run(f"source {path}")

    def create_file(self, filepath: str, size: int = 10) -> str:
        """
        在当前 SSH 会话的远程服务器上创建一个指定大小的文件，并返回其 MD5 值。

        :param filepath: 要创建的文件的完整路径。
        :param size: 文件大小，单位为 MB，默认值为 10 MB。
        :return: 创建的文件的 MD5 值。
        """
        cmd = f"dd if=/dev/zero of={filepath} bs=1M count={size}"
        self.run(cmd)
        self.run("sync")
        md5_command = f"md5sum {filepath} | awk '{{print $1}}'"
        md5_value = self.run(md5_command).strip()
        return md5_value

    def file_exist(self, path: str):
        """
        使用 SSH 客户端断言指定路径的文件存在。

        :param path: 要检查的文件路径。
        :return: 如果文件存在返回 True，否则抛出 AssertionError。
        """
        check_command = f"ls -lh {path}"
        result = self.run(check_command, return_rc=True)
        if result["rc"]:
            raise AssertionError(f"File does not exist at path: {path}")

    def file_not_exist(self, path: str):
        """
        使用 SSH 客户端断言指定路径的文件不存在。

        :param path: 要检查的文件路径。
        :return: 如果文件不存在返回 True，否则抛出 AssertionError。
        """
        check_command = f"ls -lh {path}"
        result = self.run(check_command, return_rc=True)
        if not result['rc']:
            raise AssertionError(f"File exists at path: {path}")

    def ping(self, ip, connected=True, count=4, retries=5, retry_delay=5):
        """
        通过ping命令测试目标IP的连通性，并支持重试机制。
        失败时直接抛出断言错误。

        :param ip: 目标IP地址。
        :param connected: 预期连通状态，如果为True，表示期望IP可达；如果为False，表示期望IP不可达。
        :param count: 每次ping命令发送的ICMP包数量，默认是4个。
        :param retries: 如果ping失败，最大重试次数，默认3次。
        :param retry_delay: 每次重试前的延迟时间，默认2秒。
        """

        for attempt in range(1, retries + 1):
            stdout = self.run(f'ping {ip} -c {count}')

            if connected:
                if f"{count} packets transmitted, {count} received, 0% packet loss" in stdout:
                    logger.info(f"Ping to {ip} succeeded.")
                    return
            else:
                if f"{count} packets transmitted, 0 received, 100% packet loss" in stdout:
                    logger.info(f"Ping to {ip} failed as expected.")
                    return

            if attempt < retries:
                logger.info(f"Ping attempt {attempt} failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        logger.error(f"Ping to {ip} failed after {retries} retries")
        assert False, f"Ping to {ip} failed after {retries} retries"

    def image_upload(self, name, image, backend, size=20, purpose='kvm', hw_firmware_type='bios', os_version="centos7.9", **kwargs):
        arch = self.run("arch")
        if arch == 'aarch64':
            image = image.replace(".raw", "-aarch64.raw")   # 当环境是arm时，image参数写死
            hw_firmware_type = "uefi"
        if "os_hygon_csv" in kwargs:
            hw_firmware_type = "uefi"
            os_version = "Anolis OS8.8"
        self.image_download(image)
        disk_format = image.rsplit('.', 1)[-1]
        cmd = f'glance image-create --name {name} \
            --visibility public \
            --min-disk {size} \
            --container-format bare \
            --disk-format {disk_format} \
            --property hypervisor_type=kvm \
            --property purpose={purpose} \
            --property os_version="{os_version}" \
            --property os_bits=64 \
            --property os_type=linux \
            --property architecture={arch} \
            --property hw_firmware_type={hw_firmware_type} \
            --file {image} \
            --backend {backend} \
            --progress '
        for k, v in kwargs.items():
            cmd = cmd + f"--property {k}={v} "
        r = self.run(cmd, return_stderr=True)
        return r

    def mount(self, mount_point, disk=None, partition=True, fstab=False):
        """
        对云硬盘进行操作:分区、格式化、挂载
        :param mount_point: 挂载点
        :param disk: 默认自动查找最新挂载的磁盘设备，如vdb
        :param partition: 是否分区数据盘
        :param fstab: 是否设置启动时自动挂盘
        """
        self.run('lsblk')
        if disk is None:
            cmd = "lsblk -nr -o NAME,TYPE | awk '$2 == \"disk\" {print $1}' | while read device; do if ! lsblk /dev/$device | grep -q '/'; then echo $device; fi; done | tail -n 1"
            disk = self.run(cmd)
        self.put_file(get_file_abspath("mount.sh"), './mount.sh')
        self.run('chmod +x ./mount.sh')
        self.run(f'./mount.sh /dev/{disk} {mount_point} {partition} {fstab}')
        self.run('lsblk')
        stdout = self.run("lsblk | grep {0} | awk '{1}'".format(disk+'1', "{print $7}"))
        assert stdout == mount_point, f"云盘{disk}分区挂载出现异常，请排查日志"

    def ping_in_thread(self, ip, connected=True, count=4, retries=3, retry_delay=2):
        """
        在单独的线程中执行ping方法。
        """
        ping_thread = threading.Thread(target=self.ping, args=(ip, connected, count, retries, retry_delay))
        ping_thread.start()
        return ping_thread


