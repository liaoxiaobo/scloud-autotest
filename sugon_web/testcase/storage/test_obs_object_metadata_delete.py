import datetime
import hashlib
import hmac
import os

import allure
import pytest
import requests
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


# ---------------------------------------------------------------------------
# 模块级辅助函数（AWS Signature V4 签名）
# ---------------------------------------------------------------------------

def _aws_sign_request(method, uri, access_key, secret_key, region, service, host):
    """AWS Signature Version 4 signing for S3 requests."""
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    payload_hash = hashlib.sha256(b'').hexdigest()
    headers = {'host': host, 'x-amz-date': amzdate}
    canonical_headers = ''.join(f'{k}:{v}\n' for k, v in sorted(headers.items()))
    signed_headers = ';'.join(sorted(headers.keys()))

    canonical_request = '\n'.join([
        method, uri, '', canonical_headers, signed_headers, payload_hash,
    ])

    credential_scope = f'{datestamp}/{region}/{service}/aws4_request'
    string_to_sign = '\n'.join([
        'AWS4-HMAC-SHA256', amzdate, credential_scope,
        hashlib.sha256(canonical_request.encode('utf-8')).hexdigest(),
    ])

    def _sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = _sign(('AWS4' + secret_key).encode('utf-8'), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, 'aws4_request')
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    headers['Authorization'] = (
        f'AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, '
        f'SignedHeaders={signed_headers}, Signature={signature}'
    )
    return headers


@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('元数据-删除元数据并验证服务端生效')
class TestOBSObjectMetadataDelete:

    @pytest.mark.parametrize("bucket", [{}], indirect=True)
    @allure.title("对象存储-删除元数据并验证服务端生效")
    def test_obs_object_metadata_delete_validation(self, obs_page, bucket, page):
        """验证对象元数据可删除，且删除后通过HTTP HEAD请求验证服务端生效。"""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test1"
        )
        bucket_name = bucket["name"]
        object_name = "test1"
        metadata_key = "content-111"
        metadata_value = "test-222"
        credential_ak = None
        credential_sk = None

        # ------------------ 前置：选择项目 ------------------
        with allure_step_log("前置: 选择公共测试项目"):
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")

        # ------------------ 步骤1：创建个人凭证 ------------------
        with allure_step_log("步骤1: 创建个人凭证并记录ak/sk"):
            obs_page.goto_submenu("个人凭证")
            obs_page.page.wait_for_timeout(2000)
            obs_page.obs_credential_click_create()
            dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
                has_text="新建访问密钥"
            ).first
            expect(dialog).to_be_visible(timeout=10000)
            obs_page.obs_credential_create_dialog_fill("测试凭证-" + random_data())
            credential_ak, credential_sk = obs_page.obs_credential_create_dialog_confirm()
            assert credential_ak, "未能提取 Access Key"
            assert credential_sk, "未能提取 Secret Key"
            logger.info(f"创建凭证成功，AK: {credential_ak}")
            obs_page.obs_credential_close_success_dialog()

        # ------------------ 步骤2：进入桶详情页并获取EndPoint地址 ------------------
        with allure_step_log("步骤2: 进入桶详情页并获取EndPoint地址"):
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.page.wait_for_timeout(3000)
            endpoint_text = obs_page.obs_bucket_endpoint_get()
            assert endpoint_text, "未能获取EndPoint地址"
            domain, port, protocol = obs_page.obs_bucket_endpoint_url_extract(
                endpoint_text
            )
            endpoint_url = f"{protocol}://{domain}:{port}"
            logger.info(f"EndPoint URL: {endpoint_url}")

        # ------------------ 步骤3：上传对象并配置元数据 ------------------
        with allure_step_log("步骤3: 上传对象并配置元数据"):
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload_with_metadata(
                test_file_path,
                [{"key": metadata_key, "value": metadata_value}],
            )

        # ------------------ 步骤4：验证对象上传成功并查看元数据 ------------------
        with allure_step_log("步骤4: 验证元数据初始值"):
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(2000)
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()
            obs_page.assert_object_list_contain(object_name)

            obs_page.obs_object_enter_detail(object_name)
            obs_page.obs_object_detail_click_metadata_tab()
            actual_value = obs_page.obs_object_metadata_get_value(metadata_key)
            assert actual_value == metadata_value, (
                f"元数据初始值不匹配 | 期望: {metadata_value} | 实际: {actual_value}"
            )

        # ------------------ 步骤5：HEAD请求验证元数据已写入服务端 ------------------
        with allure_step_log("步骤5: HEAD请求验证元数据已写入服务端"):
            host = endpoint_url.replace("http://", "").replace("https://", "")
            uri = f"/{bucket_name}/{object_name}"
            headers = _aws_sign_request(
                "HEAD", uri, credential_ak, credential_sk,
                "cn-north-1", "s3", host,
            )
            response = requests.head(
                f"{endpoint_url}{uri}", headers=headers, timeout=30, verify=False
            )
            assert response.status_code == 200, (
                f"HEAD请求失败 | 状态码: {response.status_code}"
            )
            meta_header = f"x-amz-meta-{metadata_key}"
            assert meta_header in response.headers, (
                f"响应头中缺少元数据字段 {meta_header} | 响应头: {dict(response.headers)}"
            )
            header_value = response.headers[meta_header]
            assert header_value == metadata_value, (
                f"元数据服务端值不匹配 | 期望: {metadata_value} | 实际: {header_value}"
            )

        # ------------------ 步骤6：删除元数据 ------------------
        with allure_step_log("步骤6: 删除元数据"):
            obs_page.obs_object_metadata_delete(metadata_key)

        # ------------------ 步骤7：验证元数据已删除（UI层面） ------------------
        with allure_step_log("步骤7: 验证元数据已从UI列表中删除"):
            deleted_value = obs_page.obs_object_metadata_get_value(metadata_key)
            assert deleted_value is None, (
                f"元数据未从UI删除 | 期望: None | 实际: {deleted_value}"
            )

        # ------------------ 步骤8：HEAD请求验证元数据已删除 ------------------
        with allure_step_log("步骤8: HEAD请求验证元数据已从服务端删除"):
            headers = _aws_sign_request(
                "HEAD", uri, credential_ak, credential_sk,
                "cn-north-1", "s3", host,
            )
            response = requests.head(
                f"{endpoint_url}{uri}", headers=headers, timeout=30, verify=False
            )
            assert response.status_code == 200, (
                f"HEAD请求失败 | 状态码: {response.status_code}"
            )
            meta_header = f"x-amz-meta-{metadata_key}"
            assert meta_header not in response.headers, (
                f"响应头中仍包含已删除的元数据字段 {meta_header} | 响应头: {dict(response.headers)}"
            )

        # ------------------ 清理1：删除个人凭证 ------------------
        with allure_step_log("清理1: 删除个人凭证"):
            obs_page.goto_service("对象存储专业版")
            obs_page.goto_submenu("个人凭证")
            obs_page.page.wait_for_timeout(2000)
            obs_page.obs_credential_delete(credential_ak)

        # ------------------ 清理2：删除对象 ------------------
        with allure_step_log("清理2: 删除上传的对象"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()
            obs_page.obs_object_delete(object_name)
