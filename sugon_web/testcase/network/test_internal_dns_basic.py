import allure

from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


@allure.epic("网络服务")
@allure.feature("内网解析")
@allure.story("基本功能验证")
class TestInternalDnsBasic:

    @allure.title("内网解析-创建和删除")
    def test_internal_dns_create_delete(self, vpc_page, vpc):
        """验证内网解析支持创建并删除。"""
        domain = f"dns-{random_data()}.com"
        email = "admin@test.com"
        desc = "内网解析创建删除自动化测试"

        with allure_step_log("步骤1: 创建内网解析"):
            vpc_page.internal_dns_create(
                domain=domain,
                vpc_name=vpc["name"],
                email=email,
                desc=desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证内网解析列表数据"):
            vpc_page.goto_internal_dns_list()
            vpc_page.assert_list_contain(domain, column_name="域名", exact_match=True)
            row_data = vpc_page.get_row_data(domain)
            assert row_data.get("域名") == domain, f"域名断言失败: {row_data}"
            assert row_data.get("记录集个数") == "2", f"记录集个数断言失败: {row_data}"
            assert vpc["name"] in row_data.get("已关联VPC", ""), f"已关联VPC断言失败: {row_data}"
            assert desc == row_data.get("描述"), f"描述断言失败: {row_data}"
            assert "正常" in row_data.get("状态", ""), f"状态断言失败: {row_data}"

        with allure_step_log("步骤3: 删除内网解析"):
            vpc_page.internal_dns_delete(domain)

        with allure_step_log("步骤4: 验证内网解析已删除"):
            vpc_page.assert_deleted(domain)

    @allure.title("内网解析-修改邮箱和描述")
    def test_internal_dns_edit_email_desc(self, vpc_page, internal_dns):
        """验证内网解析支持修改邮箱和描述。"""
        new_email = "newadmin@test.com"
        new_desc = "修改后的内网解析描述"

        with allure_step_log("步骤1: 修改内网解析邮箱和描述"):
            vpc_page.internal_dns_edit(
                domain=internal_dns["domain"],
                new_email=new_email,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证修改后的列表数据"):
            vpc_page.goto_internal_dns_list()
            row_data = vpc_page.get_row_data(internal_dns["domain"])
            assert new_desc == row_data.get("描述"), f"描述断言失败: {row_data}"
            vpc_page.goto_internal_dns_detail(internal_dns["domain"])
            expect(vpc_page.page.locator("body")).to_contain_text(new_email)
            internal_dns["email"] = new_email
            internal_dns["desc"] = new_desc

    @allure.title("内网解析-搜索和重置")
    def test_internal_dns_search_reset(self, vpc_page, internal_dns):
        """验证内网解析支持搜索和重置。"""
        with allure_step_log("步骤1: 按域名关键字搜索"):
            keyword = internal_dns["domain"][:-4]
            vpc_page.internal_dns_search(keyword)
            vpc_page.assert_list_contain(internal_dns["domain"], column_name="域名", exact_match=True)

        with allure_step_log("步骤2: 按描述关键字搜索"):
            vpc_page.internal_dns_reset()
            keyword = internal_dns["desc"][:6]
            vpc_page.search(keyword)
            vpc_page.assert_list_contain(internal_dns["domain"], column_name="域名", exact_match=True)

        with allure_step_log("步骤3: 重置搜索条件"):
            vpc_page.internal_dns_reset()
            assert vpc_page._input_search.input_value() == "", "重置后搜索输入框未清空"
            vpc_page.assert_list_contain(internal_dns["domain"], column_name="域名", exact_match=True)

    @allure.title("内网解析-批量删除")
    def test_internal_dns_batch_delete(self, vpc_page, vpc):
        """验证内网解析支持批量删除。"""
        base_name = random_data()
        domains = [f"dns-{base_name}-{index}.com" for index in range(2)]
        desc = "内网解析批量删除自动化测试"

        with allure_step_log("步骤1: 创建2条内网解析"):
            for domain in domains:
                vpc_page.internal_dns_create(
                    domain=domain,
                    vpc_name=vpc["name"],
                    email="admin@test.com",
                    desc=desc
                )
                vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证2条内网解析创建成功"):
            vpc_page.goto_internal_dns_list()
            for domain in domains:
                vpc_page.assert_list_contain(domain, column_name="域名", exact_match=True)

        with allure_step_log("步骤3: 批量删除内网解析"):
            vpc_page.internal_dns_delete(domains)

        with allure_step_log("步骤4: 验证内网解析已批量删除"):
            vpc_page.assert_deleted(domains)

    @allure.title("内网解析详情页-解析记录-创建和删除")
    def test_internal_dns_record_create_delete(self, vpc_page, internal_dns):
        """验证内网解析详情页支持创建并删除解析记录。"""
        host_record = f"www-{random_data(length=4)}"
        record_alias = vpc_page.internal_dns_record_alias(internal_dns["domain"], host_record)
        record_value = "10.10.10.10"
        record_desc = "解析记录创建删除自动化测试"

        with allure_step_log("步骤1: 创建 A 类型解析记录"):
            vpc_page.internal_dns_record_create(
                domain=internal_dns["domain"],
                host_record=host_record,
                record_type="A",
                ttl=600,
                values=record_value,
                desc=record_desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证解析记录创建成功"):
            vpc_page.assert_list_contain(record_alias, column_name="域名", exact_match=True)
            row_data = vpc_page.get_row_data(record_alias)
            assert row_data.get("域名") == record_alias, f"域名断言失败: {row_data}"
            assert row_data.get("类型") == "A", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == "600", f"TTL断言失败: {row_data}"
            assert record_value in row_data.get("值", ""), f"记录值断言失败: {row_data}"
            assert record_desc == row_data.get("描述"), f"描述断言失败: {row_data}"

        with allure_step_log("步骤3: 删除解析记录"):
            vpc_page.internal_dns_record_delete(internal_dns["domain"], record_alias)

        with allure_step_log("步骤4: 验证解析记录已删除"):
            vpc_page.assert_deleted(record_alias)

    @allure.title("内网解析详情页-解析记录-修改主机记录和TTL等信息")
    def test_internal_dns_record_edit(self, vpc_page, internal_dns_record):
        """验证内网解析详情页支持修改解析记录。"""
        new_host_record = f"api-{random_data(length=4)}"
        new_alias = vpc_page.internal_dns_record_alias(internal_dns_record["domain"], new_host_record)
        new_ttl = 1200
        new_value = "10.10.20.20"
        new_desc = "修改后的解析记录描述"

        with allure_step_log("步骤1: 修改解析记录主机记录、TTL、值和描述"):
            vpc_page.internal_dns_record_edit(
                domain=internal_dns_record["domain"],
                record_alias=internal_dns_record["alias"],
                new_host_record=new_host_record,
                new_ttl=new_ttl,
                new_values=new_value,
                new_desc=new_desc
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证修改后的解析记录数据"):
            vpc_page.goto_internal_dns_detail(internal_dns_record["domain"], tab_name="解析记录")
            row_data = vpc_page.get_row_data(new_alias)
            assert row_data.get("域名") == new_alias, f"域名断言失败: {row_data}"
            assert row_data.get("类型") == "A", f"类型断言失败: {row_data}"
            assert row_data.get("TTL") == str(new_ttl), f"TTL断言失败: {row_data}"
            assert new_value in row_data.get("值", ""), f"记录值断言失败: {row_data}"
            assert new_desc == row_data.get("描述"), f"描述断言失败: {row_data}"
            internal_dns_record["host_record"] = new_host_record
            internal_dns_record["alias"] = new_alias
            internal_dns_record["ttl"] = new_ttl
            internal_dns_record["value"] = new_value
            internal_dns_record["desc"] = new_desc

    @allure.title("内网解析详情页-解析记录-搜索和重置")
    def test_internal_dns_record_search_reset(self, vpc_page, internal_dns_record):
        """验证内网解析详情页支持搜索和重置解析记录。"""
        with allure_step_log("步骤1: 按记录值搜索解析记录"):
            vpc_page.internal_dns_record_search(internal_dns_record["domain"], internal_dns_record["value"])
            vpc_page.assert_list_contain(internal_dns_record["alias"], column_name="域名", exact_match=True)

        with allure_step_log("步骤2: 按描述关键字搜索解析记录"):
            vpc_page.internal_dns_record_reset(internal_dns_record["domain"])
            vpc_page.internal_dns_record_search(internal_dns_record["domain"], internal_dns_record["desc"][:6])
            vpc_page.assert_list_contain(internal_dns_record["alias"], column_name="域名", exact_match=True)

        with allure_step_log("步骤3: 重置解析记录搜索条件"):
            vpc_page.internal_dns_record_reset(internal_dns_record["domain"])
            active_tab = vpc_page.locator(".el-tab-pane:not([aria-hidden='true'])").first
            search_input = active_tab.get_by_placeholder("搜索（类型、TTL、值、描述）")
            assert search_input.input_value() == "", "重置后解析记录搜索输入框未清空"
            vpc_page.assert_list_contain(internal_dns_record["alias"], column_name="域名", exact_match=True)

    @allure.title("内网解析详情页-解析记录-批量删除")
    def test_internal_dns_record_batch_delete(self, vpc_page, internal_dns):
        """验证内网解析详情页支持批量删除解析记录。"""
        host_records = [f"batch-{random_data(length=4)}-{index}" for index in range(2)]
        record_aliases = [
            vpc_page.internal_dns_record_alias(internal_dns["domain"], host_record) for host_record in host_records
        ]

        with allure_step_log("步骤1: 创建2条解析记录"):
            for index, host_record in enumerate(host_records):
                vpc_page.internal_dns_record_create(
                    domain=internal_dns["domain"],
                    host_record=host_record,
                    record_type="A",
                    ttl=600 + index,
                    values=f"10.10.30.{10 + index}",
                    desc="解析记录批量删除自动化测试"
                )
                vpc_page.assert_popup_success()

        with allure_step_log("步骤2: 验证2条解析记录创建成功"):
            vpc_page.goto_internal_dns_detail(internal_dns["domain"], tab_name="解析记录")
            for record_alias in record_aliases:
                vpc_page.assert_list_contain(record_alias, column_name="域名", exact_match=True)

        with allure_step_log("步骤3: 批量删除解析记录"):
            vpc_page.internal_dns_record_delete(internal_dns["domain"], record_aliases)

        with allure_step_log("步骤4: 验证解析记录已批量删除"):
            vpc_page.assert_deleted(record_aliases)
