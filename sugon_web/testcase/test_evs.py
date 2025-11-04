import pytest
import allure
from sugon_web.utils.util import random_data, load_data


@allure.epic('存储服务')
@allure.feature('云硬盘 EVS')
class TestEVS:

    @allure.title("云硬盘-创建功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_create'))
    def test_volume_create(self, evs_page, params):
        name=random_data()

        with allure.step("创建云硬盘"):
            # 使用测试数据中的参数
            evs_page.evs_create(
                name,
                empty=params['empty'],
                size=params["size"],
                desc=params["desc"],
            )

        with allure.step("验证创建结果"):
            evs_page.assert_popup_success()
            evs_page.assert_status(name, status="可用")

        with allure.step("清理测试数据"):
            evs_page.evs_remove(name)
            evs_page.evs_delete(name)
            evs_page.assert_deleted(name)

    @allure.title("云硬盘-页面列表搜索结果验证")
    def test_volume_search(self, evs_page, volume):
        evs_page.goto_submenu("云硬盘")
        keyword = volume['name'][:-2]
        evs_page.search(keyword)
        evs_page.assert_list_contain(keyword)

    @allure.title("云硬盘-修改功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_modify'))
    def test_volume_modify(self, evs_page, volume, params):
        old_name = volume["name"]
        new_name = old_name + params["new_name_suffix"]
        new_desc = params["new_desc"]
        
        with allure.step("修改云硬盘"):
            evs_page.evs_modify(old_name, new_name, new_desc)
            
        with allure.step("验证修改结果"):
            evs_page.assert_popup_success()
            # 更新 name，便于 fixture teardown 阶段正确清理
            volume["name"] = new_name
            evs_page.assert_list_contain(new_name)

    @allure.title("云硬盘-克隆功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_clone'))
    def test_volume_clone(self, evs_page, volume, params):
        source_name = volume["name"]
        clone_name = params["clone_name_prefix"] + source_name
        
        with allure.step("克隆云硬盘"):
            evs_page.evs_clone(source_name, clone_name)
            
        with allure.step("验证克隆结果"):
            evs_page.assert_popup_success()
            evs_page.assert_list_contain(clone_name)
            evs_page.assert_status(clone_name, status="可用")

        with allure.step("清理克隆的云硬盘"):
            # 清理
            evs_page.evs_remove(clone_name)
            evs_page.evs_delete(clone_name)
            evs_page.assert_deleted(clone_name)

    @allure.title("云硬盘-扩容功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_expand'))
    def test_volume_expand(self, evs_page, volume, params):
        name = volume["name"]
        new_size = params["new_size"]
        
        with allure.step("扩容云硬盘"):
            evs_page.evs_expand(name, new_size)
            
        with allure.step("验证扩容结果"):
            evs_page.assert_popup_success()
            evs_page.assert_status(name, status="可用")

    @allure.title("云硬盘-添加快照功能验证")
    @pytest.mark.parametrize("params", load_data('test_volume_add_snapshot'))
    def test_volume_add_snapshot(self, evs_page, volume, params):
        snapshot_name = params["snapshot_name_prefix"] + random_data()
        desc = params["desc"]
        
        with allure.step("创建快照"):
            evs_page.evs_add_snapshot(volume["name"], snapshot_name, desc)
            
        with allure.step("验证快照创建"):
            evs_page.assert_popup_success()
            evs_page.goto_submenu("快照")
            evs_page.assert_status(snapshot_name, status="可用")
            
        with allure.step("清理快照"):
            evs_page.evss_delete(snapshot_name)
            evs_page.assert_deleted(snapshot_name)


class TestEVSS:

    pass
