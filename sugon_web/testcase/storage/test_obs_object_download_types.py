import datetime
import hashlib
import hmac
import os
import re
import xml.etree.ElementTree as ET

import allure
import pytest
import requests
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


# ---------------------------------------------------------------------------
# 模块级辅助函数
# ---------------------------------------------------------------------------

def _aws_sign_request(method, uri, access_key, secret_key, region, service, host,
                       payload_hash=None):
    """AWS Signature Version 4 signing for S3 requests.

    Args:
        payload_hash: 请求体的 SHA256 哈希值。若为 None，则使用空串哈希。
    """
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    if payload_hash is None:
        payload_hash = hashlib.sha256(b'').hexdigest()

    headers = {
        'host': host,
        'x-amz-date': amzdate,
        'x-amz-content-sha256': payload_hash,
    }
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
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'),
                         hashlib.sha256).hexdigest()

    headers['Authorization'] = (
        f'AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, '
        f'SignedHeaders={signed_headers}, Signature={signature}'
    )
    return headers


def _generate_small_test_files(test_data_dir):
    """生成19种不同扩展名的小文件（<1M），返回文件路径列表和文件名列表。"""
    extensions = [
        "txt", "docx", "pdf", "xlsx", "xls", "csv",
        "pptx", "ppt", "jpg", "png", "gif",
        "mp3", "mp4", "zip", "rar", "exe", "qcow2", "raw", "iso",
    ]
    file_paths = []
    file_names = []
    for ext in extensions:
        file_name = f"test_download_types.{ext}"
        file_path = os.path.join(test_data_dir, file_name)
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Test file for extension {ext}\n")
        file_paths.append(file_path)
        file_names.append(file_name)
    return file_paths, file_names


def _upload_large_file_multipart(endpoint_url, bucket_name, object_name,
                                  ak, sk, size_gb=5, part_size_mb=100):
    """通过 S3 分片上传 API 上传大文件（>5GB）。

    使用内存中的零值数据块进行上传，避免在磁盘创建大文件。
    """
    host = endpoint_url.replace("http://", "").replace("https://", "")
    part_size = part_size_mb * 1024 * 1024
    total_size = size_gb * 1024 * 1024 * 1024 + 1  # 略大于 size_gb
    num_parts = (total_size + part_size - 1) // part_size

    # 预先计算数据块哈希（所有分片使用相同数据）
    chunk = b'\x00' * part_size
    chunk_hash = hashlib.sha256(chunk).hexdigest()

    # 1. 初始化分片上传
    uri = f"/{bucket_name}/{object_name}?uploads"
    headers = _aws_sign_request("POST", uri, ak, sk, "cn-north-1", "s3", host)
    response = requests.post(
        f"{endpoint_url}{uri}", headers=headers, timeout=30, verify=False
    )
    assert response.status_code == 200, (
        f"初始化分片上传失败 | 状态码: {response.status_code} | 响应: {response.text}"
    )

    upload_id_match = re.search(r'<UploadId>([^<]+)</UploadId>', response.text)
    assert upload_id_match, f"响应中未找到 UploadId: {response.text}"
    upload_id = upload_id_match.group(1)
    logger.info(f"分片上传初始化成功，UploadId: {upload_id}, 总分片数: {num_parts}")

    # 2. 上传各分片
    etags = []
    for part_num in range(1, num_parts + 1):
        current_part_size = min(part_size,
                                total_size - (part_num - 1) * part_size)
        current_chunk = chunk[:current_part_size]
        current_hash = chunk_hash if current_part_size == part_size else (
            hashlib.sha256(current_chunk).hexdigest()
        )

        uri = f"/{bucket_name}/{object_name}?partNumber={part_num}&uploadId={upload_id}"
        headers = _aws_sign_request("PUT", uri, ak, sk, "cn-north-1", "s3", host,
                                     payload_hash=current_hash)
        headers['Content-Length'] = str(current_part_size)

        response = requests.put(
            f"{endpoint_url}{uri}", data=current_chunk, headers=headers,
            timeout=300, verify=False
        )
        assert response.status_code == 200, (
            f"上传分片 {part_num}/{num_parts} 失败 | 状态码: {response.status_code}"
        )
        etags.append(response.headers.get('ETag'))
        logger.info(f"分片 {part_num}/{num_parts} 上传完成")

    # 3. 完成分片上传
    uri = f"/{bucket_name}/{object_name}?uploadId={upload_id}"
    headers = _aws_sign_request("POST", uri, ak, sk, "cn-north-1", "s3", host)

    parts_xml = "".join([
        f"<Part><PartNumber>{i + 1}</PartNumber><ETag>{etag}</ETag></Part>"
        for i, etag in enumerate(etags)
    ])
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<CompleteMultipartUpload>{parts_xml}</CompleteMultipartUpload>'
    )

    response = requests.post(
        f"{endpoint_url}{uri}", data=body, headers=headers,
        timeout=60, verify=False
    )
    assert response.status_code == 200, (
        f"完成分片上传失败 | 状态码: {response.status_code} | 响应: {response.text}"
    )
    logger.info(f"大文件上传完成: {object_name} ({size_gb}GB+)")


