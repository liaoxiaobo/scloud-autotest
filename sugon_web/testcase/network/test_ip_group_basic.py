import allure

from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic("网络服务")
@allure.feature("负载均衡-IP地址组")
@allure.story("基本功能验证")
class TestIpGroupBasic:

    @allure.title("验证新建与删除IP地址组功能")
    def test_ip_group_create_delete(self, vpc_page):
        group_name = f"ipg-{random_data()}"
        ip_addresses = ["10.10.10.10"]
        desc = f"{group_name}基础创建删除"

        with allure_step_log("步骤1: 新建IP地址组"):
            vpc_page.ip_group_create(
                name=group_name,
                ip_addresses=ip_addresses,
                desc=desc,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表页数据"):
            row_data = vpc_page.get_row_data(group_name)
            assert row_data.get("名称") == group_name, \
                f"IP地址组名称校验失败，期望: {group_name}，实际: {row_data.get('名称')}"
            assert "10.10.10.10" in row_data.get("包含IP地址", ""), \
                f"IP地址校验失败，期望包含: 10.10.10.10，实际: {row_data.get('包含IP地址')}"
            assert desc in row_data.get("描述", ""), \
                f"描述校验失败，期望包含: {desc}，实际: {row_data.get('描述')}"

        with allure_step_log("步骤3: 删除IP地址组"):
            vpc_page.ip_group_delete(group_name)

        with allure_step_log("步骤4: 验证IP地址组已删除"):
            vpc_page.assert_deleted(group_name)

    @allure.title("验证搜索与重置IP地址组功能")
    def test_ip_group_search_reset(self, vpc_page, ip_group):
        group_name = ip_group["name"]
        keyword = group_name[:-2]

        with allure_step_log(f"步骤1: 搜索IP地址组: {keyword}"):
            vpc_page.ip_group_search(keyword)
            vpc_page.assert_list_contain(keyword, exact_match=False)

        with allure_step_log("步骤2: 重置搜索条件"):
            vpc_page.ip_group_search_reset()
            assert vpc_page._input_search.input_value() == "", \
                f"重置后搜索框未清空，实际值: {vpc_page._input_search.input_value()}"

        with allure_step_log("步骤3: 验证重置后列表恢复正常"):
            vpc_page.assert_list_contain(group_name)

    @allure.title("验证编辑IP地址组功能")
    def test_ip_group_edit(self, vpc_page, ip_group):
        old_name = ip_group["name"]
        new_name = f"{old_name}-edit"
        new_ip_addresses = ["10.10.10.20", "10.10.10.21"]
        new_desc = f"{new_name}修改后的描述"

        with allure_step_log(f"步骤1: 修改IP地址组: {old_name} -> {new_name}"):
            vpc_page.ip_group_edit(
                name=old_name,
                new_name=new_name,
                new_ip_addresses=new_ip_addresses,
                new_desc=new_desc,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证修改结果"):
            row_data = vpc_page.get_row_data(new_name)
            assert row_data.get("名称") == new_name, \
                f"名称修改失败，期望: {new_name}，实际: {row_data.get('名称')}"
            assert "10.10.10.20" in row_data.get("包含IP地址", ""), \
                f"IP地址修改失败，期望包含: 10.10.10.20，实际: {row_data.get('包含IP地址')}"
            assert new_desc in row_data.get("描述", ""), \
                f"描述修改失败，期望包含: {new_desc}，实际: {row_data.get('描述')}"

        ip_group["name"] = new_name
        ip_group["ip_addresses"] = new_ip_addresses
        ip_group["desc"] = new_desc

    @allure.title("验证IP地址组详情页修改IP功能")
    def test_ip_group_detail_edit(self, vpc_page, ip_group):
        group_name = ip_group["name"]
        old_ip_addresses = list(ip_group["ip_addresses"])
        new_ip_addresses = ["10.10.10.30", "10.10.10.31"]

        with allure_step_log(f"步骤1: 在详情页修改IP地址组 {group_name} 的IP地址"):
            vpc_page.ip_group_edit_in_detail(
                name=group_name,
                old_ip_addresses=old_ip_addresses,
                new_ip_addresses=new_ip_addresses,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证详情页修改结果"):
            vpc_page.assert_ip_group_detail_basic_info(name=group_name, desc=ip_group["desc"])
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in new_ip_addresses:
                assert ip in detail_ips, f"详情页IP修改失败，期望包含: {ip}，实际: {detail_ips}"
            for ip in old_ip_addresses:
                assert ip not in detail_ips, f"详情页旧IP未被替换，期望不包含: {ip}，实际: {detail_ips}"
            ip_group["ip_addresses"] = new_ip_addresses
        with allure_step_log("步骤3: 验证列表页修改结果"):
            vpc_page.goto_submenu("IP地址组")
            row_data = vpc_page.get_row_data(group_name)
            assert row_data.get("名称") == group_name, \
                f"详情页修改后名称异常，期望: {group_name}，实际: {row_data.get('名称')}"
            assert new_ip_addresses[0] in row_data.get("包含IP地址", ""), \
                f"详情页修改后列表页IP未更新，期望包含: {new_ip_addresses[0]}，实际: {row_data.get('包含IP地址')}"
            assert ip_group["desc"] in row_data.get("描述", ""), \
                f"详情页修改后描述异常，期望包含: {ip_group['desc']}，实际: {row_data.get('描述')}"


    @allure.title("验证IP地址组详情页新增与单个删除IP功能")
    def test_ip_group_detail_add_delete_ip(self, vpc_page, ip_group):
        group_name = ip_group["name"]
        extra_ips = ["10.10.10.11", "10.10.10.12"]

        with allure_step_log(f"步骤1: 进入IP地址组 {group_name} 详情页并校验基本信息"):
            vpc_page.goto_ip_group_detail(group_name)
            vpc_page.assert_ip_group_detail_basic_info(name=group_name, desc=ip_group["desc"])
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in ip_group["ip_addresses"]:
                assert ip in detail_ips, f"详情页初始IP缺失，期望包含: {ip}，实际: {detail_ips}"

        with allure_step_log(f"步骤2: 在详情页为 {group_name} 添加IP地址"):
            vpc_page.ip_group_add_ip_addresses(group_name, extra_ips)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 验证新增IP地址结果"):
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in extra_ips:
                assert ip in detail_ips, f"新增IP未生效，期望包含: {ip}，实际: {detail_ips}"

        with allure_step_log("步骤4: 在详情页删除新增的IP地址"):
            vpc_page.ip_group_delete_ip_addresses(group_name, extra_ips)

        with allure_step_log("步骤5: 验证IP地址已删除"):
            vpc_page.wait_for_page_ready()
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in extra_ips:
                assert ip not in detail_ips, f"IP删除失败，期望不包含: {ip}，实际: {detail_ips}"

    @allure.title("验证IP地址组详情页批量删除IP功能")
    def test_ip_group_detail_batch_delete_ip(self, vpc_page, ip_group):
        group_name = ip_group["name"]
        extra_ips = ["10.10.10.41", "10.10.10.42"]

        with allure_step_log(f"步骤1: 在详情页为 {group_name} 添加2个IP地址"):
            vpc_page.ip_group_add_ip_addresses(group_name, extra_ips)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证新增IP地址结果"):
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in extra_ips:
                assert ip in detail_ips, f"批量删除前IP缺失，期望包含: {ip}，实际: {detail_ips}"

        with allure_step_log("步骤3: 在详情页批量删除新增的IP地址"):
            vpc_page.ip_group_batch_delete_ip_addresses(group_name, extra_ips)

        with allure_step_log("步骤4: 验证IP地址已批量删除"):
            detail_ips = vpc_page.get_detail_ip_addresses()
            for ip in extra_ips:
                assert ip not in detail_ips, f"IP批量删除失败，期望不包含: {ip}，实际: {detail_ips}"

    @allure.title("验证列表页批量删除IP地址组功能")
    def test_ip_group_batch_delete(self, vpc_page):
        base_name = random_data()
        group_names = [f"ipg-{base_name}-{index}" for index in range(2)]

        with allure_step_log("步骤1: 创建2条IP地址组数据"):
            for index, name in enumerate(group_names, start=1):
                vpc_page.ip_group_create(
                    name=name,
                    ip_addresses=[f"10.10.20.{index}"],
                    desc=f"{name}批量删除测试",
                )
                vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 批量删除IP地址组"):
            vpc_page.ip_group_delete(group_names)

        with allure_step_log("步骤3: 验证IP地址组已批量删除"):
            vpc_page.assert_deleted(group_names)
