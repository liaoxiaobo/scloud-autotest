import pytest
import allure
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data, load_data, skip_stor


@allure.epic('存储服务')
@allure.feature('云硬盘')
@allure.story('云硬盘-基本功能验证')
class TestEVSBasic:

    @allure.title("云硬盘-批量创建和批量删除")
    def test_volume_batch_delete(self, evs_page, ssh_host):

        volume_names = []
        with allure_step_log("步骤1: 批量创建云硬盘"):
            base_name = random_data()
            evs_page.evs_create(
                name=base_name,
                count=3,
                size=10,
                desc="批量删除测试云硬盘"
            )
            evs_page.assert_popup_success("创建云硬盘成功")

            # 生成批量创建的云硬盘名称列表
            for i in range(1, 4):
                volume_names.append(f"{base_name}-{i}")

            # 验证所有云硬盘创建成功
            evs_page.assert_status(volume_names, status="可用")

        with allure_step_log("步骤2: 批量回收云硬盘"):
            evs_page.evs_remove(volume_names)
            # evs_page.assert_popup_success()

        with allure_step_log("步骤3: 批量删除回收站中的云硬盘"):
            evs_page.evs_delete(volume_names)
            # evs_page.assert_popup_success()

        # 验证云硬盘已彻底删除
        evs_page.assert_deleted(volume_names)
        ssh_host.wait_volume_deleted(volume_names)

    @allure.title("云硬盘-搜索和重置")
    def test_volume_search(self, evs_page, volume):

        with allure_step_log("步骤1: 输入名称进行搜索"):
            evs_page.goto_submenu("云硬盘")  # TODO: 连跑时会处于回收站页，加跳转解决
            keyword = volume['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            evs_page.btn_reset.click()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("云硬盘-修改")
    @pytest.mark.parametrize("params", load_data('test_modify'))
    def test_volume_edit(self, evs_page, volume, params):

        new_name = volume["name"] + params["name_suffix"]
        new_desc = params["new_desc"]

        with allure_step_log("步骤1: 修改云硬盘的名称和描述"):
            evs_page.evs_edit(volume["name"], new_name, new_desc)
            evs_page.assert_popup_success("执行成功")
            evs_page.assert_list_contain(new_name)

    @allure.title("云硬盘-克隆")
    def test_volume_clone(self, evs_page, volume, ssh_host):

        clone_name = "clone_" + volume["name"]

        with allure_step_log("步骤1: 克隆云硬盘"):
            evs_page.evs_clone(volume["name"], clone_name)
            evs_page.assert_popup_success("克隆云硬盘成功")
            evs_page.assert_status(clone_name, status="可用")

        with allure_step_log("步骤2: 清理克隆的云硬盘"):
            evs_page.evs_remove(clone_name)
            evs_page.evs_delete(clone_name)
            evs_page.assert_deleted(clone_name)
            ssh_host.wait_volume_deleted(clone_name)

    @allure.title("云硬盘-扩容")
    @pytest.mark.parametrize("params", load_data('test_volume_expand'))
    def test_volume_expand(self, evs_page, volume, params, ssh_host):

        name = volume["name"]
        new_size = params["new_size"]

        with allure_step_log("步骤1: 扩容云硬盘"):
            evs_page.evs_expand(name, new_size)
            evs_page.assert_popup_success("执行成功")
            evs_page.assert_status(name, status="可用")
            assert ssh_host.get_volume_size(volume["name"]) == int(new_size)

    @allure.title("云硬盘-启用QoS")
    def test_volume_enable_qos(self, evs_page, volume):

        with allure_step_log("步骤1: 启用云硬盘QoS限制"):
            evs_page.evs_enable_qos(
                volume_name=volume["name"],
                read_speed=100,
                write_speed=100,
                read_iops=200,
                write_iops=200
            )
            evs_page.assert_popup_success("设置单卷QoS成功")

    @allure.title("云硬盘-关闭QoS")
    def test_volume_disable_qos(self, evs_page, volume):

        with allure_step_log("步骤1: 关闭云硬盘QoS限制"):
            evs_page.evs_disable_qos(volume_name=volume["name"])
            evs_page.assert_popup_success("设置单卷QoS成功")

    @allure.title("云硬盘-挂载和卸载")
    def test_volume_bind_vm(self, evs_page, vm, volume, ssh_vm):
        with allure_step_log("步骤1: 挂载云硬盘"):
            evs_page.evs_mount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="正在使用")
            disk_name = evs_page.get_row_data(volume["name"]).get("挂载信息").split("上的")[-1]
            ssh_vm.connect(vm['mfip'])
            assert ssh_vm.run(f"lsblk | grep {disk_name}") != ""

        with allure_step_log("步骤2: 卸载云硬盘"):
            evs_page.evs_unmount(volume["name"], vm["name"])
            evs_page.assert_popup_success()
            evs_page.assert_status(volume["name"], status="可用")
            assert evs_page.get_row_data(volume["name"]).get("挂载信息") == "--"
            assert ssh_vm.run(f"lsblk | grep {disk_name}") == ""

    @skip_stor("local")
    @allure.title("云硬盘-转换为镜像")
    def test_volume_convert_to_image(self, ecs_page, evs_page, ssh_host):

        name = random_data()
        with allure_step_log("步骤1: 创建带镜像的云硬盘"):
            evs_page.evs_create(name, empty=False)
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

        with allure_step_log("步骤2: 将云硬盘转换为镜像"):
            image_name = "image_from_volume_" + name
            evs_page.evs_convert_to_image(
                volume_name=name,
                image_name=image_name
            )
            evs_page.assert_popup_success()
            evs_page.assert_status(name, status="可用", timeout=1200)

            # 切换到弹性云服务器服务的镜像服务页面
            evs_page.goto_service("弹性云服务器")
            evs_page.goto_submenu("镜像服务")
            ecs_page.assert_status(image_name, status="可用", timeout=1200)

        with allure_step_log("步骤3：清理测试数据"):
            # 删除创建的镜像
            ecs_page.ecs_image_delete(image_name)
            ecs_page.assert_deleted(image_name)
            # 删除创建的云硬盘
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)
            ssh_host.wait_volume_deleted(name)

    @allure.title("云硬盘-重置状态")
    def test_volume_reset_status(self, evs_page, volume, ssh_host):

        with allure_step_log("步骤1: 构造删除中的云硬盘"):
            ssh_host.set_volume_state(volume["name"], "deleting")
            evs_page.goto_submenu('云硬盘')
            evs_page.assert_status(volume["name"], status="删除中", refresh=True)

        with allure_step_log("步骤2: 重置云硬盘状态"):
            evs_page.evs_reset_status(volume["name"])
            evs_page.assert_popup_success("重置状态成功")
            evs_page.assert_status(volume["name"], status="错误")

        with allure_step_log("步骤3: 恢复云硬盘状态"):
            ssh_host.set_volume_state(volume["name"], "available")
            evs_page.assert_status(volume["name"], status="可用", refresh=True)

    @allure.title("云硬盘-查看快照")
    def test_volume_view_snapshots(self, evs_page, volume, evss):

        with allure_step_log("步骤1: 查看快照"):
            evs_page.evs_view_snapshots(volume["name"])
            evs_page.assert_list_contain(evss["name"])
            snapshot_data = evs_page.get_row_data(evss["name"])
            assert snapshot_data["名称"] == evss["name"]
            assert snapshot_data["云硬盘名称"] == volume["name"]

    @allure.title("云硬盘-移入和移出回收站")
    def test_volume_restore(self, evs_page, volume):

        with allure_step_log("步骤1: 云硬盘移入回收站"):
            evs_page.evs_remove(volume["name"])

        with allure_step_log("步骤2: 从回收站恢复云硬盘"):
            evs_page.evs_restore(volume["name"])
            evs_page.goto_submenu("云硬盘")
            evs_page.assert_status(volume["name"], status="可用")

    @allure.title("云硬盘-回收站搜索和重置")
    def test_garbage_search(self, evs_page, volume):

        with allure_step_log("步骤1: 云硬盘移入回收站"):
            evs_page.evs_remove(volume["name"])

        with allure_step_log("步骤2: 输入名称进行搜索"):
            evs_page.goto_submenu("回收站")
            keyword = volume['name'][:-2]
            evs_page.search(keyword)
            evs_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤3: 重置搜索条件"):
            evs_page.btn_reset.click()
            assert evs_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

        with allure_step_log("步骤4: 从回收站恢复云硬盘"):
            evs_page.evs_restore(volume["name"])
            evs_page.assert_popup_success(f"云硬盘{volume['name']}移出回收站成功")

    @skip_stor("local","usan",'nfs')
    @allure.title("云硬盘-安全删除")
    def test_volume_secure_delete(self, evs_page, ssh_host):

        name = random_data()
        with allure_step_log("步骤1: 创建云硬盘"):
            evs_page.evs_create(name)
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")

        with allure_step_log("步骤2: 云硬盘移入回收站"):
            evs_page.evs_remove(name)

        with allure_step_log("步骤3: 安全删除云硬盘"):
            evs_page.evs_delete(name, secure=True)
            evs_page.assert_deleted(name)
            ssh_host.wait_volume_deleted(name)
