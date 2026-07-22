import allure
import json
import pytest

from sugon_web.utils.logger import allure_step_log, logger


def _pick_acl_test_account_id(ssh_host, owner_id):
    """从 IAM 用户列表中选取一个非当前桶拥有者的有效账号 ID。

    OSS 桶 ACL 列表展示的是账号的 canonical user ID（即 Keystone userId），
    随机字符串无法被后端识别。这里通过 IAM API 动态获取一个真实存在的其他用户 ID。
    """
    token_res = ssh_host.run(
        'scli token issue --username admin --password keystone_sugon '
        '--iam-url http://172.22.3.150:30510/v3 --format json',
        return_rc=True,
        return_stderr=True,
    )
    assert token_res["rc"] == 0, f"[Backend] 获取 IAM token 失败: {token_res.get('stderr', '')}"
    token = json.loads(token_res["stdout"])["data"]["token"]

    users_res = ssh_host.run(
        f'curl -s -H "X-Auth-Token: {token}" http://172.22.3.150:30510/v3/users',
        return_rc=True,
        return_stderr=True,
    )
    assert users_res["rc"] == 0, f"[Backend] 查询 IAM 用户失败: {users_res.get('stderr', '')}"
    users = json.loads(users_res["stdout"]).get("users", [])
    candidates = [u for u in users if u.get("id") and u["id"] != owner_id]
    assert candidates, "[Backend] 未找到可用于 ACL 测试的非当前用户"

    # 优先使用 autotest 相关业务账号，避免服务账号可能无 S3 访问上下文
    autotest_ids = [u["id"] for u in candidates if "autotest" in (u.get("name") or "")]
    if autotest_ids:
        return autotest_ids[0]
    return candidates[0]["id"]


