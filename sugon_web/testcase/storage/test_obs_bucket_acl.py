import datetime
import hashlib
import hmac
import os
import re
from urllib.parse import urlparse

import allure
import requests
from playwright.sync_api import expect

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


# ---------------------------------------------------------------------------
# 模块级辅助函数（AWS签名 + 组织管理操作）
# ---------------------------------------------------------------------------

def _aws_sign_request(method, uri, access_key, secret_key, region, service, host, body=b''):
    """AWS Signature Version 4 signing for S3 requests."""
    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    payload_hash = hashlib.sha256(body).hexdigest()
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


def _goto_org_management(page):
    """导航到组织管理页面。

    先尝试通过顶部菜单点击，若失败则回退到 URL 直达。
    """
    base_url = Config.get('base_url')

    # 策略1：尝试直接访问 IAM 组织管理路由
    page.goto(f"{base_url}/iam/#/departmentManage")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)

    # 若页面显示"系统升级中"，尝试刷新一次
    upgrade_indicators = ["系统升级中", "升级时间"]
    content = page.content()
    if any(ind in content for ind in upgrade_indicators):
        page.reload()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

    # 若仍是升级页面，尝试全局项目管理路由
    content = page.content()
    if any(ind in content for ind in upgrade_indicators):
        page.goto(f"{base_url}/project-manage")
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)


def _select_org_and_switch_project_tab(page, org_name):
    """在组织管理页面选择组织并切换到项目管理 tab。

    前置条件：已在组织管理页面。
    """
    # 在左侧组织树中点击目标组织
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

    # 点击右侧“项目管理”tab
    project_tab = page.locator(".el-tabs__item, .tab-header-bg .el-tab-pane").filter(
        has_text=re.compile(r"项目管理")
    )
    if project_tab.count() > 0:
        project_tab.first.click()
        page.wait_for_timeout(2000)


def _delete_project_if_exists(page, project_name):
    """若项目存在则删除。前置条件：已在项目管理页面。"""
    # 搜索项目
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

    # 点击删除按钮（JS 触发，避免 strict mode）
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

    # 确认删除
    confirm_dialog = page.locator(".el-dialog, .cv-dialog, .sugon-delete-dialog").filter(
        has_text=re.compile(r"删除")
    )
    if confirm_dialog.count() > 0:
        confirm_dialog.first.get_by_text("确定", exact=True).first.click()
        page.wait_for_timeout(3000)


def _create_project(page, project_name):
    """在项目管理页面新建项目。前置条件：已在项目管理页面。"""
    page.wait_for_timeout(3000)

    # 尝试多种策略点击新建按钮
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
        # fallback: 使用 Playwright 标准定位
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

    # 断言所属组织已展示
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
    # 等待弹窗关闭及列表刷新
    page.wait_for_timeout(2000)
    # 验证项目出现在列表中（通过页面内容，避免 strict/hidden 问题）
    assert project_name in page.content(), f"项目'{project_name}'创建后未出现在列表中"


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


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------

