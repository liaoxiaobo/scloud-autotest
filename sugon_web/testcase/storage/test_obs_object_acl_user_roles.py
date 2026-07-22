import datetime
import hashlib
import hmac
import os
import re
import time
from urllib.parse import urlparse

import allure
import pytest
import requests
from playwright.sync_api import expect

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


# ---------------------------------------------------------------------------
# 模块级辅助函数（AWS签名 + 组织管理操作）
# ---------------------------------------------------------------------------

def _aws_sign_request(method, uri, access_key, secret_key, region, service,
                       host, body=b''):
    """AWS Signature Version 4 signing for S3 requests."""
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {'host': host, 'x-amz-date': amzdate}
    canonical_headers = ''.join(
        f'{k}:{v}\n' for k, v in sorted(headers.items())
    )
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
    signature = hmac.new(
        k_signing, string_to_sign.encode('utf-8'), hashlib.sha256
    ).hexdigest()

    headers['Authorization'] = (
        f'AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, '
        f'SignedHeaders={signed_headers}, Signature={signature}'
    )
    return headers


def _goto_org_management(page):
    """导航到组织管理页面。"""
    base_url = Config.get('base_url')
    page.goto(f"{base_url}/iam/#/departmentManage")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)

    upgrade_indicators = ["系统升级中", "升级时间"]
    content = page.content()
    if any(ind in content for ind in upgrade_indicators):
        page.reload()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

    content = page.content()
    if any(ind in content for ind in upgrade_indicators):
        page.goto(f"{base_url}/project-manage")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)


def _select_org_and_switch_project_tab(page, org_name):
    """在组织管理页面选择组织并切换到项目管理 tab。"""
    page.evaluate(
        """
        (orgName) => {
            const tree = document.querySelector('.department_tree, .one-tree');
            if (!tree) return 'no-tree';
            const items = tree.querySelectorAll('.one-tree-msg-text-content, .tree-node-label, .el-tree-node__label');
            for (let item of items) {
                if (item.innerText.trim() === orgName) {
                    item.click();
                    return 'clicked';
                }
            }
            return 'not-found';
        }
        """,
        org_name,
    )
    page.wait_for_timeout(2000)

    project_tab = page.locator(
        ".el-tabs__item, .tab-header-bg .el-tab-pane"
    ).filter(has_text=re.compile(r"项目管理"))
    if project_tab.count() > 0:
        project_tab.first.click()
        page.wait_for_timeout(2000)


def _delete_project_if_exists(page, project_name):
    """若项目存在则删除。前置条件：已在项目管理页面。"""
    search_input = page.locator('input[type="text"]').filter(
        has=page.get_by_placeholder(re.compile(r"搜索|请输入"))
    )
    if search_input.count() > 0:
        search_input.first.fill(project_name)
        page.wait_for_timeout(1000)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

    rows = page.locator(".el-table__row")
    found = False
    for i in range(rows.count()):
        if project_name in rows.nth(i).inner_text():
            found = True
            break
    if not found:
        return

    page.evaluate(
        """
        (name) => {
            const rows = document.querySelectorAll('.el-table__row');
            for (let row of rows) {
                if (row.innerText.includes(name)) {
                    const btns = row.querySelectorAll('button, .el-link, a, .cloud-table-dropdown-item-btn');
                    for (let btn of btns) {
                        if (btn.innerText.trim() === '删除') {
                            btn.click();
                            return 'ok';
                        }
                    }
                }
            }
            return 'not-found';
        }
        """,
        project_name,
    )
    page.wait_for_timeout(2000)

    confirm_dialog = page.locator(
        ".el-dialog, .cv-dialog, .sugon-delete-dialog"
    ).filter(has_text=re.compile(r"删除"))
    if confirm_dialog.count() > 0:
        confirm_dialog.first.get_by_text("确定", exact=True).first.click()
        page.wait_for_timeout(3000)


