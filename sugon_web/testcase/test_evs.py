import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('存储服务')
@allure.feature('云硬盘 EVS')
class TestEVS:

    @allure.title("云硬盘-创建&删除")
    @pytest.mark.parametrize("params", load_data('test_volume_create'))
    def test_volume_create(self, evs_page, params):
        name=random_data()

        with allure.step("创建云硬盘"):
            evs_page.evs_create(
                name,
                empty=params['empty'],
                size=params["size"],
                desc=params["desc"],
            )

        with allure.step("验证创建结果"):
            evs_page.assert_popup_success("创建云硬盘成功")
            evs_page.assert_status(name, status="可用")
            data = evs_page.get_row_details(name)

            if not params['empty']:
                assert data['可启动'] == '是'
            else:
                assert data['可启动'] == '否'
            assert data['容量'] == str(params["size"]) + "GiB"
            # assert data['描述'] == params["desc"]

        with allure.step("清理测试数据"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)

    @allure.title("云硬盘-页面列表搜索")
    def test_volume_search(self, evs_page, volume):
        keyword = volume['name'][:-2]
        evs_page.search(keyword)
        evs_page.assert_list_contain(keyword)

    @allure.title("云硬盘-修改名称")
    @pytest.mark.parametrize("params", load_data('test_volume_modify'))
    def test_volume_modify(self, evs_page, volume, params):
        new_name = volume["name"] + params["name_suffix"]
        new_desc = params["new_desc"]
        
        with allure.step("修改云硬盘"):
            evs_page.evs_modify(volume["name"], new_name, new_desc)
            
        with allure.step("验证修改结果"):
            evs_page.assert_popup_success("执行成功")
            # 更新 name，便于 fixture teardown 阶段正确清理
            volume["name"] = new_name
            evs_page.assert_list_contain(new_name)

    @allure.title("云硬盘-克隆")
    def test_volume_clone(self, evs_page, volume):
        clone_name = "clone_" + volume["name"]
        
        with allure.step("克隆云硬盘"):
            evs_page.evs_clone(volume["name"], clone_name)
            
        with allure.step("验证克隆结果"):
            evs_page.assert_popup_success("克隆云硬盘成功")
            evs_page.assert_status(clone_name, status="可用")

        with allure.step("清理克隆的云硬盘"):
            evs_page.evs_remove(clone_name)
            evs_page.evs_delete(clone_name)
            evs_page.assert_deleted(clone_name)

    @allure.title("云硬盘-扩容")
    @pytest.mark.parametrize("params", load_data('test_volume_expand'))
    def test_volume_expand(self, evs_page, volume, params):
        name = volume["name"]
        new_size = params["new_size"]
        
        with allure.step("扩容云硬盘"):
            evs_page.evs_expand(name, new_size)
            
        with allure.step("验证扩容结果"):
            evs_page.assert_popup_success("执行成功")
            evs_page.assert_status(name, status="可用")

    @allure.title("云硬盘-添加&删除快照")
    @pytest.mark.parametrize("params", load_data('test_volume_add_snapshot'))
    def test_volume_add_snapshot(self, evs_page, volume, params):
        snapshot_name = params["snapshot_name_prefix"] + random_data()

        with allure.step("创建快照"):
            evs_page.evs_add_snapshot(volume["name"], snapshot_name, params["desc"])
            
        with allure.step("验证快照创建"):
            evs_page.assert_popup_success("创建快照成功")
            evs_page.goto_submenu("快照")
            evs_page.assert_status(snapshot_name, status="可用")
            
        with allure.step("清理快照"):
            evs_page.evss_delete(snapshot_name)
            evs_page.assert_deleted(snapshot_name)

