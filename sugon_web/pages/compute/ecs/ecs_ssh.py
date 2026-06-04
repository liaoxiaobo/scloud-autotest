from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger
from sugon_web.config.config import Config

class EcsSshMixin(BasePage):
    """ECS SSH 后端辅助方法。"""
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
    def _get_volume_file_name(vol_name, sys_disk, data_vols):
        """根据磁盘角色返回用于校验的文件名。"""
        if vol_name == sys_disk:
            return "IMAGE_CDB_20220910.qcow2"
        return "CentOS-7-aarch64-Minimal-2009.iso" if vol_name == data_vols[0] else "cn_windows_7_professional_x64_dvd_x15-65791.iso"


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


    def _write_volume_test_data(self, ssh_vm, curr_dir, curr_file, vol_name, image_path):
        """下载测试文件并生成 MD5 校验文件。"""
        wget_cmd = f"cd {curr_dir} && curl -O --max-time 300 {Config.get('image_source')}{image_path}{curr_file}"
        ssh_vm.run(wget_cmd, timeout=180, get_pty=False, check_rc=True)
        ssh_vm.run(f"cd {curr_dir} && sync && md5sum {curr_file} > cbr_test_{vol_name}_md5.txt", check_rc=True)
        return ssh_vm.run(f"cd {curr_dir} && md5sum {curr_file} | awk '{{print $1}}'", check_rc=True).strip()


    def vm_pre_data(self, ssh_vm):
        """虚机预置数据"""
        md5_dict = {}
        image_path = "/offlinePackage/image_download/support-fsagent/"

        # 通过 lsblk 判断系统盘和数据盘, 获取父设备名，排除分区号
        # 解决 guest os 内核内的行为，os 内部枚举设备的时候具有不稳定性
        sys_disk = self._get_system_disk_name(ssh_vm)
        target_vols = self._get_target_volumes(ssh_vm, sys_disk)
        data_vols = [vol for vol in target_vols if vol != sys_disk]
        for vol_name in target_vols:
            curr_file = self._get_volume_file_name(vol_name, sys_disk, data_vols)
            curr_dir = self._get_volume_directory(vol_name, sys_disk)
            if vol_name == sys_disk:
                # 系统盘: 直接写数据到预定目录，不用分区/格式化/挂载
                ssh_vm.run(f"mkdir -p {curr_dir}", check_rc=True)
                logger.info(f"处理系统盘: {vol_name}, 写入文件: {curr_file}")
            else:
                # 数据盘: 需要格式化、挂载后再写数据
                logger.info(f"处理数据盘: {vol_name}, 写入文件: {curr_file}")
                self._prepare_data_volume_mount(ssh_vm, vol_name, curr_dir)

            # 统一在目标目录下建立路径并写入数据
            md5_val = self._write_volume_test_data(ssh_vm, curr_dir, curr_file, vol_name, image_path)
            key = 'root' if vol_name == sys_disk else vol_name
            md5_dict[key] = {
                'md5': md5_val,
                'dir': curr_dir,
                'file': curr_file
            }

        return md5_dict
