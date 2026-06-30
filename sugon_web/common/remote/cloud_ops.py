"""
【职责】提供云平台 API 调用、远程文件操作、磁盘挂载、网络连通性检测、系统服务状态查询、数据库节点信息查询及 SQL 执行等远端辅助能力。

【层级】Fixture 层；被 SSH 类继承，通过 SSH fixture 调用。

【接口】
- find_mfip(fixed_ip, host=None) -> str：查询 fixed_ip 对应的 MFIP 地址。
- ping(ip, connected=True, count=10, retries=5)：执行 ping 并断言 ICMP 连通性。
- ping_in_thread(ip, connected=True, count=4, retries=3) -> Thread：在后台线程执行 ping，返回线程句柄。
- telnet(host, port=22, timeout=300)：轮询检测目标主机端口的 TCP 连通性，超时抛异常。
- mount_disk(disk_name, mount_point=None, format_disk=True, disk_type="ext4") -> str：在虚拟机中挂载磁盘。
- create_file(filepath, size=10) -> str：在远端创建指定大小文件并返回 MD5。
- file_exist(path) / file_not_exist(path)：断言文件存在或不存在。
- get_service_status(service_name) -> str：查询 systemd 服务状态（running/stopped/failed）。
- run_sql(database, sql_statement)：在远端执行 SQL 语句。
- get_node_mfip(db_name, node_name, table_name="node") -> str：从数据库查询节点 MFIP。
- get_instance_node_ips(db_name, instance_name) -> list：从数据库查询实例各节点的 (名称, MFIP) 列表。

【示例】
def test_disk(ssh_vm):
    mount_point = ssh_vm.mount_disk("sdb", mount_point="/mnt/test", format_disk=True)
    md5 = ssh_vm.create_file("/mnt/test/file", size=100)
    ssh_vm.ping("10.0.0.5", connected=True)
"""

import json
import re
import shlex
import threading
import time

from sugon_web.config.config import Config
from sugon_web.utils.logger import logger


class CloudOpsMixin:
    """云平台、虚机和远端环境辅助操作。"""

    @staticmethod
    def _find_json_value(data, key):
        """递归查找 JSON 中第一个指定 key 的值。"""
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for value in data.values():
                found = CloudOpsMixin._find_json_value(value, key)
                if found is not None:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = CloudOpsMixin._find_json_value(item, key)
                if found is not None:
                    return found
        return None

    def find_mfip(self, fixed_ip: str, host: str = None) -> str:
        """
        通过 SDN mfip 接口查询 fixed_ip 对应的 mfip_address。
        优先使用配置的 host 访问，若失败则回退到固定 VIP (100.126.255.250)。
        """
        vip = host or Config.get("host")
        if not vip:
            raise ValueError("未传入 host，且配置中未找到 host，无法查询 mfip_address")

        token_command = (
            "curl -s -X POST "
            "-H 'Content-Type: application/json' "
            "-d '{\"origin_login\": true, \"password\": \"Inner@fullstackOwner\", \"username\": \"inner\"}' "
            "http://sugoncloud-iam-api-http.micro-service.svc.cluster.local:8080/api/oauth/token"
        )
        token_response = self.run(token_command, check_rc=True)
        try:
            token_data = json.loads(token_response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"获取 token 返回非 JSON 内容: {token_response}") from exc

        token = self._find_json_value(token_data, "content")
        if not token:
            raise RuntimeError(f"获取 token 失败，响应内容: {token_response}")

        mfip_fixed_vip = "100.126.255.250"
        vips_to_try = [vip]
        if vip != mfip_fixed_vip:
            vips_to_try.append(mfip_fixed_vip)

        last_error = None
        for current_vip in vips_to_try:
            try:
                mfip_command = (
                    f"curl -s 'http://{current_vip}:14830/sdn/v2.0/mfip/?per_page=10&fixed_ip={fixed_ip}&page=1' "
                    "-H 'accept: application/json' "
                    f"-H {shlex.quote(f'X-Auth-Token: {token}')} "
                    "--compressed --insecure"
                )
                mfip_response = self.run(mfip_command, check_rc=True)
                mfip_data = json.loads(mfip_response)

                mfip_address = self._find_json_value(mfip_data, "mfip_address")
                if not mfip_address:
                    last_error = RuntimeError(
                        f"使用 VIP {current_vip} 未查询到 fixed_ip={fixed_ip} 对应的 mfip_address，响应内容: {mfip_response}"
                    )
                    logger.warning(f"使用 VIP {current_vip} 未查询到 mfip_address，尝试下一个 VIP")
                    continue

                logger.info(f"查询到 fixed_ip '{fixed_ip}' 对应的 mfip_address: {mfip_address} (使用 VIP: {current_vip})")
                return mfip_address
            except Exception as exc:
                last_error = exc
                logger.warning(f"使用 VIP {current_vip} 查询 mfip 失败: {exc}，尝试下一个 VIP")
                continue

        raise RuntimeError(f"所有 VIP {vips_to_try} 均无法查询到 fixed_ip={fixed_ip} 对应的 mfip_address") from last_error

    def telnet(self, host, port=22, timeout=300):
        """
        检测服务器端口是否连通。

        :param host: 服务器地址。
        :param port: 端口号，默认为 22。
        :param timeout: 超时时间（秒），默认为 300。
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            stdout = self.run(f"echo quit | timeout --signal=9 2 telnet {host} {port}")
            if f"Connected to {host}" in stdout:
                return
            time.sleep(5)
        raise Exception(f"Telnet to {host}:{port} timed out")

    def _get_host(self) -> dict:
        """获取集群的节点 IP。"""
        node_info = self.run("sudo kubectl get no -owide", check_rc=True)

        master_nodes = []
        all_nodes = []
        for line in node_info.split("\n")[1:]:
            if line.strip() == "":
                continue

            parts = line.split()
            if len(parts) >= 6:
                ip = parts[5]
                all_nodes.append(ip)
                if "master" in line:
                    master_nodes.append(ip)

        return {"master": master_nodes, "host": all_nodes}

    def _set_alias(self):
        """设置 alias 命令，仅适用于物理环境节点。"""
        name = "/root/admin-openrc.sh"
        for path in ["/home/scloudadmin/.bashrc", "/root/.bashrc"]:
            if not self.run(f"cat {path} |grep {name}"):
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
        在当前 SSH 会话的远程服务器上创建指定大小的文件，并返回 MD5 值。

        :param filepath: 要创建的完整文件路径。
        :param size: 文件大小，单位 MB。
        :return: 创建文件的 MD5 值。
        """
        cmd = f"dd if=/dev/zero of={filepath} bs=1M count={size}"
        self.run(cmd)
        self.run("sync")
        md5_command = f"md5sum {filepath} | awk '{{print $1}}'"
        return self.run(md5_command).strip()

    def file_exist(self, path: str):
        """断言指定路径的文件存在。"""
        check_command = f"ls -lh {path}"
        result = self.run(check_command, return_rc=True)
        if result["rc"]:
            raise AssertionError(f"File does not exist at path: {path}")

    def file_not_exist(self, path: str):
        """断言指定路径的文件不存在。"""
        check_command = f"ls -lh {path}"
        result = self.run(check_command, return_rc=True)
        if not result["rc"]:
            raise AssertionError(f"File exists at path: {path}")

    def ping(self, ip, connected=True, count=10, retries=5, retry_delay=5, ipv6=False):
        """
        通过 ping 命令测试目标 IP 的连通性，并支持重试机制。
        失败时直接抛出断言错误。
        """
        ping_cmd = f"ping6 {ip} -c {count}" if ipv6 else f"ping {ip} -c {count}"
        loss_re = re.compile(r"(\d+)% packet loss")

        for attempt in range(1, retries + 1):
            stdout = self.run(ping_cmd)

            match = loss_re.search(stdout)
            loss = int(match.group(1)) if match else 100
            reachable = loss < 100

            if connected:
                if reachable:
                    logger.info(f"Ping to {ip} succeeded.")
                    return
            else:
                if not reachable:
                    logger.info(f"Ping to {ip} failed as expected.")
                    return

            if attempt < retries:
                logger.info(f"Ping attempt {attempt} failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        logger.error(f"Ping to {ip} failed after {retries} retries")
        assert False, f"Ping to {ip} failed after {retries} retries"

    def mount_disk(self, disk_name, mount_point=None, format_disk=True, disk_type="ext4"):
        """
        在虚拟机中挂载磁盘。

        Args:
            disk_name: 磁盘设备名，如 "sdb"。
            mount_point: 挂载点，默认为 /mnt/{disk_name}。
            format_disk: 是否格式化磁盘，默认为 True。

        Returns:
            str: 实际使用的挂载点。
        """
        if not mount_point:
            mount_point = f"/mnt/{disk_name}"

        self.run("lsblk")

        if format_disk:
            self.run(f"mkfs.{disk_type} -F /dev/{disk_name}", check_rc=True)

        self.run(f"mkdir -p {mount_point}")
        self.run(f"mount /dev/{disk_name} {mount_point}")

        mount_check = self.run(f"df -h | grep '/dev/{disk_name}' | awk '{{print $6}}'")
        assert mount_point in mount_check, f"磁盘 {disk_name} 未正确挂载到 {mount_point}，实际挂载点: {mount_check}"

        return mount_point

    def ping_in_thread(self, ip, connected=True, count=4, retries=3, retry_delay=2):
        """在单独的线程中执行 ping 方法。"""
        ping_thread = threading.Thread(target=self.ping, args=(ip, connected, count, retries, retry_delay))
        ping_thread.start()
        return ping_thread

    def run_sql(self, database: str, sql_statement: str):
        """
        执行 SQL 语句并返回结果。

        :param database: 数据库名称。
        :param sql_statement: SQL 语句。
        :return: SQL 执行结果。
        """
        sql_command = f"use {database};{sql_statement}"
        command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_command}\\\"\""
        result = self.run(command, return_stderr=True)
        logger.info(f"SQL执行成功: {sql_statement}, 结果: {result}")

    def get_service_status(self, service_name: str) -> str:
        """
        获取系统服务状态。

        :param service_name: 服务名称（如 doris-be, doris-fe, mysql 等）。
        :return: 服务状态（如 running, stopped, failed 等）。
        :raises RuntimeError: 命令执行或解析失败时。
        """
        try:
            result = self.run(f"systemctl status {service_name}")
            logger.info(f"systemctl status {service_name} 输出:\n{result}")

            if 'active (running)' in result.lower():
                status = 'running'
            elif 'inactive (dead)' in result.lower():
                status = 'stopped'
            elif 'failed' in result.lower():
                status = 'failed'
            else:
                for line in result.splitlines():
                    if 'Active:' in line:
                        status = line.strip()
                        break
                else:
                    status = 'unknown'

            logger.info(f"服务 '{service_name}' 的状态为: {status}")
            return status
        except Exception as e:
            raise RuntimeError(f"获取服务状态失败 (服务: {service_name}): {e}")

    def get_node_mfip(self, db_name: str, node_name: str, table_name: str = "node") -> str:
        """
        通过在 master 节点执行 anhan 命令，从数据库中查询节点的 mfip。

        :param db_name: 数据库名称。
        :param node_name: 节点名称。
        :param table_name: 表名，默认为 node。
        :return: 节点的 mfip 地址。
        """
        sql_query = f"use {db_name};select mfip from {table_name} where name='{node_name}'"
        command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_query}\\\"\""
        result = self.run(command)
        ip = result.strip().splitlines()[-1].strip()
        logger.info(f"从数据库查询到节点 '{node_name}' 的IP地址为: {ip}")
        return ip

    def get_instance_node_ips(self, db_name: str, instance_name: str) -> list:
        """
        通过数据库查询实例下所有节点名称和 mfip。

        :param db_name: 数据库名称。
        :param instance_name: 实例名称前缀。
        :return: list[tuple[str, str]] 节点名称和IP列表。
        """
        sql_query = (
            f"use {db_name};"
            f"select name,mfip from node where name like '{instance_name}-%' order by name;"
        )
        command = f"echo 'admin1234@sugon' | su - root -c \"anhan -e \\\"{sql_query}\\\"\""
        result = self.run(command)
        node_infos = []
        for line in result.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("name") or line.startswith("-"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith(f"{instance_name}-"):
                node_infos.append((parts[0], parts[-1]))
        logger.info(f"从数据库查询到实例 '{instance_name}' 节点列表: {node_infos}")
        return node_infos

    def _get_release_version(self, host):
        """
        获取版本信息并解析为字典。

        Args:
            host: 主机 IP。

        Returns:
            dict: 解析后的版本信息。
        """
        version_paths = [
            "/opt/extra/init-base/patch_release_version",
            "/opt/extra/release_version",
        ]

        for path in version_paths:
            try:
                cmd = f"ssh -o StrictHostKeyChecking=no {host} cat {path}"
                release_version = self.run(cmd)

                if release_version and release_version.strip():
                    logger.info(f"成功从 {path} 获取版本信息")
                    return dict(item.split(": ") for item in release_version.split("\n"))
                logger.warning(f"路径 {path} 中的版本信息为空")
            except Exception as exc:
                logger.error(f"从 {path} 获取版本信息失败: {exc}")

        logger.error("警告: 无法从任何路径获取版本信息")
        return {}
