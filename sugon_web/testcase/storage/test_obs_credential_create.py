import datetime
import hashlib
import hmac

import allure
import requests
from playwright.sync_api import expect

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data


def _aws_sign_request(method, uri, access_key, secret_key, region, service, host):
    """AWS Signature Version 4 signing for S3 requests.

    Args:
        method: HTTP method (e.g., "GET")
        uri: Request URI path (e.g., "/bucket-name")
        access_key: AWS Access Key ID
        secret_key: AWS Secret Access Key
        region: AWS region (e.g., "cn-north-1")
        service: AWS service (e.g., "s3")
        host: Host header value (e.g., "172.22.1.187:20480")

    Returns:
        dict: Headers including Authorization
    """
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    payload_hash = hashlib.sha256(b'').hexdigest()
    headers = {
        'host': host,
        'x-amz-date': amzdate,
    }
    canonical_headers = ''.join(f'{k}:{v}\n' for k, v in sorted(headers.items()))
    signed_headers = ';'.join(sorted(headers.keys()))

    canonical_request = '\n'.join([
        method,
        uri,
        '',
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f'{datestamp}/{region}/{service}/aws4_request'
    string_to_sign = '\n'.join([
        'AWS4-HMAC-SHA256',
        amzdate,
        credential_scope,
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
@allure.story('个人凭证-新建访问密钥')
class TestOBSCredentialCreate:

    @allure.title("对象存储-个人凭证-新建访问密钥")
    def test_obs_credential_create_access_key(self, obs_page, bucket):
        """验证新建访问密钥功能及 AK/SK 的 API 生效性。"""
        desc = f"desc-{random_data()}"
        ak = sk = None

        with allure_step_log("步骤1: 导航到个人凭证页面"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("个人凭证")
            obs_page.wait_for_page_ready()
            obs_page.page.wait_for_timeout(3000)

        with allure_step_log("步骤2: 打开新建访问密钥弹窗"):
            obs_page.obs_credential_click_create()
            dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
                has_text="新建访问密钥"
            ).first
            expect(dialog).to_be_visible(timeout=10000)

        with allure_step_log("步骤3: 填写描述并创建访问密钥"):
            obs_page.obs_credential_create_dialog_fill(desc)
            ak, sk = obs_page.obs_credential_create_dialog_confirm()
            assert ak, "Access Key ID 为空"
            assert sk, "Secret Access Key 为空"
            # 验证成功弹窗展示项目信息
            success_dialog = obs_page.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="创建密钥成功").first
            expect(
                success_dialog.get_by_text("公共测试").first
            ).to_be_visible(timeout=5000)

        with allure_step_log("步骤4: 验证 AK/SK API 生效性"):
            # OBS API 端点与 Web UI 主机不同，使用固定端点地址
            obs_api_host = "172.22.1.187"
            port = 20480
            full_host = f"{obs_api_host}:{port}"
            url = f"http://{full_host}/{bucket['name']}"
            headers = _aws_sign_request(
                "GET",
                f"/{bucket['name']}",
                ak,
                sk,
                "cn-north-1",
                "s3",
                full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"AK/SK API 验证失败，状态码: {response.status_code}, "
                f"响应: {response.text[:200]}"
            )

        with allure_step_log("步骤5: 关闭创建成功弹窗并验证列表"):
            obs_page.obs_credential_close_success_dialog()
            obs_page.assert_list_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )

        with allure_step_log("清理: 删除访问密钥"):
            obs_page.obs_credential_delete(ak)
            obs_page.assert_list_not_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )
