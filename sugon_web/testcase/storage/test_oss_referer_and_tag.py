import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-防盗链与标签管理')
class TestOSSRefererAndTag:
    """验证OSS对象存储防盗链与标签管理功能。

    包含两个独立场景：
    1. 防盗链：创建公共读桶、上传对象、设置白名单/黑名单Referer、通过curl验证。
    2. 创建标签：创建桶、批量创建10个标签（含超长值和特殊字符）、验证标签数量上限。
    两个场景各自独立，不共享数据。
    """

    # ── 场景1：防盗链（用例405409） ──

    @allure.title("对象存储OSS-桶操作-访问权限控制-防盗链")
    @pytest.mark.parametrize(
        "oss_bucket",
        [{
            "region": "RegionOne",
            "az_strategy": "MULTI_AZ",
            "storage_class": "标准存储",
            "bucket_strategy": "公共读写",
            "is_encryption": True,
            "data_read": False,
        }],
        indirect=True,
    )
    def test_oss_bucket_anti_hotlinking(self, oss_page, ssh_host, oss_bucket):
        """验证防盗链白名单和黑名单功能，通过curl验证HTTP状态码。"""
        bucket_name = oss_bucket["name"]
        object_name = f"test01-{random_data()}"

        with allure_step_log("步骤1: 进入桶详情页并上传对象"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            # 通过桶列表页点击进入详情页
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_object_tab_click()

            # 上传测试对象（使用内置的测试文件）
            import os
            import tempfile
            test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
            test_file_path = os.path.join(test_data_dir, "test_upload.txt")
            if os.path.exists(test_file_path):
                oss_page.oss_bucket_upload_object(bucket_name, test_file_path)
            else:
                # 如果没有测试文件，创建一个临时文件
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write("test content for anti-hotlinking")
                    temp_file_path = f.name
                oss_page.oss_bucket_upload_object(bucket_name, temp_file_path)
                os.unlink(temp_file_path)

        with allure_step_log("步骤2: 记录对象URL链接"):
            object_url = oss_page.oss_bucket_get_object_url(bucket_name, "test_upload.txt")
            logger.info(f"[AntiHotlinking] 对象URL: {object_url}")
            assert object_url.startswith("http"), \
                f"[FieldAssertion] 对象URL格式错误 | 期望以http开头，实际: {object_url}"

        with allure_step_log("步骤3: 进入防盗链配置页面"):
            oss_page.oss_bucket_goto_safety_chain_page(bucket_name)
            # P0: 验证页面已加载
            assert "/basicconfig/securitychain" in oss_page.page.url, \
                f"[StatusAssertion] 未进入防盗链页面 | 当前URL: {oss_page.page.url}"

        with allure_step_log("步骤4: 设置白名单Referer并验证"):
            whitelist_referer = "http://www.baidu.com"
            oss_page.oss_bucket_set_referer(bucket_name, "whitelist", whitelist_referer)

            # P0: 验证白名单Referer已设置
            displayed_referer = oss_page.oss_bucket_get_referer(bucket_name, "whitelist")
            assert whitelist_referer in displayed_referer, \
                f"[FieldAssertion] 白名单Referer显示不正确 | 期望包含: {whitelist_referer} | 实际: {displayed_referer}"

            # P2: 使用curl验证白名单Referer返回HTTP 200（OSS使用自签名证书，加 -k 跳过SSL校验）
            curl_cmd = f'curl -k -I -H "Referer:{whitelist_referer}" "{object_url}"'
            result = ssh_host.run(curl_cmd, return_rc=True)
            assert result["rc"] == 0, \
                f"[BackendAssertion] curl命令执行失败 | stderr: {result.get('stderr', '')}"
            assert "HTTP/1.1 200" in result["stdout"] or "HTTP/2 200" in result["stdout"], \
                f"[BackendAssertion] 白名单Referer验证失败 | 期望HTTP 200 | 实际: {result['stdout']}"

        with allure_step_log("步骤5: 设置黑名单Referer并验证"):
            blacklist_referer = "http://www.google.com"
            oss_page.oss_bucket_set_referer(bucket_name, "blacklist", blacklist_referer)

            # P0: 验证黑名单Referer已设置
            displayed_referer = oss_page.oss_bucket_get_referer(bucket_name, "blacklist")
            assert blacklist_referer in displayed_referer, \
                f"[FieldAssertion] 黑名单Referer显示不正确 | 期望包含: {blacklist_referer} | 实际: {displayed_referer}"

            # P2: 使用curl验证黑名单Referer返回HTTP 403（OSS使用自签名证书，加 -k 跳过SSL校验）
            curl_cmd = f'curl -k -I -H "Referer:{blacklist_referer}" "{object_url}"'
            result = ssh_host.run(curl_cmd, return_rc=True)
            assert result["rc"] == 0, \
                f"[BackendAssertion] curl命令执行失败 | stderr: {result.get('stderr', '')}"
            assert "HTTP/1.1 403" in result["stdout"] or "HTTP/2 403" in result["stdout"], \
                f"[BackendAssertion] 黑名单Referer验证失败 | 期望HTTP 403 | 实际: {result['stdout']}"

        # 对象清理由桶 fixture teardown 统一处理（删除桶时自动删除对象）

    # ── 场景2：创建标签（用例405354） ──

    @allure.title("对象存储OSS-桶操作-基础配置-创建标签")
    @pytest.mark.parametrize(
        "oss_bucket",
        [{
            "region": "RegionOne",
            "az_strategy": "MULTI_AZ",
            "storage_class": "标准存储",
            "bucket_strategy": "私有",
            "is_encryption": True,
            "data_read": False,
        }],
        indirect=True,
    )
    def test_oss_bucket_create_tags(self, oss_page, oss_bucket):
        """验证桶标签创建功能，包括批量创建10个标签和验证数量上限。"""
        bucket_name = oss_bucket["name"]

        # 定义10组标签数据（按需求MD定义）
        tags_data = [
            {"key": "Key1", "value": "value1"},
            {"key": "key2", "value": "value2"},
            {
                "key": "key3",
                "value": "wkey22222222222221222322wwwewwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww",
            },
            {
                "key": "wkey22222222222221222322wwwewwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww",
                "value": "wkey22222222222221222322wwwewwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww",
            },
            {"key": "key5", "value": "abcdeft22123AdW2!@#?WW2222"},
            {"key": "key6", "value": "1232221Wawweww2-ww2;_112122"},
            {"key": "key7", "value": "test2"},
            {"key": "key8", "value": "kye7yuyuiuettyw9wijhuyu@1##!@%^*(*(#@wwwwssww"},
            {"key": "key9", "value": "kyeyyuiiuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu"},
            {"key": "key10", "value": "test109"},
        ]

        with allure_step_log("步骤1: 进入桶详情页"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enter_detail_via_ui(bucket_name)
            oss_page.wait_for_page_ready()

        with allure_step_log("步骤2: 进入标签页面"):
            tag_page_opened = oss_page.oss_bucket_detail_click_tag_tab(bucket_name)
            assert tag_page_opened, \
                f"[StatusAssertion] 标签页面被权限隐藏，无法访问 | bucket={bucket_name}"
            assert "/basicconfig/tag" in oss_page.page.url, \
                f"[StatusAssertion] 未进入标签页面 | 当前URL: {oss_page.page.url}"

        with allure_step_log("步骤3: 批量创建10个标签"):
            for i, tag in enumerate(tags_data):
                logger.info(f"[TagCreate] 创建第 {i+1} 个标签: key={tag['key']}, value={tag['value'][:20]}...")
                # 第一个标签需要导航到标签页，后续标签复用当前页面
                skip_nav = (i > 0)
                oss_page.oss_bucket_tag_create(bucket_name, tag["key"], tag["value"], skip_navigation=skip_nav)

        with allure_step_log("步骤4: 验证创建的标签"):
            # P0: 验证标签总数为10
            tag_count = oss_page.oss_bucket_tag_get_count(bucket_name)
            assert tag_count == 10, \
                f"[ListAssertion] 标签数量不正确 | 期望: 10 | 实际: {tag_count}"

            # P1: 验证每个标签的key和value与输入一致
            # 注：前端表格对超长值会做显示截断，因此对长值采用"前缀匹配"而非精确全等
            tags_from_ui = oss_page.oss_bucket_detail_get_tags()
            for expected_tag in tags_data:
                found = False
                for actual_tag in tags_from_ui:
                    if actual_tag["key"] == expected_tag["key"]:
                        expected_value = expected_tag["value"]
                        actual_value = actual_tag["value"]
                        if len(expected_value) > 50:
                            # 长值仅验证前端显示前缀一致，避免显示截断导致误判
                            prefix = expected_value[:50]
                            assert actual_value.startswith(prefix), \
                                f"[FieldAssertion] 长标签值显示前缀不匹配 | key={expected_tag['key']} | 期望前缀: {prefix} | 实际: {actual_value}"
                        else:
                            assert actual_value == expected_value, \
                                f"[FieldAssertion] 标签值不匹配 | key={expected_tag['key']} | 期望: {expected_value} | 实际: {actual_value}"
                        found = True
                        break
                assert found, \
                    f"[ListAssertion] 标签未找到 | key={expected_tag['key']} | 实际标签列表: {tags_from_ui}"

        with allure_step_log("步骤5: 验证标签数量上限"):
            # P0: 验证"新建"按钮被禁用
            is_disabled = oss_page.oss_bucket_tag_is_create_disabled(bucket_name)
            assert is_disabled, \
                f"[StatusAssertion] 标签数量已达上限但'新建'按钮未被禁用 | bucket={bucket_name}"

            # 验证第11个标签创建被阻止（按钮已禁用，直接调用方法会抛出异常）
            # 这里使用 pytest.raises 模式来验证异常被抛出
            from pytest import raises
            with raises(AssertionError) as exc_info:
                oss_page.oss_bucket_tag_create(bucket_name, "key11", "test11", skip_navigation=True)
            assert "禁用" in str(exc_info.value) or "新建" in str(exc_info.value), \
                f"[StatusAssertion] 第11个标签创建未被正确阻止 | 异常信息: {exc_info.value}"

        # 标签清理由桶 fixture teardown 统一处理（删除桶时自动清理标签）
