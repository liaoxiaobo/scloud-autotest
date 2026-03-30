import time
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, only_stor


@allure.epic('计算服务')
@allure.feature('回收站')
@allure.story('回收站功能验证')
class TestECSRecycle:

    @allure.title("恢复弹性云服务器")
    def test_ecs_recycle_recover(self, ecs_page, vm, ssh_vm):
        name = vm.get("name")
        ecs_page.goto_service('弹性云服务器')
        with allure_step_log(f"步骤1: 虚拟机{name}系统盘写入数据，记录MD5"):
            ssh_vm.connect(vm['mfip'])
            md5 = ssh_vm.create_file(name)

        with allure_step_log(f"步骤2: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            time.sleep(3)
            ecs_page.assert_deleted(name)

        with allure_step_log("步骤3: 恢复弹性云服务器"):
            ecs_page.goto_submenu("回收站")
            ecs_page.ecs_recover(name)
            ecs_page.assert_popup_success(f"移出回收站成功")
            ecs_page.assert_deleted(name)

        with allure_step_log("步骤4: 验证恢复结果"):
            ecs_page.goto_service('弹性云服务器')
            ecs_page.assert_status(name, refresh=True)
            ssh_vm.connect(vm['mfip'])
            ecs_page.assert_ecs_enable(name, ssh_vm, timeout=90)
            assert md5 in ssh_vm.run(f"md5sum {name}"), "恢复后系统盘数据MD5不一致"
            assert ssh_vm.create_file(name) is not None, "恢复后系统盘数据不能写入"

    @allure.title("列表页搜索&重置")
    def test_ecs_recycle_search(self, ecs_page, vm):
        name = vm.get("name")
        with allure_step_log(f"步骤1: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            time.sleep(1)
            ecs_page.assert_deleted(name)

        with allure_step_log("步骤2: 输入名称进行搜索"):
            ecs_page.goto_submenu("回收站")
            keyword = vm['name'][:-2]
            ecs_page.search(keyword)
            ecs_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            ecs_page.btn_reset.click()
            ecs_page.wait_for_page_ready()
            # 断言重置后搜索输入框已清空
            assert ecs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 恢复弹性云服务器"):
            ecs_page.goto_submenu("回收站")
            ecs_page.ecs_recover(name)
            ecs_page.assert_popup_success(f"移出回收站成功")
            ecs_page.assert_deleted(name)
            ecs_page.goto_service('弹性云服务器')
            ecs_page.assert_status(name, refresh=True)

    @allure.title("删除弹性云服务器")
    def test_ecs_recycle_remove(self, ecs_page, ssh_host):
        name = random_data()
        with allure_step_log("步骤1: 创建云服务器并验证创建结果"):
            ecs_page.ecs_create(name=name)
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)

        with allure_step_log(f"步骤2: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            ecs_page.assert_deleted(name)

        with allure_step_log("步骤3: 验证删除结果"):
            ecs_page.ecs_recover_delete(name)
            ecs_page.assert_deleted(name)
            ssh_host.wait_vm_deleted(name)


    @allure.title("批量删除弹性云服务器")
    def test_ecs_recycle_batch_remove(self, ecs_page, ssh_host):
        """测试弹性云服务器批量删除功能"""

        # 批量创建弹性云服务器用于测试
        ecs_names = []
        ids = []
        with allure_step_log("步骤1: 批量创建弹性云服务器"):
            base_name = random_data()
            ecs_page.ecs_create(
                base_name,
                count=3
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")

            # 生成批量创建的云硬盘名称列表
            for i in range(3):
                name = f"{base_name}-{i}"
                ecs_names.append(name)
                ids.append(ecs_page.get_row_data(name).get("名称/ID").split(':')[1])

            # 验证所有弹性云服务器创建成功
            for name, ecs_id in zip(ecs_names, ids):
                ecs_page.assert_status(name)
                stdout = ecs_page.stout_to_dict(ssh_host.run(f"gova show {ecs_id}"))
                assert stdout.get("vm_state") == "active", f"{name}后台状态不是active，状态为:{stdout.get('vm_state')}"

        # 批量回收弹性云服务器
        with allure_step_log("步骤2: 批量回收弹性云服务器"):
            ecs_page.ecs_batch_operations(ecs_names, "批量删除")

        # 批量删除回收站中的弹性云服务器
        with allure_step_log("步骤3: 批量删除回收站中的弹性云服务器"):
            ecs_page.ecs_recover_batch_delete(ecs_names)

        with allure_step_log("步骤4: 验证删除结果"):
            ecs_page.wait_for_page_ready()
            # 验证弹性云服务器已彻底删除
            ecs_page.assert_deleted(ecs_names)
            ssh_host.wait_vm_deleted(ecs_names)

    @only_stor('xstor')
    @allure.title("安全删除功能验证")
    def test_ecs_recycle_secure_delete(self, ecs_page, ssh_host):
        """测试弹性云服务器删除功能，包括普通删除和安全删除"""

        name = random_data()
        with allure_step_log("步骤1: 创建云服务器并验证创建结果"):
            ecs_page.ecs_create(name=name)
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(name)

        with allure_step_log(f"步骤2: 删除云服务器{name}"):
            ecs_page.ecs_remove(name)
            ecs_page.assert_deleted(name)

        with allure_step_log("步骤3: 验证删除成功提示"):
            # 导航到回收站页面
            ecs_page.goto_submenu("回收站")

        with allure_step_log("步骤4: 安全删除云服务器"):
            # 从回收站安全删除
            ecs_page.ecs_delete(name, secure=True)

        with allure_step_log("步骤5: 验证资源已完全删除"):
            # 验证资源已完全删除
            ecs_page.assert_deleted(name)
            ssh_host.wait_vm_deleted(name)
