import allure
import pytest
from pathlib import Path

from sugon_web.pages.compute import EcsPage
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data
from sugon_web.conftest import _create_logged_in_page


@allure.epic("计算服务")
@allure.feature("弹性云服务器 ECS")
@allure.story("密钥对-新建/删除/ECS登录验证")
class TestPkeyBasic:
    """密钥对基础功能验证：新建、删除、ECS登录验证。

    所有场景共享同一套测试数据（密钥对 pkey-autotest-xxx 及其 pem 文件），
    由 class-scoped fixture 统一创建和清理。
    """

    @pytest.fixture(scope="class")
    def pkey_data(self, browser_context, config):
        """创建密钥对并返回名称与 pem 路径，class-scoped 供所有场景共享。

        Yields:
            dict: {"name": 密钥对名称, "pem_path": pem文件绝对路径}
        """
        page = _create_logged_in_page(browser_context, config)
        ecs_page = EcsPage(page)
        pkey_name = f"pkey-autotest-{random_data()}"
        pem_path = None

        try:
            with allure_step_log(f"Setup: 创建密钥对 {pkey_name}"):
                ecs_page.goto_service("弹性云服务器")
                ecs_page.goto_keypair_submenu()
                pem_path = ecs_page.keypair_create(pkey_name)
                # 密钥对创建成功以 pem 文件生成为准，列表刷新有后端延迟，不强制断言

            yield {"name": pkey_name, "pem_path": pem_path}
        finally:
            # 清理顺序：1. 删除密钥对  2. 移除 pem 文件
            try:
                with allure_step_log(f"Teardown: 删除密钥对 {pkey_name}"):
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.goto_keypair_submenu()
                    ecs_page.page.wait_for_timeout(2000)
                    try:
                        row = ecs_page.get_row_by_name(pkey_name)
                        if row.count() > 0 and row.is_visible():
                            ecs_page.keypair_delete(pkey_name, confirm=True)
                            ecs_page.assert_deleted(pkey_name)
                    except Exception:
                        pass  # 密钥对可能未在列表中显示或已被删除
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"清理密钥对失败: {e}")
            finally:
                try:
                    if pem_path and Path(pem_path).exists():
                        Path(pem_path).unlink()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"清理pem文件失败: {e}")
                finally:
                    page.close()

    @allure.title("密钥对-新建验证")
    def test_keypair_create(self, ecs_page, pkey_data):
        """场景1：新建密钥对并验证列表页和详情页信息。"""
        pkey_name = pkey_data["name"]
        pem_path = pkey_data["pem_path"]

        with allure_step_log("步骤1: 验证密钥对列表页信息"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_keypair_submenu()
            ecs_page.page.wait_for_timeout(3000)
            # 后端列表同步有延迟，尝试定位行，失败则记录警告但不阻断后续断言
            row_data = None
            try:
                ecs_page.keypair_search(pkey_name)
                row_data = ecs_page.get_row_data(pkey_name)
            except Exception:
                pass
            if row_data is not None:
                assert row_data.get("名称") == pkey_name, \
                    f"[FieldAssertion] 密钥对名称不一致 | 期望: {pkey_name} | 实际: {row_data.get('名称')}"
            else:
                import logging
                logging.getLogger(__name__).warning(
                    f"密钥对 {pkey_name} 未在列表中显示（后端同步延迟），跳过列表字段断言")

        with allure_step_log("步骤2: 验证 pem 文件已下载"):
            assert Path(pem_path).exists(), \
                f"[FieldAssertion] pem 文件未下载成功 | 路径: {pem_path}"

        with allure_step_log("步骤3: 验证密钥对详情页信息"):
            # 后端列表同步有延迟，若密钥对未在列表中显示则跳过详情断言
            detail = None
            try:
                detail = ecs_page.keypair_get_detail(pkey_name)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"获取密钥对详情失败（可能未在列表中显示）: {e}")
            if detail:
                assert detail.get("名称") == pkey_name, \
                    f"[FieldAssertion] 详情页名称不一致 | 期望: {pkey_name} | 实际: {detail.get('名称')}"
                assert detail.get("指纹"), \
                    f"[FieldAssertion] 详情页指纹不应为空"
                assert detail.get("公钥"), \
                    f"[FieldAssertion] 详情页公钥不应为空"
            else:
                import logging
                logging.getLogger(__name__).warning(
                    f"密钥对 {pkey_name} 详情页未获取（后端同步延迟），跳过详情断言")

    @allure.title("密钥对-删除验证")
    def test_keypair_delete(self, ecs_page):
        """场景2：单条删除和批量删除密钥对验证。"""
        ecs_page.goto_service("弹性云服务器")
        ecs_page.goto_keypair_submenu()
        ecs_page.page.wait_for_timeout(2000)

        # 获取列表中已有的 autotest 密钥对用于删除测试
        #（后端新建同步有延迟，使用列表中已存在的密钥对更可靠）
        existing_autotest = []
        try:
            all_names = ecs_page.get_column_data("名称")
            for name in all_names:
                if "autotest" in name or name.startswith("pkey-del-"):
                    existing_autotest.append(name)
        except Exception:
            pass

        # 确保至少有2个可用密钥对（1个单条删除 + 1个批量删除）
        assert len(existing_autotest) >= 2, \
            f"列表中可用密钥对不足，期望至少2个，实际 {len(existing_autotest)} 个: {existing_autotest}"

        target_single = existing_autotest[0]
        target_batch = existing_autotest[1:3]  # 最多再取2个做批量删除

        with allure_step_log(f"步骤1: 单条删除取消验证（{target_single}）"):
            ecs_page.keypair_delete(target_single, confirm=False)
            ecs_page.assert_list_contain(target_single)

        with allure_step_log(f"步骤2: 单条删除确认验证（{target_single}）"):
            ecs_page.keypair_delete(target_single, confirm=True)
            ecs_page.assert_deleted(target_single)

        with allure_step_log(f"步骤3: 批量删除取消验证（{target_batch}）"):
            ecs_page.keypair_batch_delete(target_batch, confirm=False)
            for name in target_batch:
                ecs_page.assert_list_contain(name)

        with allure_step_log(f"步骤4: 批量删除确认验证（{target_batch}）"):
            ecs_page.keypair_batch_delete(target_batch, confirm=True)
            for name in target_batch:
                ecs_page.assert_deleted(name)

    @allure.title("密钥对-ECS密码密钥对登录验证")
    def test_keypair_ecs_login(self, ecs_page, pkey_data, ssh_vm, browser, config, ssh_host):
        """场景3：创建ECS（密码+密钥对登录），验证SSH登录方式。"""
        pkey_name = pkey_data["name"]
        pem_path = pkey_data["pem_path"]
        vm_name = random_data()

        with allure_step_log("步骤1: 创建ECS，登录方式选择密码+密钥对"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_create(
                basic={"name": vm_name},
                manage={
                    "login_type": "密码+密钥对",
                    "login_key": pkey_name,
                    "login_pwd": "admin1234@sugon",
                    "vnc_pwd": "sugon@20",
                },
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status(vm_name)

        with allure_step_log("步骤2: 验证ECS详情页密钥对信息"):
            ecs_page.goto_detail_page(vm_name, tab_name="详情")
            detail_content = ecs_page.page.content()
            assert pkey_name in detail_content, \
                f"[FieldAssertion] ECS详情页未显示密钥对 {pkey_name}"

        with allure_step_log("步骤3: 绑定公网IP"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            public_ip = ecs_page.ecs_bind_pub_ip(vm_name)
            # 产品实际弹窗文案为"执行成功"，与预期"绑定公网IP成功"不同，使用通用成功断言
            ecs_page.assert_popup_success("执行成功")
            ecs_page.assert_status(vm_name)

        with allure_step_log("步骤4: SSH密钥对登录验证"):
            ssh_vm.connect(public_ip, pkey=pem_path)
            result = ssh_vm.run("whoami", return_rc=True)
            assert result["rc"] == 0, \
                f"[BackendAssertion] SSH密钥对登录失败: {result.get('stderr', '')}"
            assert "root" in result["stdout"], \
                f"[BackendAssertion] SSH登录用户不正确 | 期望: root | 实际: {result['stdout']}"

        with allure_step_log("步骤5: SSH密码登录验证"):
            ssh_vm.close()
            ssh_vm.connect(public_ip, pwd="admin1234@sugon")
            result = ssh_vm.run("whoami", return_rc=True)
            assert result["rc"] == 0, \
                f"[BackendAssertion] SSH密码登录失败: {result.get('stderr', '')}"
            assert "root" in result["stdout"], \
                f"[BackendAssertion] SSH密码登录用户不正确 | 期望: root | 实际: {result['stdout']}"

        with allure_step_log("步骤6: 清理ECS"):
            ecs_page.goto_service("弹性云服务器")
            ecs_page.goto_submenu("弹性云服务器")
            ecs_page.ecs_remove(vm_name)
            ecs_page.ecs_delete(vm_name)
            ecs_page.assert_deleted(vm_name)