def _create_project(page, project_name):
    """在项目管理页面新建项目。前置条件：已在项目管理页面。"""
    page.wait_for_timeout(3000)

    clicked = page.evaluate("""
        () => {
            const btns = document.querySelectorAll('button, .el-button, .cloud-button-btn, a');
            for (let btn of btns) {
                const text = btn.innerText.trim();
                if (text === '新建' || text === '新增' || text === '创建') {
                    if (btn.offsetParent !== null) {
                        btn.click();
                        return 'clicked:' + text;
                    }
                }
            }
            return 'not-found';
        }
    """)
    if clicked == 'not-found':
        btn = page.get_by_text("新建", exact=True)
        if btn.count() == 0:
            btn = page.get_by_text("新增", exact=True)
        if btn.count() == 0:
            btn = page.get_by_role("button", name="新建")
        if btn.count() == 0:
            btn = page.locator("button").filter(has_text="新建")
        expect(btn.first).to_be_visible(timeout=10000)
        btn.first.click(force=True)
    page.wait_for_timeout(1500)

    dialog = page.locator(".el-dialog").filter(has_text="新建项目").first
    expect(dialog).to_be_visible(timeout=10000)

    org_item = dialog.locator(".el-form-item").filter(has_text="所属组织")
    expect(org_item.first).to_be_visible(timeout=5000)

    dialog.get_by_placeholder("请输入项目名称").fill(project_name)
    page.wait_for_timeout(500)

    formal = dialog.get_by_text("正式项目", exact=True)
    if formal.count() > 0:
        formal.first.click()
        page.wait_for_timeout(500)

    dialog.get_by_text("确定", exact=True).first.click()
    page.wait_for_timeout(3000)
    page.wait_for_timeout(2000)
    assert project_name in page.content(), (
        f"项目'{project_name}'创建后未出现在列表中"
    )


def _get_project_id(page, project_name):
    """从项目列表中提取指定项目的 ID。前置条件：已在项目管理页面。"""
    pid = page.evaluate(
        """
        (name) => {
            const rows = document.querySelectorAll('.el-table__row');
            for (let row of rows) {
                if (row.innerText.includes(name)) {
                    const m = row.innerText.match(/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/i);
                    if (m) return m[1];
                    const parts = row.innerText.split(/\\s+/);
                    for (let p of parts) {
                        if (p.length > 15 && /^[a-f0-9-]+$/.test(p)) return p;
                    }
                }
            }
            return null;
        }
        """,
        project_name,
    )
    return pid


def _create_obs_credentials(obs_page, project_name):
    """为指定项目创建访问密钥并返回 AK/SK。

    前置条件：已在对象存储专业版服务的个人凭证页面。
    """
    obs_page.obs_credential_click_create()

    dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
        has_text="新建访问密钥"
    ).first
    project_select = dialog.locator(".el-select").filter(
        has_text=re.compile(r"项目")
    )
    if project_select.count() > 0:
        project_select.first.click()
        obs_page.page.wait_for_timeout(500)
        result = obs_page.page.evaluate(
            """
            (name) => {
                const items = document.querySelectorAll('.el-select-dropdown__item');
                for (let item of items) {
                    if (item.innerText.trim() === name) {
                        item.click();
                        return 'clicked';
                    }
                }
                const spans = document.querySelectorAll('.el-select-dropdown__item span');
                for (let span of spans) {
                    if (span.innerText.trim() === name) {
                        span.click();
                        return 'clicked';
                    }
                }
                return 'not-found';
            }
            """,
            project_name,
        )
        assert result == "clicked", f"未能选择项目: {project_name}"
        obs_page.page.wait_for_timeout(500)

    ak, sk = obs_page.obs_credential_create_dialog_confirm()
    assert ak, "Access Key ID 为空"
    assert sk, "Secret Access Key 为空"
    obs_page.obs_credential_close_success_dialog()
    return ak, sk


def _api_get_no_auth(url, timeout=30):
    """发送无认证 GET 请求，返回响应。"""
    return requests.get(url, timeout=timeout)


