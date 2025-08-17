import pytest
import allure
from sugon_web.utils.util import random_data


@allure.epic('存储服务')
@allure.feature('云硬盘 EVS')
class TestEVS:

    @allure.title("云硬盘-创建功能验证")
    @pytest.mark.parametrize("empty, size, desc", [(True, 30, "页面测试描述"),(False, 50, "test_description")])
    def test_volume_create(self, evs_page, empty, size, desc):
        name=random_data()
        evs_page.evs_create(name, empty=empty, size=size, desc=desc)

        evs_page.assert_popup_success()
        evs_page.assert_status(name, status="可用")

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
    def test_volume_modify(self, evs_page, volume):
        old_name = volume["name"]
        new_name = old_name + "222"
        new_desc = "少时诵诗书少时诵诗书3331112222"
        evs_page.evs_modify(old_name, new_name, new_desc)
        evs_page.assert_popup_success()

        # 更新 name，便于 fixture teardown 阶段正确清理
        volume["name"] = new_name

        # 可选：断言新名称/描述已生效
        evs_page.assert_list_contain(new_name)

    @allure.title("云硬盘-克隆功能验证")
    def test_volume_clone(self, evs_page, volume):
        source_name = volume["name"]
        clone_name = "clone-" + source_name
        evs_page.evs_clone(source_name, clone_name)
        evs_page.assert_popup_success()
        # 可选：断言克隆后的云硬盘出现在列表
        evs_page.assert_list_contain(clone_name)
        evs_page.assert_status(clone_name, status="可用")
        # 清理
        evs_page.evs_remove(clone_name)
        evs_page.evs_delete(clone_name)
        evs_page.assert_deleted(clone_name)

    @allure.title("云硬盘-扩容功能验证")
    def test_volume_expand(self, evs_page, volume):
        name = volume["name"]
        new_size = 50
        evs_page.evs_expand(name, new_size)
        evs_page.assert_popup_success()
        # 可选：断言扩容后容量已变更（如有相关断言方法，可补充）
        # evs_page.assert_volume_size(name, new_size)
        evs_page.assert_status(name, status="可用")

    @allure.title("云硬盘-添加快照功能验证")
    def test_volume_add_snapshot(self, evs_page, volume):
        snapshot_name = random_data()
        desc = "三生三世十里桃花"
        evs_page.evs_add_snapshot(volume["name"], snapshot_name, desc)
        evs_page.assert_popup_success()
        evs_page.goto_submenu("快照")
        evs_page.assert_status(snapshot_name, status="可用")
        evs_page.evss_delete(snapshot_name)
        evs_page.assert_deleted(snapshot_name)


class TestEVSS:

    pass