@allure.epic('存储服务')
@allure.feature('对象存储专业版')
@allure.story('桶列表-桶ACL配置功能验证')
class TestOBSBucketACL:

    @allure.title("对象存储-为指定账户配置桶ACL并验证生效")
    def test_obs_bucket_acl_configure(self, obs_page, bucket, page):
        """验证为指定账户配置桶ACL后，该账户可通过API访问桶和对象。"""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)
        project_name = f"obs专项{random_data(length=4)}"
        project_id = None
        ak = sk = None

        # ------------------ 前置：上传对象 ------------------
        with allure_step_log("前置: 上传测试对象到桶中"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 步骤1：创建项目 ------------------
        with allure_step_log("步骤1: 创建obs专项项目并记录项目ID"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)
            _create_project(page, project_name)
            # 验证项目出现在列表中（使用页面内容断言，避免 hidden 元素问题）
            assert project_name in page.content(), (
                f"项目'{project_name}'创建后未出现在页面中"
            )
            project_id = _get_project_id(page, project_name)
            assert project_id, f"未能获取项目'{project_name}'的ID"

        # ------------------ 步骤2~3：配置桶ACL ------------------
        with allure_step_log("步骤2: 进入桶ACLs配置页面"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_bucket_acl_config_click()

        with allure_step_log("步骤3: 新建桶ACL权限"):
            obs_page.obs_bucket_acl_create(
                project_id=project_id,
                read_permission=True,
                object_read_permission=True,
            )
            obs_page.obs_bucket_acl_assert_contain(project_name)

        # ------------------ 步骤4：创建AK/SK ------------------
        with allure_step_log("步骤4: 为obs专项项目创建访问密钥"):
            # 导航到个人凭证页面
            # 策略：先回到 OBS 首页（避免 ACL 页无菜单），再通过子菜单进入
            obs_page.page.goto(f"{Config.get('base_url')}/obs")
            obs_page.page.wait_for_load_state('networkidle')
            obs_page.page.wait_for_timeout(3000)
            obs_page.wait_for_page_ready()
            obs_page.goto_submenu("个人凭证")

            # 点击新建按钮打开弹窗
            obs_page.obs_credential_click_create()

            # 若弹窗中有项目选择，先选 obs专项
            dialog = obs_page.page.locator(".cv-dialog, .el-dialog").filter(
                has_text="新建访问密钥"
            ).first
            project_select = dialog.locator(".el-select").filter(
                has_text=re.compile(r"项目")
            )
            if project_select.count() > 0:
                project_select.first.click()
                obs_page.page.wait_for_timeout(500)
                # 使用 JS 点击避免 dialog wrapper 遮挡 dropdown option
                result = obs_page.page.evaluate(
                    """
                    (name) => {
                        const items = document.querySelectorAll(
                            '.el-select-dropdown__item'
                        );
                        for (let item of items) {
                            if (item.innerText.trim() === name) {
                                item.click();
                                return 'clicked';
                            }
                        }
                        const spans = document.querySelectorAll(
                            '.el-select-dropdown__item span'
                        );
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
                assert result == "clicked", f"未能通过 JS 点击选择项目: {project_name}"
                obs_page.page.wait_for_timeout(500)

            ak, sk = obs_page.obs_credential_create_dialog_confirm()
            assert ak, "Access Key ID 为空"
            assert sk, "Secret Access Key 为空"
            obs_page.obs_credential_close_success_dialog()

        # ------------------ 步骤5~6：API验证 ------------------
        with allure_step_log("步骤5: 验证obs专项可读取桶"):
            full_host = "172.22.1.187:20480"
            url = f"http://{full_host}/{bucket['name']}"
            headers = _aws_sign_request(
                "GET", f"/{bucket['name']}", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"桶访问验证失败，状态码: {response.status_code}, "
                f"响应: {response.text[:200]}"
            )

        with allure_step_log("步骤6: 验证obs专项可读取桶内对象"):
            url = f"http://{full_host}/{bucket['name']}/{test_file_name}"
            headers = _aws_sign_request(
                "GET", f"/{bucket['name']}/{test_file_name}", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"对象访问验证失败，状态码: {response.status_code}, "
                f"响应: {response.text[:200]}"
            )

        # ------------------ 清理 ------------------
        with allure_step_log("清理1: 删除obs专项项目的访问密钥"):
            # 确保页面在项目上下文为 obs专项 的个人凭证页
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name=project_name,
            )
            obs_page.goto_submenu("个人凭证")
            obs_page.obs_credential_delete(ak)
            obs_page.assert_list_not_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )

        with allure_step_log("清理2: 删除桶ACL配置"):
            # 切回桶所在的公共测试项目上下文
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_list_contain(bucket["name"])
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_delete(project_name)
            # 断言已删除：页面中不应再包含该项目名称的 ACL 行
            page_content = obs_page.page.content()
            assert (
                project_name not in page_content
                or "暂无数据" in page_content
            ), f"ACL删除后列表仍包含{project_name}"

        with allure_step_log("清理3: 删除obs专项项目"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)

    @allure.title("对象存储-为指定账户配置桶ACL写入权限并验证生效")
    def test_obs_bucket_acl_write_permission(self, obs_page, bucket, page):
        """验证为指定账户配置桶ACL写入权限后，该账户可通过API上传对象。"""
        project_name = f"obs专项{random_data(length=4)}"
        project_id = None
        ak = sk = None
        endpoint_url = None

        # ------------------ 步骤1-2: 创建项目并记录项目ID ------------------
        with allure_step_log("步骤1-2: 创建obs专项项目并记录项目ID"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)
            _create_project(page, project_name)
            assert project_name in page.content(), (
                f"项目'{project_name}'创建后未出现在页面中"
            )
            project_id = _get_project_id(page, project_name)
            assert project_id, f"未能获取项目'{project_name}'的ID"

        # ------------------ 步骤3: 记录桶EndPoint信息 ------------------
        with allure_step_log("步骤3: 记录桶EndPoint信息"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            endpoint_url = obs_page.obs_bucket_endpoint_get(protocol="http")
            assert endpoint_url, "未能获取桶的EndPoint URL"

        # ------------------ 步骤4-5: 配置桶ACL写入权限 ------------------
        with allure_step_log("步骤4-5: 配置桶ACL写入权限"):
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_create(
                project_id=project_id,
                read_permission=False,
                object_read_permission=False,
                write_permission=True,
            )
            obs_page.obs_bucket_acl_assert_contain(project_name)

        # ------------------ 步骤6: 创建AK/SK ------------------
        with allure_step_log("步骤6: 为obs专项项目创建访问密钥"):
            obs_page.page.goto(f"{Config.get('base_url')}/obs")
            obs_page.page.wait_for_load_state('networkidle')
            obs_page.page.wait_for_timeout(3000)
            obs_page.wait_for_page_ready()
            obs_page.goto_submenu("个人凭证")

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
                        const items = document.querySelectorAll(
                            '.el-select-dropdown__item'
                        );
                        for (let item of items) {
                            if (item.innerText.trim() === name) {
                                item.click();
                                return 'clicked';
                            }
                        }
                        const spans = document.querySelectorAll(
                            '.el-select-dropdown__item span'
                        );
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
                assert result == "clicked", f"未能通过 JS 点击选择项目: {project_name}"
                obs_page.page.wait_for_timeout(500)

            ak, sk = obs_page.obs_credential_create_dialog_confirm()
            assert ak, "Access Key ID 为空"
            assert sk, "Secret Access Key 为空"
            obs_page.obs_credential_close_success_dialog()

        # ------------------ 步骤7: API验证写入权限（PUT上传对象） ------------------
        with allure_step_log("步骤7: 使用API验证写入权限生效"):
            parsed = urlparse(endpoint_url)
            host = parsed.netloc
            bucket_name = bucket["name"]
            object_name = "test-put"
            body = b"test-content"
            uri = f"/{bucket_name}/{object_name}"
            url = f"{endpoint_url}{uri}"

            headers = _aws_sign_request(
                "PUT", uri, ak, sk,
                "cn-north-1", "s3", host, body=body,
            )
            response = requests.put(url, headers=headers, data=body, timeout=30)
            assert response.status_code == 200, (
                f"上传对象验证失败，状态码: {response.status_code}, "
                f"响应: {response.text[:200]}"
            )

        # ------------------ 步骤8: 验证对象已上传 ------------------
        with allure_step_log("步骤8: 验证对象已上传至桶内"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()
            obs_page.assert_object_list_contain(object_name)

        # ------------------ 清理 ------------------
        with allure_step_log("清理1: 删除上传的对象"):
            obs_page.obs_object_delete(object_name)

        with allure_step_log("清理2: 删除obs专项项目的访问密钥"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name=project_name,
            )
            obs_page.goto_submenu("个人凭证")
            obs_page.obs_credential_delete(ak)
            obs_page.assert_list_not_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )

        with allure_step_log("清理3: 删除桶ACL配置"):
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_list_contain(bucket_name)
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_delete(project_name)
            page_content = obs_page.page.content()
            assert (
                project_name not in page_content
                or "暂无数据" in page_content
            ), f"ACL删除后列表仍包含{project_name}"

        with allure_step_log("清理4: 删除obs专项项目"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)

    @allure.title("对象存储-平台注册用户桶访问权限及ACL访问权限验证")
    def test_obs_bucket_acl_public_access_validation(self, obs_page, bucket, page):
        """验证平台注册用户的桶访问权限和ACL访问权限配置后，API行为符合预期。"""
        project_name = f"obs专项{random_data(length=4)}"
        ak = sk = None
        endpoint_url = None
        full_host = None

        # ------------------ 前置：上传对象test01 ------------------
        with allure_step_log("前置: 上传测试对象test01到桶中"):
            test_file_path = os.path.join(
                os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
            )
            test_file_name = os.path.basename(test_file_path)
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 步骤1：创建项目 ------------------
        with allure_step_log("步骤1: 创建obs专项项目并记录项目ID"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)
            _create_project(page, project_name)
            assert project_name in page.content(), (
                f"项目'{project_name}'创建后未出现在页面中"
            )

        # ------------------ 步骤2：创建AK/SK ------------------
        with allure_step_log("步骤2: 为obs专项项目创建访问密钥"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name=project_name,
            )
            obs_page.goto_submenu("个人凭证")
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

        # ------------------ 步骤3：记录EndPoint ------------------
        with allure_step_log("步骤3: 记录桶EndPoint信息"):
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

        # ------------------ 预置：确保匿名用户无权限 ------------------
        with allure_step_log("预置: 确保所有用户(匿名)无桶访问权限"):
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_public_edit(
                user_type="所有用户",
                read_permission=False,
                object_read_permission=False,
                write_permission=False,
                acl_read_permission=False,
                acl_write_permission=False,
            )

        # ------------------ 验证点1：桶读取权限+对象读取 ------------------
        with allure_step_log("验证点1: 配置平台注册用户桶读取+对象读取权限"):
            obs_page.obs_bucket_acl_public_edit(
                user_type="平台注册用户",
                read_permission=True,
                object_read_permission=True,
                write_permission=False,
                acl_read_permission=False,
                acl_write_permission=False,
            )

        with allure_step_log("验证点1-1: 无AK/SK访问桶列表应返回403"):
            url = f"{endpoint_url}/{bucket_name}"
            response = requests.get(url, timeout=30)
            assert response.status_code == 403, (
                f"期望403，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        with allure_step_log("验证点1-2: 有AK/SK访问桶列表应返回200"):
            headers = _aws_sign_request(
                "GET", f"/{bucket_name}", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"期望200，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        # ------------------ 验证点2：ACL读取权限 ------------------
        with allure_step_log("验证点2: 配置平台注册用户ACL读取权限"):
            obs_page.obs_bucket_acl_public_edit(
                user_type="平台注册用户",
                read_permission=False,
                object_read_permission=False,
                write_permission=False,
                acl_read_permission=True,
                acl_write_permission=False,
            )

        with allure_step_log("验证点2-1: 无AK/SK访问桶ACL应返回403"):
            url_acl = f"{endpoint_url}/{bucket_name}?acl"
            response = requests.get(url_acl, timeout=30)
            assert response.status_code == 403, (
                f"期望403，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        with allure_step_log("验证点2-2: 有AK/SK访问桶ACL应返回200"):
            headers = _aws_sign_request(
                "GET", f"/{bucket_name}?acl", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url_acl, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"期望200，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        # ------------------ 验证点3：桶写入权限 ------------------
        with allure_step_log("验证点3: 配置平台注册用户桶写入权限"):
            obs_page.obs_bucket_acl_public_edit(
                user_type="平台注册用户",
                read_permission=False,
                object_read_permission=False,
                write_permission=True,
                acl_read_permission=False,
                acl_write_permission=False,
            )

        with allure_step_log("验证点3-1: 有AK/SK PUT上传对象应返回200"):
            object_name = "test-put"
            body = b"test-content"
            uri = f"/{bucket_name}/{object_name}"
            url_put = f"{endpoint_url}{uri}"
            headers = _aws_sign_request(
                "PUT", uri, ak, sk,
                "cn-north-1", "s3", full_host, body=body,
            )
            response = requests.put(url_put, headers=headers, data=body, timeout=30)
            assert response.status_code == 200, (
                f"期望200，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        with allure_step_log("验证点3-2: 验证对象已上传"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()
            obs_page.assert_object_list_contain(object_name)

        with allure_step_log("验证点3-3: 有AK/SK DELETE删除对象应返回204"):
            uri_del = f"/{bucket_name}/{object_name}"
            url_del = f"{endpoint_url}{uri_del}"
            headers = _aws_sign_request(
                "DELETE", uri_del, ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.delete(url_del, headers=headers, timeout=30)
            assert response.status_code == 204, (
                f"期望204，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        # ------------------ 验证点4：ACL写入权限 ------------------
        with allure_step_log("验证点4: 配置平台注册用户ACL写入权限"):
            # 验证点3-2 已离开ACL配置页，需重新进入
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_public_edit(
                user_type="平台注册用户",
                read_permission=False,
                object_read_permission=False,
                write_permission=False,
                acl_read_permission=False,
                acl_write_permission=True,
            )

        with allure_step_log("验证点4-1: 无AK/SK PUT设置桶ACL应返回403"):
            url_acl_put = f"{endpoint_url}/{bucket_name}?acl"
            response = requests.put(
                url_acl_put,
                headers={"x-amz-acl": ""},
                timeout=30,
            )
            assert response.status_code == 403, (
                f"期望403，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        with allure_step_log("验证点4-2: 有AK/SK PUT设置桶ACL应返回200"):
            headers = _aws_sign_request(
                "PUT", f"/{bucket_name}?acl", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            headers["x-amz-acl"] = "public-read"
            response = requests.put(url_acl_put, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"期望200，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        # ------------------ 清理 ------------------
        with allure_step_log("清理1: 删除上传的对象test01"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket_name)
            obs_page.obs_object_tab_click()
            try:
                obs_page.obs_object_delete(test_file_name)
            except Exception:
                pass

        with allure_step_log("清理2: 删除obs专项项目的访问密钥"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name=project_name,
            )
            obs_page.goto_submenu("个人凭证")
            obs_page.obs_credential_delete(ak)
            obs_page.assert_list_not_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )

        with allure_step_log("清理3: 删除obs专项项目"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)

    @allure.title("对象存储-禁用访问密钥验证")
    def test_obs_disable_access_key(self, obs_page, bucket, page):
        """验证禁用访问密钥后，该密钥无法继续访问桶资源。"""
        test_file_path = os.path.join(
            os.path.dirname(__file__), "..", "test_data", "test_upload.txt"
        )
        test_file_name = os.path.basename(test_file_path)
        project_name = f"obs专项{random_data(length=4)}"
        project_id = None
        ak = sk = None
        endpoint_url = None
        full_host = None

        # ------------------ 前置：上传对象 ------------------
        with allure_step_log("前置: 上传测试对象到桶中"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_upload(test_file_path)
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_object_list_contain(test_file_name)

        # ------------------ 步骤1：创建项目 ------------------
        with allure_step_log("步骤1: 创建obs专项项目并记录项目ID"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)
            _create_project(page, project_name)
            assert project_name in page.content(), (
                f"项目'{project_name}'创建后未出现在页面中"
            )
            project_id = _get_project_id(page, project_name)
            assert project_id, f"未能获取项目'{project_name}'的ID"

        # ------------------ 步骤2：记录EndPoint ------------------
        with allure_step_log("步骤2: 记录桶EndPoint信息"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            endpoint_url = obs_page.obs_bucket_endpoint_get(protocol="http")
            assert endpoint_url, "未能获取桶的EndPoint URL"
            parsed = urlparse(endpoint_url)
            full_host = parsed.netloc

        # ------------------ 步骤3：配置桶ACL ------------------
        with allure_step_log("步骤3: 配置桶ACL权限"):
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_create(
                project_id=project_id,
                read_permission=True,
                object_read_permission=True,
            )
            obs_page.obs_bucket_acl_assert_contain(project_name)

        # ------------------ 步骤4：创建AK/SK ------------------
        with allure_step_log("步骤4: 为obs专项项目创建访问密钥"):
            obs_page.page.goto(f"{Config.get('base_url')}/obs")
            obs_page.page.wait_for_load_state('networkidle')
            obs_page.page.wait_for_timeout(3000)
            obs_page.wait_for_page_ready()
            obs_page.goto_submenu("个人凭证")

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

        # ------------------ 步骤5：验证有AK/SK可读取桶 ------------------
        with allure_step_log("步骤5: 验证有AK/SK时可读取桶列表"):
            url = f"{endpoint_url}/{bucket['name']}"
            headers = _aws_sign_request(
                "GET", f"/{bucket['name']}", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 200, (
                f"桶访问验证失败，状态码: {response.status_code}, "
                f"响应: {response.text[:200]}"
            )

        # ------------------ 步骤6：停用访问密钥 ------------------
        with allure_step_log("步骤6: 停用访问密钥"):
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name=project_name,
            )
            obs_page.goto_submenu("个人凭证")
            obs_page.wait_for_page_ready()
            obs_page.page.wait_for_timeout(3000)
            obs_page.obs_credential_stop(ak)
            # 断言状态已变为停用
            obs_page.assert_credential_status(ak, expected_status="停用")

        # ------------------ 步骤7：验证停用后无法读取桶 ------------------
        with allure_step_log("步骤7: 验证停用后无法读取桶列表"):
            headers = _aws_sign_request(
                "GET", f"/{bucket['name']}", ak, sk,
                "cn-north-1", "s3", full_host,
            )
            response = requests.get(url, headers=headers, timeout=30)
            assert response.status_code == 400, (
                f"期望400，实际: {response.status_code}, 响应: {response.text[:200]}"
            )

        # ------------------ 清理 ------------------
        with allure_step_log("清理1: 删除obs专项项目的访问密钥"):
            obs_page.obs_credential_delete(ak)
            obs_page.assert_list_not_contain(
                ak, column_name="访问密钥（Access Key ID）"
            )

        with allure_step_log("清理2: 删除桶ACL配置"):
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.page.wait_for_timeout(3000)
            obs_page.assert_list_contain(bucket["name"])
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_bucket_acl_config_click()
            obs_page.obs_bucket_acl_delete(project_name)
            page_content = obs_page.page.content()
            assert (
                project_name not in page_content
                or "暂无数据" in page_content
            ), f"ACL删除后列表仍包含{project_name}"

        with allure_step_log("清理3: 删除上传的对象"):
            # 从ACL配置页导航回桶详情页的对象tab
            obs_page.goto_service("对象存储专业版")
            obs_page.select_top_nav_project(
                org_name=["sugoncloud", "智能云事业部"],
                project_name="公共测试",
            )
            obs_page.goto_submenu("桶列表")
            obs_page.obs_bucket_enter_detail(bucket["name"])
            obs_page.obs_object_tab_click()
            obs_page.obs_object_delete(test_file_name)

        with allure_step_log("清理4: 删除obs专项项目"):
            _goto_org_management(page)
            _select_org_and_switch_project_tab(page, "智能云事业部")
            _delete_project_if_exists(page, project_name)