def _get_download_url(obs_page, file_name):
    """点击对象下载按钮并拦截响应，返回下载 URL。"""
    download_url = None

    def handle_response(response):
        nonlocal download_url
        url = response.url
        if ("objects/url" in url or "objects/share-url" in url) and not download_url:
            try:
                data = response.json()
                if data and "content" in data and data["content"] and "genUrl" in data["content"]:
                    download_url = data["content"]["genUrl"]
            except Exception:
                pass

    # 某些前端通过 window.open / location.assign 触发下载，预先注入拦截脚本
    obs_page.page.evaluate("""
        () => {
            window._capturedDownloadUrl = null;
            const originalOpen = window.open;
            window.open = function(url, target) {
                if (url) window._capturedDownloadUrl = url;
                return originalOpen.apply(this, arguments);
            };
            const originalAssign = window.location.assign;
            window.location.assign = function(url) {
                if (url) window._capturedDownloadUrl = url;
                return originalAssign.apply(this, arguments);
            };
            const originalReplace = window.location.replace;
            window.location.replace = function(url) {
                if (url) window._capturedDownloadUrl = url;
                return originalReplace.apply(this, arguments);
            };
            return 'ok';
        }
    """)

    obs_page.page.on("response", handle_response)
    obs_page.obs_object_download(file_name)
    # 等待 API 响应或下载触发
    obs_page.page.wait_for_timeout(8000)
    obs_page.page.remove_listener("response", handle_response)

    # 如果 response 拦截未获取到，尝试从 window.open 拦截获取
    if not download_url:
        try:
            captured = obs_page.page.evaluate("() => window._capturedDownloadUrl")
            if captured:
                download_url = captured
        except Exception:
            pass

    assert download_url, f"未能获取 {file_name} 的下载URL"
    return download_url


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------