@allure.epic('存储服务')
@allure.feature('对象存储OSS')
@allure.story('桶操作-访问权限控制-桶ACL管理')
class TestOSSBucketACLManagement:
    """验证OSS对象存储桶ACL管理功能。

    三个场景共享同一个桶（class-scoped fixture）：
    1. 新增桶ACL（创建桶 + 新增账号权限）
    2. 编辑桶ACL（修改已有账号权限）
    3. 删除桶ACL（删除账号权限）

    数据复用策略：场景1创建桶和ACL，场景2编辑该ACL，场景3删除该ACL。
    所有场景执行完成后统一清理（桶由 oss_bucket fixture teardown 自动删除）。
    """

    @allure.title("对象存储OSS-桶操作-访问权限控制-新增桶ACL")
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
    def test_oss_bucket_acl_create(self, oss_page, ssh_host, oss_bucket):
        """新增桶ACL配置，验证创建后列表中显示正确。"""
        bucket_name = oss_bucket["name"]

        with allure_step_log("步骤1: 进入桶详情页并导航到桶ACLs页面"):
            oss_page.oss_bucket_goto_acl_page(bucket_name)
            oss_page.oss_bucket_acl_assert_page_loaded(bucket_name)
            # 桶创建后 ACL 列表默认仅有桶拥有者行，取其 canonical ID 后从 IAM 选一个非拥有者账号
            acl_list = oss_page.oss_bucket_acl_get_list(bucket_name)
            assert acl_list, "[Precondition] ACL 列表为空，无法获取桶拥有者账号"
            owner_id = acl_list[0]["name"]
            account_id = _pick_acl_test_account_id(ssh_host, owner_id)
            logger.info(f"[ACLCreate] 桶拥有者ID: {owner_id} | 测试账号ID: {account_id}")

        with allure_step_log("步骤2: 点击'新建'按钮，弹出新增账号权限弹窗"):
            oss_page.oss_bucket_acl_click_new()
            assert oss_page.oss_bucket_acl_dialog_is_visible("新增账号权限"), \
                "[ExistenceAssertion] '新增账号权限'弹窗未出现"

        with allure_step_log("步骤3: 填写账号权限配置并提交"):
            oss_page.oss_bucket_acl_dialog_fill_account(account_id)
            logger.info(f"[ACLCreate] 填写账号ID: {account_id}")

            oss_page.oss_bucket_acl_dialog_check_permission("桶访问权限", "读取权限")
            logger.info("[ACLCreate] 勾选桶访问权限-读取权限")

            oss_page.oss_bucket_acl_dialog_check_permission("ACL访问权限", "读取权限")
            logger.info("[ACLCreate] 勾选ACL访问权限-读取权限")

            oss_page.oss_bucket_acl_dialog_click_confirm()
            logger.info("[ACLCreate] 点击'确定'按钮")

        with allure_step_log("步骤4: 验证ACL配置已创建成功（P0-存在性断言）"):
            oss_page.wait_for_operation_complete()
            acl_list = oss_page.oss_bucket_acl_get_list(bucket_name)

            account_ids = [item["name"] for item in acl_list]
            assert account_id in account_ids, \
                f"[ListAssertion] ACL列表中未找到账号 '{account_id}' | 实际列表: {account_ids}"

            oss_page.oss_bucket_acl_assert_account_permissions(
                bucket_name, account_id,
                expect_bucket_read=True, expect_acl_read=True,
            )

    @allure.title("对象存储OSS-桶操作-访问权限控制-编辑桶ACL")
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
    def test_oss_bucket_acl_edit(self, oss_page, ssh_host, oss_bucket):
        """编辑桶ACL配置，验证编辑后权限值正确。"""
        bucket_name = oss_bucket["name"]

        with allure_step_log("前置: 准备待编辑的ACL配置"):
            # 使用 IAM 中真实存在的其他账号，避免随机字符串无法被后端识别
            acl_list = oss_page.oss_bucket_acl_get_list(bucket_name)
            assert acl_list, "[Precondition] ACL 列表为空，无法获取桶拥有者账号"
            owner_id = acl_list[0]["name"]
            account_id = _pick_acl_test_account_id(ssh_host, owner_id)
            logger.info(f"[ACLEdit] 桶拥有者ID: {owner_id} | 测试账号ID: {account_id}")
            oss_page.oss_bucket_acl_create(
                bucket_name=bucket_name,
                account_id=account_id,
                bucket_read=True,
                acl_read=True,
            )
            oss_page.wait_for_operation_complete()
            assert oss_page.oss_bucket_acl_exists(bucket_name, account_id), \
                f"[Precondition] 前置ACL配置创建失败 | account_id={account_id}"

        with allure_step_log("步骤1: 导航到桶ACLs页面"):
            oss_page.oss_bucket_goto_acl_page(bucket_name)
            oss_page.oss_bucket_acl_assert_page_loaded(bucket_name)

        with allure_step_log("步骤2: 找到目标ACL配置并点击'编辑'"):
            oss_page.oss_bucket_acl_click_row_edit(account_id)
            logger.info(f"[ACLEdit] 点击账号 {account_id} 的'编辑'按钮")
            assert oss_page.oss_bucket_acl_dialog_is_visible("编辑账号权限"), \
                "[ExistenceAssertion] '编辑账号权限'弹窗未出现"

        with allure_step_log("步骤3: 修改权限配置（增加写入权限）"):
            oss_page.oss_bucket_acl_dialog_uncheck_permission("桶访问权限", "读取权限")
            oss_page.oss_bucket_acl_dialog_uncheck_permission("ACL访问权限", "读取权限")

            oss_page.oss_bucket_acl_dialog_check_permission("桶访问权限", "读取权限")
            oss_page.oss_bucket_acl_dialog_check_permission("桶访问权限", "写入权限")
            oss_page.oss_bucket_acl_dialog_check_permission("ACL访问权限", "读取权限")
            oss_page.oss_bucket_acl_dialog_check_permission("ACL访问权限", "写入权限")
            logger.info("[ACLEdit] 已勾选所有权限（读取+写入）")

            oss_page.oss_bucket_acl_dialog_click_confirm()
            logger.info("[ACLEdit] 点击'确定'按钮")

        with allure_step_log("步骤4: 验证编辑后的ACL权限正确（P1-末态字段断言）"):
            oss_page.wait_for_operation_complete()
            oss_page.oss_bucket_acl_assert_account_permissions(
                bucket_name, account_id,
                expect_bucket_read=True, expect_bucket_write=True,
                expect_acl_read=True, expect_acl_write=True,
            )

    @allure.title("对象存储OSS-桶操作-访问权限控制-删除桶ACL")
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
    def test_oss_bucket_acl_delete(self, oss_page, ssh_host, oss_bucket):
        """删除桶ACL配置，验证删除后列表中不再存在。"""
        bucket_name = oss_bucket["name"]

        with allure_step_log("前置: 准备待删除的ACL配置"):
            # 使用 IAM 中真实存在的其他账号，避免随机字符串无法被后端识别
            acl_list = oss_page.oss_bucket_acl_get_list(bucket_name)
            assert acl_list, "[Precondition] ACL 列表为空，无法获取桶拥有者账号"
            owner_id = acl_list[0]["name"]
            account_id = _pick_acl_test_account_id(ssh_host, owner_id)
            logger.info(f"[ACLDelete] 桶拥有者ID: {owner_id} | 测试账号ID: {account_id}")
            oss_page.oss_bucket_acl_create(
                bucket_name=bucket_name,
                account_id=account_id,
                bucket_read=True,
                acl_read=True,
            )
            oss_page.wait_for_operation_complete()
            assert oss_page.oss_bucket_acl_exists(bucket_name, account_id), \
                f"[Precondition] 前置ACL配置创建失败 | account_id={account_id}"

        with allure_step_log("步骤1: 导航到桶ACLs页面"):
            oss_page.oss_bucket_goto_acl_page(bucket_name)
            oss_page.oss_bucket_acl_assert_page_loaded(bucket_name)

        with allure_step_log("步骤2: 找到目标ACL配置并点击'删除'"):
            oss_page.oss_bucket_acl_click_row_delete(account_id)
            logger.info(f"[ACLDelete] 点击账号 {account_id} 的'删除'按钮")

            oss_page.oss_bucket_acl_click_delete_confirm()
            logger.info("[ACLDelete] 点击确认'确定'按钮")

        with allure_step_log("步骤3: 验证ACL配置已删除（P0-删除断言）"):
            oss_page.wait_for_operation_complete()
            oss_page.oss_bucket_acl_assert_account_not_exists(bucket_name, account_id)
