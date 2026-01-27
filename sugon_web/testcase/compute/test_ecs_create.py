import allure
from sugon_web.testcase.conftest import ecs_page
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, skip_stor


@allure.epic('计算服务')
@allure.feature('弹性云服务器 ECS')
@allure.story('创建功能验证')
class TestECSCreate:

    @allure.title("创建功能验证: 镜像来源")
    def test_ecs_create(self, ecs_page):
        name = random_data()

        with allure_step_log("步骤1: 创建云服务器"):
            ecs_page.ecs_create(name=name)

        with allure_step_log("步骤2: 验证创建结果"):
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title("创建功能验证: 快照来源")
    @skip_stor("usan","local", "nfs")
    def test_ecs_create_with_snapshot(self, ecss, ecs_page, ssh_vm):
        name = random_data()
        snapshot_name = ecss.get("name")
        with allure_step_log("步骤1: 创建启动方式为 快照 的云服务器"):
            ecs_page.ecs_create(name=name, image_source="快照", image_name=snapshot_name)

        with allure_step_log("步骤2: 验证创建结果"):
            # 页面验证
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)
            assert ecs_page.get_row_data(name).get("镜像名称") == snapshot_name, "镜像名称快照不一致"

            # 登录虚机验证
            ip = ecs_page.get_row_data(name).get("IP地址").split(':')[1]
            mfip = ecs_page.bind_mfip(ip.strip())
            ssh_vm.connect(mfip)
            ecs_page.assert_ecs_enable(name, ssh_vm)

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title("创建功能验证: ISO来源")
    @skip_stor("local")
    def test_ecs_create_with_iso(self, ecs_page, image, ssh_vm):
        name = random_data()
        iso_name = image.get("name")
        with allure_step_log("步骤1: 创建启动方式为 ISO 的云服务器"):
            ecs_page.ecs_create(name=name, image_source="ISO", image_name=iso_name)

        with allure_step_log("步骤2: 验证创建结果"):
            # 页面验证
            ecs_page.assert_popup_success("创建实例命令下发成功", timeout=30)
            ecs_page.assert_status(name)
            assert ecs_page.get_row_data(name).get("镜像名称") == iso_name, "镜像名称与ISO镜像名称不一致"
            assert ecs_page.get_row_data(name).get("挂载云硬盘").startswith("cdrom"), "系统盘类型不一致"

        with allure_step_log("步骤3: 登录vnc验证"):
            ecs_page.ecs_vnc(name)

        with allure_step_log("步骤3: 清理测试数据"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)

    @allure.title("创建功能验证: 空启动来源")
    def test_ecs_create_with_empty(self, ecs_page, image, ssh_vm):
        name = random_data()
        iso_name = image.get("name")
        with allure_step_log("步骤1: 创建启动方式为 空启动 的云服务器"):
            ecs_page.ecs_create(name=name, image_source="空启动")
            ecs_page.assert_popup_success("创建实例命令下发成功")

        with allure_step_log("步骤2: 验证创建结果"):
            # 页面验证
            ecs_page.assert_status(name)
            assert ecs_page.get_row_data(name).get("镜像名称") == "--", "镜像名称不为空"

        with allure_step_log(f"步骤3: 为虚机{name}挂载CD-ROM"):
            ecs_page.ecs_mount_cdrom(name, iso_name)

        with allure_step_log(f"步骤4: 验证虚机{name}挂载CD-ROM结果"):
            ecs_page.assert_popup_success(f"挂载CD-ROM到虚拟机{name}成功")
            # ecs_page.wait_for_source_complete(name)
            ecs_page.assert_status(name)
            # 验证CD-ROM已成功挂载
            cdrom_name = ecs_page.get_row_data(name).get("挂载云硬盘")
            assert cdrom_name.startswith("cdrom-")
            # 验证云硬盘状态
            ecs_page.goto_service("云硬盘")
            ecs_page.goto_submenu("云硬盘")
            ecs_page.assert_status(cdrom_name, status="正在使用", refresh=True)

        with allure_step_log("步骤5: 登录vnc验证"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.ecs_vnc(name)

        with allure_step_log(f"步骤6: 卸载CD-ROM"):
            ecs_page.ecs_unmount_cdrom(name, cdrom_name)

        with allure_step_log(f"步骤7: 验证虚机{name}卸载CD-ROM结果"):
            ecs_page.assert_popup_success(f"从虚拟机{name}卸载CD-ROM成功")
            assert ecs_page.get_row_data(name).get("挂载云硬盘") == "--"

        with allure_step_log("步骤8: 清理测试数据"):
            ecs_page.ecs_remove(name)
            ecs_page.ecs_delete(name)
            ecs_page.assert_deleted(name)