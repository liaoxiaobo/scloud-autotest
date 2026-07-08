import json
import os
import shlex
import urllib.parse

import allure
import pytest

from sugon_web.config.config import Config
from sugon_web.pages.storage.oss_version_control import OssVersionControlPage
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import allure_step_log, logger


def _assert_backend_versions_via_api(page, ssh_host, bucket_name, object_key):
    """通过 SSH 在后台节点 curl OSS 内部 API，验证对象多版本真实存在。

    原需求基于 SeaweedFS 的 weed shell，但当前部署环境（XStor/object-routing）
    并不存在 weed 二进制，因此改为调用 sugoncloud-oss-api 的 ListVersions 接口
    做后端验证：必须在后端返回中查到对象，且版本数不少于 2。
    """
    api_header_json = page.evaluate('() => localStorage.getItem("api_header")')
    assert api_header_json, \
        "[BackendAssertion] 无法从 localStorage 获取登录凭证(api_header)"
    api_header = json.loads(api_header_json)
    token = api_header.get("Authorization")
    assert token, \
        "[BackendAssertion] api_header 中缺少 Authorization"

    region_id = page.evaluate('() => localStorage.getItem("regionId")') or "RegionOne"
    host = Config.get("host")
    encoded_key = urllib.parse.quote(object_key, safe="")
    url = (
        f"https://{host}:30000/api/sugoncloud-oss-api/api/ossObject/ListVersions?"
        f"bucketName={bucket_name}&delimiter=/&keyMarker=&maxKeys=1000&prefix={encoded_key}"
    )

    auth_header = f"Authorization: {token}"
    region_header = f"regionId: {region_id}"
    cmd = (
        f"curl -sk -H {shlex.quote(auth_header)} "
        f"-H {shlex.quote(region_header)} {shlex.quote(url)}"
    )

    result = ssh_host.run(cmd, return_rc=True, return_stdout=True, return_stderr=True, timeout=60)
    assert result["rc"] == 0, \
        f"[BackendAssertion] curl 命令执行失败 | rc={result['rc']} | stderr={result.get('stderr', '')}"

    try:
        resp = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"[BackendAssertion] 后端返回不是合法 JSON | stdout={result['stdout']}"
        ) from exc

    assert resp.get("success") is True, \
        f"[BackendAssertion] OSS API 返回失败 | response={resp}"

    versions = resp.get("content", {}).get("versions") or []
    assert len(versions) >= 2, \
        f"[BackendAssertion] 后端版本数不足 2 | versions={versions}"
    assert any(object_key in v.get("objectKey", "") for v in versions), \
        f"[BackendAssertion] 后端版本列表未找到对象 {object_key} | versions={versions}"


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-多版本控制')
class TestOSSVersionControl:
    """验证OSS对象存储桶多版本控制功能。

    桶资源由 class-scoped fixture 共享创建，所有场景执行完成后统一清理。
    """

    @pytest.fixture(scope="class")
    def version_bucket(self, browser_context, config, request):
        """创建测试桶并在 class 内共享，测试结束后先清空对象再删除桶。"""
        from sugon_web.conftest import _create_logged_in_page
        from sugon_web.testcase.storage._oss_helpers import (
            create_oss_bucket,
            delete_oss_bucket,
        )

        page = _create_logged_in_page(browser_context, config)
        oss_page = OssVersionControlPage(page)

        bucket_name = f"oss-{random_data()}"
        try:
            with allure_step_log(f"创建测试桶: {bucket_name}"):
                bucket = create_oss_bucket(oss_page, name=bucket_name)
            yield bucket
        finally:
            try:
                with allure_step_log(f"清理: 删除桶内对象并删除桶 {bucket_name}"):
                    # 先清空桶内对象（包括所有版本）
                    oss_page.goto_service("对象存储")
                    oss_page.wait_for_page_ready()
                    objects = oss_page.oss_bucket_get_objects(bucket_name)
                    test_file_name = "test_upload.txt"
                    if test_file_name in objects:
                        oss_page.oss_bucket_delete_object(bucket_name, test_file_name)
                        oss_page.oss_bucket_permanent_delete_object(
                            bucket_name, test_file_name, single=True
                        )
                        remaining = oss_page.oss_bucket_get_objects(bucket_name)
                        if test_file_name in remaining:
                            raise AssertionError(
                                f"清理后对象 {test_file_name} 仍存在于对象列表 | 实际: {remaining}"
                            )
                    # 再删除桶
                    delete_oss_bucket(oss_page, bucket_name)
            except Exception as e:
                logger.error(f"清理桶 {bucket_name} 失败: {e}")
                raise
            finally:
                page.close()

    @pytest.fixture()
    def version_oss_page(self, page):
        """初始化多版本控制场景页面对象并导航到对象存储服务。"""
        oss_page = OssVersionControlPage(page)
        oss_page.goto_service("对象存储")
        return oss_page

    @allure.title("对象存储OSS-桶操作-多版本控制验证")
    def test_oss_version_control(self, version_oss_page, ssh_host, version_bucket):
        """验证开启多版本控制后，同名文件多次上传会生成多个版本，并通过SSH后端验证。"""
        oss_page = version_oss_page
        bucket_name = version_bucket["name"]
        test_file_name = "test_upload.txt"
        test_data_dir = os.path.join(
            os.path.dirname(__file__), "..", "test_data"
        )
        test_file_path = os.path.join(test_data_dir, test_file_name)
        assert os.path.exists(test_file_path), \
            f"[BackendAssertion] 测试文件不存在: {test_file_path}"

        with allure_step_log("步骤1: 进入桶详情页"):
            oss_page.goto_service("对象存储")
            oss_page.wait_for_page_ready()
            oss_page.oss_bucket_enter_detail(bucket_name)
            oss_page.wait_for_page_ready()

        with allure_step_log("步骤2: 开启多版本控制"):
            oss_page.oss_bucket_enable_versioning(bucket_name)

        with allure_step_log("步骤3: 上传同名文件两次"):
            oss_page.oss_bucket_object_tab_click()
            for i in range(2):
                # headless 下 mounted 钩子会把 URL 重定向到 dashboard，
                # 但页面实际已渲染对象列表，故跳过 upload_object 内部导航。
                oss_page.oss_bucket_upload_object(
                    bucket_name, test_file_path, skip_navigation=True
                )
                oss_page.wait_for_page_ready()

            objects = oss_page.oss_bucket_get_objects(bucket_name)
            assert test_file_name in objects, \
                f"[ListAssertion] 对象列表未包含 {test_file_name} | 实际列表: {objects}"

        with allure_step_log("步骤4: 进入对象详情页并查看版本"):
            oss_page.oss_bucket_enter_object_detail(bucket_name, test_file_name)
            oss_page.oss_bucket_object_detail_click_version_tab()
            version_count = oss_page.oss_bucket_object_detail_get_version_count()
            assert version_count == 2, \
                f"[VersionAssertion] 版本数量期望 2，实际: {version_count}"

        with allure_step_log("步骤5: SSH后端验证"):
            _assert_backend_versions_via_api(
                oss_page.page, ssh_host, bucket_name, test_file_name
            )
