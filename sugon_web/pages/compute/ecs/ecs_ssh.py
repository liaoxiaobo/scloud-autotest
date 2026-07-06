from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class EcsSshMixin(BasePage):
    """ECS SSH 后端辅助方法。"""

    # 预置数据文件参数：1GB = 1M * 1024
    _CBR_TEST_FILE_NAME = "test"
    _CBR_TEST_BS = "1M"
    _CBR_TEST_COUNT = 1024

    def _get_system_disk_name(self, ssh_vm):
        """识别系统盘设备名。"""
        sys_disk = ssh_vm.run("lsblk -no PKNAME,MOUNTPOINT | grep -w '/' | awk '{print $1}'", check_rc=True).strip()
        if not sys_disk:
            sys_disk = ssh_vm.run("lsblk -no NAME,MOUNTPOINT | grep -w '/' | awk '{print $1}'", check_rc=True).strip()
        logger.info(f"识别到系统盘: {sys_disk}")
        return sys_disk


    def _get_target_volumes(self, ssh_vm, sys_disk):
        """获取需要预置数据的磁盘列表，系统盘排在首位。"""
        actual_disks_output = ssh_vm.run(r"""lsblk -dn -o NAME,TYPE | awk '$2 == "disk" {print $1}'""", check_rc=True)
        actual_disks = list(dict.fromkeys(disk.strip() for disk in actual_disks_output.splitlines() if disk.strip()))
        if sys_disk and sys_disk not in actual_disks:
            actual_disks.insert(0, sys_disk)
        return [sys_disk] + [vol for vol in actual_disks if vol != sys_disk]


    @staticmethod
    def _get_volume_directory(vol_name, sys_disk):
        """返回磁盘预置数据目录。"""
        if vol_name == sys_disk:
            return "/cbr_test_root"
        return f"/cbr_test_{vol_name}"


    def _prepare_data_volume_mount(self, ssh_vm, vol_name, mount_dir):
        """格式化并挂载数据盘，同时写入开机挂载配置。"""
        ssh_vm.run(f"mkfs.xfs -f /dev/{vol_name}", check_rc=True)
        ssh_vm.run(f"mkdir -p {mount_dir}", check_rc=True)
        ssh_vm.run(f"mount /dev/{vol_name} {mount_dir}", check_rc=True)
        uuid = ssh_vm.run(
            rf"""blkid|grep /dev/{vol_name}|awk -F" " '{{print $2}}'|awk -F'"' '{{print $2}}'""",
            check_rc=True
        ).strip()
        ssh_vm.run(f"""echo "UUID={uuid} {mount_dir} xfs defaults 0 0" >> /etc/fstab""", check_rc=True)


    def _generate_volume_test_data(self, ssh_vm, curr_dir, vol_name):
        """在目标目录下生成 1GB 随机测试文件并记录 MD5。"""
        file_path = f"{curr_dir}/{self._CBR_TEST_FILE_NAME}"

        ssh_vm.run(
            f"mkdir -p {curr_dir} && "
            f"dd if=/dev/urandom of={file_path} "
            f"bs={self._CBR_TEST_BS} count={self._CBR_TEST_COUNT} 2>/dev/null && "
            f"sync",
            check_rc=True,
            timeout=900,
        )
        logger.info(f"{vol_name} 盘已生成 1GB 测试文件: {file_path}")

        ssh_vm.run(
            f"cd {curr_dir} && md5sum {self._CBR_TEST_FILE_NAME} > cbr_test_{vol_name}_md5.txt",
            check_rc=True,
        )
        return ssh_vm.run(
            f"cd {curr_dir} && md5sum {self._CBR_TEST_FILE_NAME} | awk '{{print $1}}'",
            check_rc=True,
        ).strip()


    def vm_pre_data(self, ssh_vm):
        """虚机预置数据：本地生成 1GB 随机文件，不依赖外部镜像和公网 IP。"""
        md5_dict = {}

        sys_disk = self._get_system_disk_name(ssh_vm)
        target_vols = self._get_target_volumes(ssh_vm, sys_disk)

        for vol_name in target_vols:
            key = 'root' if vol_name == sys_disk else vol_name
            curr_dir = self._get_volume_directory(vol_name, sys_disk)
            curr_file = self._CBR_TEST_FILE_NAME

            if vol_name == sys_disk:
                ssh_vm.run(f"mkdir -p {curr_dir}", check_rc=True)
                logger.info(f"处理系统盘: {vol_name}, 写入文件: {curr_file}")
            else:
                logger.info(f"处理数据盘: {vol_name}, 写入文件: {curr_file}")
                self._prepare_data_volume_mount(ssh_vm, vol_name, curr_dir)

            md5_val = self._generate_volume_test_data(ssh_vm, curr_dir, vol_name)
            md5_dict[key] = {
                'md5': md5_val,
                'dir': curr_dir,
                'file': curr_file
            }

        return md5_dict
