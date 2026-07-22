import re

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsVolumeMixin(BasePage):
    """ECS 磁盘与卷操作。"""
    @submenu("弹性云服务器")
    def ecs_mount_to_server(self, volume_name, vm_name):
        """将云硬盘挂载到指定服务器

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """
        # 点击挂载云硬盘选项
        self.click_action(vm_name, "挂载云硬盘")

        # 搜索云硬盘
        self.get_by_label("挂载云硬盘").get_by_placeholder("搜索（名称）").fill(volume_name)
        self.get_by_label("挂载云硬盘").get_by_text("搜索").click()

        # 选择云硬盘
        self.get_by_role("row").filter(has_text=volume_name).get_by_role("radio").click()

        # 确认挂载
        self.get_by_label("挂载云硬盘").get_by_text("挂载", exact=True).click()
        logger.info(f"操作完成: 云硬盘{volume_name}挂载到服务器{vm_name}")


    @submenu("弹性云服务器")
    def ecs_unmount_from_server(self, volume_name, vm_name):
        """从指定服务器卸载云硬盘

        Args:
            volume_name: 云硬盘名称
            vm_name: 服务器名称
        """

        # 点击卸载云硬盘选项
        self.click_action(vm_name, "卸载云硬盘")

        # 选择云硬盘
        self.get_by_placeholder("请选择云硬盘").click()
        self.locator("span").filter(has_text=re.compile(rf"^{volume_name}$")).click()

        # 确认卸载
        self.dialog_confirm.click()
        logger.info(f"操作完成: 云硬盘{volume_name}从服务器{vm_name}卸载")


    @submenu("弹性云服务器")
    def ecs_expand_system_disk(self, name: str, new_size: str):
        """扩容弹性云服务器系统盘

        Args:
            name: 云服务器名称
            new_size: 新的系统盘大小（GiB）
        """
        logger.info(f"开始扩容云服务器系统盘: {name}，扩容至: {new_size}GiB")

        # 点击下拉菜单中的"系统盘扩容"选项
        self.click_action(name, "系统盘扩容")

        # 设置新的系统盘大小
        self.get_by_label("系统盘扩容").get_by_role("spinbutton").fill(new_size)

        # 确认扩容
        self.dialog_confirm.click()

        logger.info(f"云服务器系统盘扩容成功: {name}")


    @submenu("弹性云服务器")
    def ecs_mount_cdrom(self, name: str, iso_name: str = None):
        """
        为指定弹性云服务器挂载CD-ROM

        Args:
            name: 云服务器名称
            iso_name: CD-ROM名称，如果为None则使用自动生成的名称
        """
        # 点击云服务器操作按钮
        self.click_action(name, "挂载CD-ROM")

        # 选择CD-ROM类型（如果需要选择）
        try:
            # 根据类型iso名称选择对应的单选按钮
            self.get_by_label("挂载CD-ROM").get_by_placeholder("搜索（名称）").fill(iso_name)
            self.get_by_label("挂载CD-ROM").get_by_text("搜索").click()
            self.get_by_label("挂载CD-ROM").get_by_role("radio").first.click()
        except:
            logger.warning(f"未找到CD-ROM '{iso_name}' ，默认选择第一个CD-ROM")
            self.get_by_label("挂载CD-ROM").get_by_text("重置").click()
            self.get_by_label("挂载CD-ROM").get_by_role("row").filter(has_text="autotest").get_by_role(
                "radio").first.click()

        # 点击挂载按钮
        self.get_by_label("挂载CD-ROM").get_by_text("挂载", exact=True).click()
        logger.info(f"云服务器{name}挂载CD-ROM请求已提交")


    @submenu("弹性云服务器")
    def ecs_unmount_cdrom(self, name: str, cdrom_name: str = None):
        """
        为指定弹性云服务器挂载CD-ROM

        Args:
            name: 云服务器名称
            cdrom_name: CD-ROM名称
        """
        # 点击云服务器操作按钮
        self.click_action(name, "卸载CD-ROM")

        # 选择CD-ROM
        self.get_by_placeholder("请选择CD-ROM").click()
        self.locator("li").filter(has_text=cdrom_name).click()

        # 点击挂载按钮
        self.dialog_confirm.click()
        logger.info(f"云服务器{name}卸载CD-ROM请求已提交")


    @submenu("弹性云服务器")
    def ecs_mount_bare_disk(self, name: str, pool_name: str):
        """为云服务器挂载裸磁盘

        Args:
            name: 云服务器名称
            pool_name: 存储池名称
        """

        # 点击挂载裸磁盘选项
        self.click_action(name, "挂载裸磁盘")

        # 选择存储池
        self.get_by_placeholder("请选择存储池").click()
        # 查找包含存储池名称和总量的选项
        self.locator("li").filter(has_text=re.compile(rf"{pool_name}.*总量:")).click()

        # 选择磁盘
        self.get_by_placeholder("请输入名称").fill(pool_name)

        # 选择挂载裸磁盘选项
        self.get_by_label("挂载裸磁盘").get_by_role("radio").first.click()

        # 确认挂载
        self.get_by_label("挂载裸磁盘").get_by_text("挂载", exact=True).click()
        logger.info(f"为云服务器{name}挂载裸磁盘: 存储池={pool_name}")


    @submenu("弹性云服务器")
    def ecs_unmount_bare_disk(self, name: str, pool_name: str = None):
        """为云服务器卸载裸磁盘

        Args:
            name: 云服务器名称
        """

        # 点击挂载裸磁盘选项
        self.click_action(name, "卸载裸磁盘")

        # 选择裸磁盘
        self.get_by_label("卸载裸磁盘").get_by_role("radio").click()

        # 确认卸载
        self.dialog_confirm.click()
        logger.info(f"为云服务器{name}卸载裸磁盘: 裸磁盘={pool_name}")