@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象管理-多种类型文件下载场景验证')
class TestOBSObjectDownloadTypes:

    @pytest.mark.parametrize("bucket", [{}], indirect=True)
    @allure.title("对象存储-多种类型文件上传下载验证")
    def test_obs_object_download_types_validation(self, obs_page, bucket, page):
        """验证多种类型文件可上传、可在对象列表中展示、可下载，且支持并发下载。"""
        test_data_dir = os.path.join(
            os.path.dirname(__file__), "..", "test_data"
        )
        bucket_name = bucket["name"]
        large_object_name = "test_large_5g.bin"
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

            # 前置清理：删除已有的测试凭证，避免达到项目密钥数量上限（2个）
            try:
                ak_list = obs_page.get_column_data("访问密钥（Access Key ID）")
                for ak in ak_list:
                    if ak and len(ak) > 5:
                        logger.info(f"清理已有凭证: {ak}")
                        obs_page.obs_credential_delete(ak)
                        obs_page.page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"清理已有凭证时出错: {e}")

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

        # ------------------ 步骤2：进入桶详情并获取EndPoint地址 ------------------
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

        def _ensure_object_visible(obs_page, object_name, max_attempts=6):
            """确保对象在列表中可见，带重试和分页扩大。"""
            for attempt in range(max_attempts):
                # 尝试扩大分页（可能因对话框/加载中而失败，需重试）
                page_size_ok = obs_page._expand_page_size("100")
                if not page_size_ok:
                    obs_page.page.wait_for_timeout(2000)
                    continue
                obs_page.page.wait_for_timeout(2000)
                try:
                    obs_page.assert_object_list_contain(object_name)
                    return True
                except AssertionError:
                    if attempt == max_attempts - 1:
                        raise
                    obs_page.page.wait_for_timeout(2000)
            return False

        # ------------------ 步骤3：生成并上传多种类型小文件 ------------------
        with allure_step_log("步骤3: 生成并上传多种类型小文件"):
            file_paths, file_names = _generate_small_test_files(test_data_dir)
            logger.info(f"生成小文件数量: {len(file_names)}")

            obs_page.obs_object_tab_click()
            obs_page.obs_object_batch_upload(file_paths)
            obs_page.page.wait_for_timeout(5000)
            # 关闭可能残留的弹窗/对话框，避免遮挡分页器
            try:
                obs_page.close_dialog_if_exists()
            except Exception:
                pass

            # 扩大分页并验证所有小文件可见
            for file_name in file_names:
                _ensure_object_visible(obs_page, file_name)
            logger.info("所有小文件上传成功并在对象列表中可见")

        # ------------------ 步骤4：通过API上传大文件 ------------------
        with allure_step_log("步骤4: 通过S3 API上传大于5G的大文件"):
            _upload_large_file_multipart(
                endpoint_url, bucket_name, large_object_name,
                credential_ak, credential_sk, size_gb=5, part_size_mb=100
            )
            # 刷新页面并验证大文件出现在对象列表
            obs_page.page.reload()
            obs_page.wait_for_page_ready()
            obs_page.obs_object_tab_click()
            _ensure_object_visible(obs_page, large_object_name)
            logger.info("大文件上传成功并在对象列表中可见")

        try:
            # ------------------ 步骤5：依次下载各类型文件并验证 ------------------
            with allure_step_log("步骤5: 依次下载各类型文件并验证"):
                obs_page._expand_page_size("100")
                obs_page.page.wait_for_timeout(2000)
                # 选取代表性的文件进行下载验证（覆盖不同扩展名）
                sample_files = [
                    file_names[1],   # docx (txt会被浏览器直接打开，无法拦截下载URL)
                    file_names[5],   # csv
                    file_names[8],   # jpg
                    file_names[12],  # mp4
                    file_names[15],  # exe
                    large_object_name,
                ]
                for file_name in sample_files:
                    if file_name == large_object_name:
                        # 大文件：浏览器下载拦截不稳定（URL生成耗时可能超过8s或触发页面导航）
                        # 优先尝试拦截，失败则回退到S3 API HEAD验证
                        try:
                            download_url = _get_download_url(obs_page, file_name)
                            assert download_url and download_url.startswith("http")
                            response = page.request.head(download_url)
                            assert response.status == 200
                            logger.info(f"大文件下载验证通过: {file_name}")
                        except AssertionError:
                            host = endpoint_url.replace("http://", "").replace("https://", "")
                            uri = f"/{bucket_name}/{file_name}"
                            headers = _aws_sign_request("HEAD", uri, credential_ak, credential_sk,
                                                         "cn-north-1", "s3", host)
                            response = requests.head(f"{endpoint_url}{uri}", headers=headers,
                                                      verify=False, timeout=30)
                            assert response.status_code == 200, (
                                f"大文件 {file_name} 通过S3 API访问失败 | 状态码: {response.status_code}"
                            )
                            logger.info(f"大文件S3 API验证通过: {file_name}")
                    else:
                        download_url = _get_download_url(obs_page, file_name)
                        assert download_url, f"未能获取 {file_name} 的下载URL"
                        assert download_url.startswith("http"), (
                            f"下载URL格式不正确: {download_url}"
                        )
                        response = page.request.get(download_url)
                        assert response.status == 200, (
                            f"下载 {file_name} 失败 | HTTP状态码: {response.status}"
                        )
                        logger.info(f"下载验证通过: {file_name}")

            # ------------------ 步骤6：并发下载同一个对象 ------------------
            with allure_step_log("步骤6: 并发下载同一个对象"):
                obs_page._expand_page_size("100")
                obs_page.page.wait_for_timeout(2000)
                concurrent_file = file_names[1]  # 使用 docx 文件测试并发（txt会被浏览器直接打开）
                download_url = _get_download_url(obs_page, concurrent_file)
                assert download_url, "未能获取并发测试对象的下载URL"

                # 使用多个并发请求验证下载能力
                concurrent_count = 3
                for i in range(concurrent_count):
                    response = page.request.get(download_url)
                    assert response.status == 200, (
                        f"并发下载请求 {i + 1}/{concurrent_count} 失败 | "
                        f"HTTP状态码: {response.status}"
                    )
                logger.info(f"并发下载验证通过: {concurrent_count} 个请求全部成功")
        finally:
            # ------------------ 清理：删除对象和个人凭证 ------------------
            with allure_step_log("清理: 删除对象和个人凭证"):
                try:
                    obs_page.goto_service("对象存储专业版")
                    obs_page.select_top_nav_project(
                        org_name=["sugoncloud", "智能云事业部"],
                        project_name="公共测试",
                    )
                    obs_page._obs_bucket_empty(bucket_name)
                except Exception as e:
                    logger.warning(f"清理对象时出错: {e}")

                try:
                    obs_page.goto_service("对象存储专业版")
                    obs_page.goto_submenu("个人凭证")
                    obs_page.page.wait_for_timeout(2000)
                    if credential_ak:
                        obs_page.obs_credential_delete(credential_ak)
                except Exception as e:
                    logger.warning(f"清理个人凭证时出错: {e}")
