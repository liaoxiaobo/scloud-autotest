import re
import shlex
import time

from sugon_web.config.config import Config
from sugon_web.utils.logger import logger


def _handle_arch_specific_config(arch, image, hw_firmware_type, os_version, kwargs):
    """处理架构特定的镜像配置。"""
    if arch == "aarch64":
        image = image.replace(".raw", "-aarch64.raw")
        hw_firmware_type = "uefi"

    if "os_hygon_csv" in kwargs:
        hw_firmware_type = "uefi"
        os_version = "Anolis OS8.8"

    return image, hw_firmware_type, os_version


class ScliMixin:
    """SCLI 相关后端查询、解析和资源等待能力。"""

    def wait_resource_deleted(self, names, check_command, timeout=600, interval=5):
        """
        轮询等待资源从后端彻底删除，支持单个或多个资源名称。

        :param names: 资源名称（字符串）或资源名称列表（列表）。
        :param check_command: 查询资源的命令，如 "scli volume list"、"scli guest list"。
        :param timeout: 每个资源的超时时间（秒）。
        :param interval: 轮询间隔时间（秒）。
        """
        resource_names = [names] if isinstance(names, str) else list(names)

        for resource_name in resource_names:
            end_time = time.time() + timeout
            grep_command = f"{check_command} | grep -F -- {shlex.quote(resource_name)}"
            logger.info(f"开始轮询检查资源是否已删除: {resource_name}")

            while time.time() < end_time:
                result = self.run(grep_command)
                if result == "":
                    logger.info(f"资源已成功删除: {resource_name}")
                    break

                logger.debug(f"资源仍存在，{interval} 秒后重试: {resource_name}")
                time.sleep(interval)
            else:
                final_result = self.run(grep_command)
                if final_result == "":
                    logger.info(f"资源在最后一次检查时已删除: {resource_name}")
                else:
                    raise AssertionError(
                        f"超时错误：资源 '{resource_name}' 在 {timeout} 秒内未能从后端删除。\n"
                        f"检查命令: {check_command}\n"
                        f"当前结果:\n{final_result}"
                    )

    def wait_volume_deleted(self, names, timeout=600, interval=5):
        """轮询等待云硬盘从 SCLI 后端彻底删除。"""
        self.wait_resource_deleted(names, check_command="scli volume list", timeout=timeout, interval=interval)

    def wait_vm_deleted(self, names, timeout=600, interval=5):
        """轮询等待虚机从 Gova 后端彻底删除。"""
        self.wait_resource_deleted(names, check_command="scli guest list", timeout=timeout, interval=interval)

    def wait_image_deleted(self, names, timeout=600, interval=5):
        """轮询等待镜像从 Glance 后端彻底删除。"""
        self.wait_resource_deleted(names, check_command="scli image list", timeout=timeout, interval=interval)

    @staticmethod
    def parse_table_output(output):
        """将 CLI 表格输出解析为字典，兼容 ASCII 和 Unicode 边框表格。"""
        result = {}
        if not output:
            return result

        current_key = None
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            parts = [part.strip() for part in re.split(r"[|│┃¦]+", line)]
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]
            if not parts or not any(parts):
                continue

            joined = "".join(parts)
            if not re.search(r"[A-Za-z0-9_]", joined):
                continue
            if len(parts) >= 2 and parts[0].upper() == "FIELD" and parts[1].upper() == "VALUE":
                continue
            if re.fullmatch(r"[-─━]+", parts[0]):
                continue

            if len(parts) >= 2:
                key = parts[0]
                value = parts[1]
                if key:
                    current_key = key
                    result[current_key] = value
                elif current_key and value:
                    result[current_key] = f"{result[current_key]} {value}".strip()
                continue

            if current_key and parts[0]:
                result[current_key] = f"{result[current_key]} {parts[0]}".strip()

        return result

    def guest_show(self, ref: str):
        """执行 scli guest show 并返回解析后的字典。

        支持传入 guest UUID 或节点名称。传入名称时会先通过 scli guest list 查找对应 ID。
        """
        guest_id = self._extract_uuid(ref)
        if not guest_id:
            guest_id = self.run(
                f"scli guest list --name '{ref}' | grep -F '{ref}' | head -n 1 | cut -d '|' -f 2 | xargs"
            ).strip()
            if not guest_id and ref.endswith("-0"):
                instance_name = ref.rsplit("-0", 1)[0]
                guest_id = self.run(
                    f"scli guest list --name '{instance_name}' | grep -F '{instance_name}' | head -n 1 | cut -d '|' -f 2 | xargs"
                ).strip()
            if not guest_id:
                raise RuntimeError(f"未找到节点对应的 guest id: {ref}")
        return self.parse_table_output(self.run(f"scli guest show {guest_id}"))

    def assert_guest_fields(self, ecs_id, expected_fields, error_prefix):
        """校验 scli guest show 中的字段值。"""
        stdout = self.guest_show(ecs_id)
        for field, expected in expected_fields.items():
            actual = stdout.get(field)
            assert actual == expected, f"{error_prefix}，期望 {field}:{expected}，实际 {field}:{actual}"
        return stdout

    def assert_guest_node(self, ecs_id, expected_node, error_prefix):
        """校验虚机后端节点。"""
        self.assert_guest_fields(ecs_id, {"node": expected_node}, error_prefix)

    @staticmethod
    def _extract_uuid(text):
        match = re.search(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", text or "")
        return match.group(0) if match else ""

    def get_volume_id(self, volume_name):
        output = self.run(f"scli volume list | grep -F -- {shlex.quote(volume_name)}")
        for line in output.splitlines():
            if volume_name in line:
                volume_id = self._extract_uuid(line)
                if volume_id:
                    return volume_id
        raise RuntimeError(f"未找到云硬盘 ID: {volume_name}")

    def volume_show(self, volume_ref):
        volume_id = volume_ref if self._extract_uuid(volume_ref) else self.get_volume_id(volume_ref)
        return self.parse_table_output(self.run(f"scli volume show {volume_id}"))

    def get_volume_size(self, volume_ref):
        """
        获取云硬盘容量。

        :param volume_ref: 云硬盘标识，可传云硬盘名称或云硬盘 UUID。
        :return: 云硬盘容量，单位为 GB。
        """
        volume_info = self.volume_show(volume_ref)
        for key in ("size", "Size", "volume_size", "Volume Size"):
            value = volume_info.get(key)
            if value:
                match = re.search(r"\d+", str(value))
                if match:
                    return int(match.group(0))
        raise RuntimeError(f"无法从 scli volume show 结果中解析云硬盘容量: {volume_ref} -> {volume_info}")

    def assert_resource_created(self, name: str, command: str = "scli guest list", timeout: int = 600,
                                interval: int = 10):
        """
        断言资源已在后端创建成功，支持轮询检查。

        :param name: 要检查的资源名称。
        :param command: 用于检查的命令模板，默认为 ``scli guest list``。
        :param timeout: 超时时间（秒），默认为 600 秒。
        :param interval: 轮询间隔时间（秒），默认为 10 秒。
        :raises pytest.skip: 当 SSH 连接未配置时。
        :raises pytest.fail: 当资源在超时时间内未被创建时。
        """
        import pytest

        if not self:
            pytest.skip("SSH host is not configured, skipping backend assertion.")
            return

        end_time = time.time() + timeout
        if command.strip() == "scli guest list":
            check_command = f"scli guest list --name '{name}' | grep -F '{name}'"
        else:
            check_command = f"{command} | grep {name}"
        logger.info(f"开始轮询检查后端资源 '{name}' 是否已创建...")

        while time.time() < end_time:
            result = self.run(check_command)
            if result != "":
                logger.info(f"后端资源 '{name}' 已成功创建。")
                logger.debug(f"资源详情: {result}")
                return

            logger.debug(f"资源 '{name}' 尚未在后端创建，将在 {interval} 秒后重试...")
            time.sleep(interval)

        final_result = self.run(check_command)
        if final_result != "":
            logger.info(f"后端资源 '{name}' 在最后一次检查时已创建。")
            logger.debug(f"资源详情: {final_result}")
        else:
            pytest.fail(f"超时错误：资源 '{name}' 在 {timeout} 秒内未能在后端创建。")

    def set_volume_state(self, volume_ref, state):
        """
        重置云硬盘状态。

        :param volume_ref: 云硬盘标识，可传云硬盘名称或云硬盘 UUID。
        :param state: 目标状态，对应 ``scli volume reset-state --state`` 支持的状态值。
        """
        volume_id = volume_ref if self._extract_uuid(volume_ref) else self.get_volume_id(volume_ref)
        self.run(f"scli volume reset-state --status {state} {volume_id}", check_rc=True)

    def glance_image_create(self, name, image, backend, size=20, purpose="kvm", hw_firmware_type="bios", os_version="centos7.9", **kwargs):
        """
        通过 ``scli image create`` 上传镜像到 OpenStack Glance 服务。

        Args:
            name: 镜像名称。
            image: 镜像文件名。
            backend: 存储后端。
            size: 最小磁盘大小（GB），默认 20GB。
            purpose: 镜像用途，默认 'kvm'。
            hw_firmware_type: 固件类型，默认 'bios'。
            os_version: 操作系统版本，默认 'centos7.9'。
            **kwargs: 额外的镜像属性。
        """
        arch = self.run("arch")
        image_name, hw_firmware_type, os_version = _handle_arch_specific_config(
            arch,
            image,
            hw_firmware_type,
            os_version,
            kwargs,
        )

        self.image_download(image_name)

        disk_format = image_name.rsplit(".", 1)[-1]
        cmd = f'scli image create --name {name} \
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
            --file {image_name} \
            --backend {backend} \
            --progress '

        for key, value in kwargs.items():
            cmd = cmd + f"--property {key}={value} "
        return self.run(cmd, return_stderr=True, check_rc=True)

    def image_download(self, image, img_path="/liaoxb/test_image_dontdel"):
        """为镜像导入准备远端镜像文件。"""
        img_source = Config.get("image_source")
        full_url = rf"{img_source}{img_path}/{image}"
        if image not in self.run("ls"):
            self.run(f"sudo curl {full_url} -o {image}")
            self.file_exist(image)

    def glance_image_delete(self, name):
        """通过 ``scli image delete`` 删除镜像。"""
        image_id = self.run(f"scli image list |grep {name} |awk '{{print $2}}'")
        if image_id:
            self.run(f"scli image delete {image_id}", check_rc=True)
            logger.info(f"镜像 {name} 已删除")
        else:
            logger.info(f"镜像 {name} 不存在，无需删除")