def _api_get_with_auth(url, uri, ak, sk, host, timeout=30):
    """发送带 AWS Signature V4 认证的 GET 请求，返回响应。"""
    headers = _aws_sign_request(
        "GET", uri, ak, sk, "cn-north-1", "s3", host,
    )
    return requests.get(url, headers=headers, timeout=timeout)


def _api_put_no_auth(url, timeout=30):
    """发送无认证 PUT 请求（带空 x-amz-acl header），返回响应。"""
    return requests.put(url, headers={"x-amz-acl": ""}, timeout=timeout)


def _api_put_with_auth(url, uri, ak, sk, host, timeout=30):
    """发送带 AWS Signature V4 认证的 PUT 请求（带 public-read x-amz-acl），返回响应。"""
    headers = _aws_sign_request(
        "PUT", uri, ak, sk, "cn-north-1", "s3", host,
    )
    headers["x-amz-acl"] = "public-read"
    return requests.put(url, headers=headers, timeout=timeout)


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------

@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('对象ACLs-多种用户角色读取/写入权限验证')
class TestOBSObjectACLUserRoles:

    @allure.title("对象存储-对象ACLs-多种用户角色读取/写入权限验证")
    def test_obs_object_acl_user_roles(self, obs_page, bucket, page):
        """验证多种用户角色的对象ACL读取/写入权限配置及API生效性。

        覆盖用例：407684、407708、407602、407604、407709
        场景1~5按顺序执行，共享"obs专项"项目和AK/SK，
        使用同一fixture桶，各场景通过不同对象名隔离。
        """
        project_name = f"obs专项{random_data(length=4)}"
        project_id = None
        ak = sk = None
        endpoint_url = None
        full_host = None

        # 各场景使用不同对象文件，避免相互影响
        scene_objects = [
            ("test_upload.txt", "场景1"),
            ("test_upload_02.txt", "场景2"),
            ("test_upload_03.txt", "场景3"),
            ("test_upload_04.txt", "场景4"),
            ("test_upload_05.txt", "场景5"),
        ]

        # 记录需要清理的对象ACL
        # 每项: (object_name, acl_type)
        acl_entries = []

        try:
            # ================================================================
            # 共享资源准备
            # ================================================================
            with allure_step_log("前置: 创建obs专项项目并记录项目ID"):
                _goto_org_management(page)
                _select_org_and_switch_project_tab(page, "智能云事业部")
                _delete_project_if_exists(page, project_name)
                _create_project(page, project_name)
                assert project_name in page.content(), (
                    f"项目'{project_name}'创建后未出现在页面中"
                )
                project_id = _get_project_id(page, project_name)
                assert project_id, f"未能获取项目'{project_name}'的ID"

            with allure_step_log("前置: 为obs专项项目创建访问密钥"):
                obs_page.goto_service("对象存储专业版")
                obs_page.select_top_nav_project(
                    org_name=["sugoncloud", "智能云事业部"],
                    project_name=project_name,
                )
                obs_page.goto_submenu("个人凭证")
                ak, sk = _create_obs_credentials(obs_page, project_name)

            with allure_step_log("前置: 记录桶EndPoint信息"):
                obs_page.goto_service("对象存储专业版")
                obs_page.select_top_nav_project(
                    org_name=["sugoncloud", "智能云事业部"],
                    project_name="公共测试",
                )
                obs_page.goto_submenu("桶列表")
                obs_page.obs_bucket_enter_detail(bucket["name"])
                endpoint_url = obs_page.obs_bucket_endpoint_get(protocol="http")
                if not endpoint_url:
                    endpoint_url = "http://172.22.1.187:20480"
                parsed = urlparse(endpoint_url)
                full_host = parsed.netloc

            bucket_name = bucket["name"]

            def _ensure_bucket_detail():
                """确保当前在目标桶详情页的对象标签下。"""
                obs_page.goto_service("对象存储专业版")
                obs_page.select_top_nav_project(
                    org_name=["sugoncloud", "智能云事业部"],
                    project_name="公共测试",
                )
                obs_page.page.wait_for_timeout(3000)
                obs_page.obs_bucket_enter_detail(bucket_name)
                obs_page.obs_object_tab_click()
                obs_page.page.wait_for_timeout(1500)

            # ================================================================
            # 场景1：授权所有用户对象读取权限（用例407684）
            # ================================================================
            with allure_step_log("场景1: 授权所有用户对象读取权限（用例407684）"):
                obj_file = os.path.join(
                    os.path.dirname(__file__), "..", "test_data", scene_objects[0][0]
                )
                object_name = scene_objects[0][0]

                _ensure_bucket_detail()
                obs_page.obs_object_upload(obj_file)
                obs_page.page.wait_for_timeout(3000)
                obs_page.assert_object_list_contain(object_name)

                obs_page.obs_object_enter_detail(object_name)
                obs_page.obs_object_acl_tab_click()

                with allure_step_log("场景1-预置: 清除所有用户默认权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="所有用户",
                        object_read_permission=False,
                        acl_read_permission=False,
                        acl_write_permission=False,
                    )

                with allure_step_log("场景1: 设置所有用户-对象读取权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="所有用户",
                        object_read_permission=True,
                    )

                base_url = f"http://{full_host}/{bucket_name}/{object_name}"

                with allure_step_log("场景1-验证: 无认证访问应返回200"):
                    resp_status = None
                    for attempt in range(3):
                        resp = _api_get_no_auth(base_url)
                        resp_status = resp.status_code
                        if resp_status == 200:
                            break
                        logger.warning(
                            f"匿名GET返回{resp_status}，等待ACL生效..."
                        )
                        time.sleep(5)
                    assert resp_status == 200, (
                        f"期望200，实际: {resp_status}, "
                        f"响应: {resp.text[:200]}"
                    )

                with allure_step_log("场景1-验证: 有认证访问应返回200"):
                    resp = _api_get_with_auth(
                        base_url, f"/{bucket_name}/{object_name}",
                        ak, sk, full_host,
                    )
                    assert resp.status_code == 200, (
                        f"期望200，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                acl_entries.append((object_name, "public"))

            # ================================================================
            # 场景2：授权平台注册用户对象ACL访问权限-读取权限（用例407708）
            # ================================================================
            with allure_step_log(
                "场景2: 授权平台注册用户对象ACL访问权限-读取权限（用例407708）"
            ):
                obj_file = os.path.join(
                    os.path.dirname(__file__), "..", "test_data", scene_objects[1][0]
                )
                object_name = scene_objects[1][0]

                _ensure_bucket_detail()
                obs_page.obs_object_upload(obj_file)
                obs_page.page.wait_for_timeout(3000)
                obs_page.assert_object_list_contain(object_name)

                obs_page.obs_object_enter_detail(object_name)
                obs_page.obs_object_acl_tab_click()

                with allure_step_log("场景2-预置: 清除平台注册用户默认权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="平台注册用户",
                        object_read_permission=False,
                        acl_read_permission=False,
                        acl_write_permission=False,
                    )

                with allure_step_log("场景2: 设置平台注册用户-ACL读取权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="平台注册用户",
                        acl_read_permission=True,
                    )

                base_url = f"http://{full_host}/{bucket_name}/{object_name}?acl"

                with allure_step_log("场景2-验证: 无认证访问ACL应返回403"):
                    resp = _api_get_no_auth(base_url)
                    assert resp.status_code == 403, (
                        f"期望403，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                with allure_step_log("场景2-验证: 有认证访问ACL应返回200"):
                    resp = _api_get_with_auth(
                        base_url, f"/{bucket_name}/{object_name}?acl",
                        ak, sk, full_host,
                    )
                    assert resp.status_code == 200, (
                        f"期望200，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                acl_entries.append((object_name, "public"))

            # ================================================================
            # 场景3：授权指定账户对象ACL访问权限-写入权限（用例407602）
            # ================================================================
            with allure_step_log(
                "场景3: 授权指定账户对象ACL访问权限-写入权限（用例407602）"
            ):
                obj_file = os.path.join(
                    os.path.dirname(__file__), "..", "test_data", scene_objects[2][0]
                )
                object_name = scene_objects[2][0]

                _ensure_bucket_detail()
                obs_page.obs_object_upload(obj_file)
                obs_page.page.wait_for_timeout(3000)
                obs_page.assert_object_list_contain(object_name)

                obs_page.obs_object_enter_detail(object_name)
                obs_page.obs_object_acl_tab_click()

                obs_page.obs_object_acl_create(
                    project_id=project_id,
                    read_permission=False,
                    write_permission=True,
                )
                obs_page.obs_object_acl_assert_contain(project_name)

                base_url = f"http://{full_host}/{bucket_name}/{object_name}?acl"

                with allure_step_log("场景3-验证: 无认证PUT应返回403"):
                    resp = _api_put_no_auth(base_url)
                    assert resp.status_code == 403, (
                        f"期望403，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                with allure_step_log("场景3-验证: 有认证PUT应返回200"):
                    resp = _api_put_with_auth(
                        base_url, f"/{bucket_name}/{object_name}?acl",
                        ak, sk, full_host,
                    )
                    assert resp.status_code == 200, (
                        f"期望200，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                acl_entries.append((object_name, "project"))

            # ================================================================
            # 场景4：授权所有用户对象ACL访问权限-写入权限（用例407604）
            # ================================================================
            with allure_step_log(
                "场景4: 授权所有用户对象ACL访问权限-写入权限（用例407604）"
            ):
                obj_file = os.path.join(
                    os.path.dirname(__file__), "..", "test_data", scene_objects[3][0]
                )
                object_name = scene_objects[3][0]

                _ensure_bucket_detail()
                obs_page.obs_object_upload(obj_file)
                obs_page.page.wait_for_timeout(3000)
                obs_page.assert_object_list_contain(object_name)

                obs_page.obs_object_enter_detail(object_name)
                obs_page.obs_object_acl_tab_click()

                with allure_step_log("场景4-预置: 清除所有用户默认权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="所有用户",
                        object_read_permission=False,
                        acl_read_permission=False,
                        acl_write_permission=False,
                    )

                with allure_step_log("场景4: 设置所有用户-ACL写入权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="所有用户",
                        acl_write_permission=True,
                    )

                base_url = f"http://{full_host}/{bucket_name}/{object_name}?acl"

                with allure_step_log("场景4-验证: 无认证PUT应返回200"):
                    resp = _api_put_no_auth(base_url)
                    assert resp.status_code == 200, (
                        f"期望200，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                with allure_step_log("场景4-验证: 有认证PUT应返回403"):
                    resp = _api_put_with_auth(
                        base_url, f"/{bucket_name}/{object_name}?acl",
                        ak, sk, full_host,
                    )
                    assert resp.status_code == 403, (
                        f"期望403，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                acl_entries.append((object_name, "public"))

            # ================================================================
            # 场景5：授权平台注册用户对象ACL访问权限-写入权限（用例407709）
            # ================================================================
            with allure_step_log(
                "场景5: 授权平台注册用户对象ACL访问权限-写入权限（用例407709）"
            ):
                obj_file = os.path.join(
                    os.path.dirname(__file__), "..", "test_data", scene_objects[4][0]
                )
                object_name = scene_objects[4][0]

                _ensure_bucket_detail()
                obs_page.obs_object_upload(obj_file)
                obs_page.page.wait_for_timeout(3000)
                obs_page.assert_object_list_contain(object_name)

                obs_page.obs_object_enter_detail(object_name)
                obs_page.obs_object_acl_tab_click()

                with allure_step_log("场景5-预置: 清除平台注册用户默认权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="平台注册用户",
                        object_read_permission=False,
                        acl_read_permission=False,
                        acl_write_permission=False,
                    )

                with allure_step_log("场景5: 设置平台注册用户-ACL写入权限"):
                    obs_page.obs_object_acl_public_edit(
                        user_type="平台注册用户",
                        acl_write_permission=True,
                    )

                base_url = f"http://{full_host}/{bucket_name}/{object_name}?acl"

                with allure_step_log("场景5-验证: 无认证PUT应返回403"):
                    resp = _api_put_no_auth(base_url)
                    assert resp.status_code == 403, (
                        f"期望403，实际: {resp.status_code}, "
                        f"响应: {resp.text[:200]}"
                    )

                with allure_step_log("场景5-验证: 有认证PUT应返回200"):
                    resp_status = None
                    for attempt in range(3):
                        resp = _api_put_with_auth(
                            base_url, f"/{bucket_name}/{object_name}?acl",
                            ak, sk, full_host,
                        )
                        resp_status = resp.status_code
                        if resp_status == 200:
                            break
                        logger.warning(
                            f"认证PUT返回{resp_status}，等待ACL生效..."
                        )
                        time.sleep(5)
                    assert resp_status == 200, (
                        f"期望200，实际: {resp_status}, "
                        f"响应: {resp.text[:200]}"
                    )

                acl_entries.append((object_name, "public"))

        finally:
            # ================================================================
            # 清理数据
            # ================================================================

            # 1. 删除对象ACL配置
            if acl_entries:
                for obj_name, acl_type in acl_entries:
                    with allure_step_log(f"清理: 删除对象 {obj_name} 的ACL"):
                        try:
                            obs_page.obs_bucket_enter_detail(bucket_name)
                            obs_page.obs_object_tab_click()
                            obs_page.obs_object_enter_detail(obj_name)
                            obs_page.obs_object_acl_tab_click()
                            if acl_type == "project":
                                obs_page.obs_object_acl_delete(project_name)
                            else:
                                obs_page.obs_object_acl_public_edit(
                                    user_type="所有用户",
                                    object_read_permission=False,
                                    acl_read_permission=False,
                                    acl_write_permission=False,
                                )
                                obs_page.obs_object_acl_public_edit(
                                    user_type="平台注册用户",
                                    object_read_permission=False,
                                    acl_read_permission=False,
                                    acl_write_permission=False,
                                )
                        except Exception as e:
                            obs_page.logger.warning(
                                f"清理对象ACL失败（{obj_name}）: {e}"
                            )

            # 2. 删除对象
            if acl_entries:
                try:
                    obs_page.select_top_nav_project(
                        org_name=["sugoncloud", "智能云事业部"],
                        project_name="公共测试",
                    )
                    obs_page.obs_bucket_enter_detail(bucket_name)
                    obs_page.obs_object_tab_click()
                    obs_page.page.wait_for_timeout(2000)
                    for obj_name, _ in acl_entries:
                        try:
                            obs_page.obs_object_delete(obj_name)
                        except Exception:
                            pass
                except Exception as e:
                    obs_page.logger.warning(f"清理对象失败: {e}")

            # 3. 删除访问密钥
            if ak:
                with allure_step_log("清理: 删除obs专项项目的访问密钥"):
                    try:
                        base_url = Config.get('base_url').rstrip('/')
                        obs_page.page.goto(
                            f"{base_url}/obs/#/store/auth"
                        )
                        obs_page.wait_for_page_ready()
                        obs_page.page.wait_for_timeout(2000)
                        obs_page.obs_credential_delete(ak)
                    except Exception as e:
                        obs_page.logger.warning(f"清理访问密钥失败: {e}")

            # 4. 删除项目
            if project_name:
                with allure_step_log("清理: 删除obs专项项目"):
                    try:
                        _goto_org_management(page)
                        _select_org_and_switch_project_tab(
                            page, "智能云事业部"
                        )
                        _delete_project_if_exists(page, project_name)
                    except Exception as e:
                        obs_page.logger.warning(f"清理项目失败: {e}")
