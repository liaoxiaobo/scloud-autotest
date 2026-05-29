import time
import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import only_stor


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('xbd存储池-新建实例-全生命周期验证')
class TestUsmCreateLifecycle:

    @allure.title("USM-xbd存储池-新建实例-全生命周期验证")
    @only_stor("xbd")
    def test_usm_create_with_xbd_lifecycle(self, usm_instance, usm_page):
        """xbd 存储池环境下，通过 fixture 获取共享 USM 实例，
        覆盖关机/启动、跳转地址再验证全流程。"""

        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 云堡垒机实例 {name} 关机"):
            usm_page.goto_list_page()
            usm_page.usm_operations(name, "关机")
            usm_page.assert_usm_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = usm_page.usm_name_clickable(name)
            assert not is_clickable, f"关机后 USM 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤2: 云堡垒机实例 {name} 启动"):
            usm_page.goto_list_page()
            usm_page.usm_operations(name, "开机")
            usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤3: 开机后等待并再次验证实例 {name} 状态"):
            time.sleep(60)
            usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=120)
            # 开机后等待 2 分钟让 USM 服务完全就绪，确保跳转地址 token 有效
            logger.info(f"开机后等待 2 分钟让 USM 服务就绪...")
            time.sleep(120)

        with allure_step_log(f"步骤4: 再次验证实例 {name} 跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning(f"USM 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                if new_page != usm_page.page:
                    new_page.close()
                logger.info(f"USM 实例 {name} 再次跳转地址验证通过")
            usm_page.goto_list_page()

        # 注意：本测试不删除实例，供场景二复用
        logger.info(f"场景一完成，实例 {name} 保留供场景二复用")

    @allure.title("USM-xbd存储池-续期授权生命周期操作")
    @only_stor("xbd")
    def test_usm_renewal_auth_lifecycle(self, usm_instance, usm_page):
        """xbd 存储池环境下，通过 fixture 获取共享 USM 实例执行退订 → 授权（3个月）→
        续期（2个月）的全生命周期操作，验证到期时间更新和跳转地址可用性。"""

        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪")

        with allure_step_log(f"步骤1: 执行退订操作"):
            usm_page.usm_unsubscribe(name)
            usm_page.wait_for_operation_complete(timeout=60)
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            service_status = row_data.get("服务状态", "")
            expire_time = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time = v
                    break
            logger.info(f"USM 实例 {name} 退订后状态: 服务={service_status}, 到期时间={expire_time}")
            assert "已退订" in service_status or "不可用" in service_status, \
                f"退订后服务状态异常: {service_status}"

        with allure_step_log(f"步骤2: 验证退订后详情页信息"):
            usm_page.usm_to_details(name)
            body_text = usm_page.page.inner_text("body")
            assert "--" in body_text, "退订后详情页未显示'--'（跳转地址或到期时间）"
            logger.info("退订后详情页验证通过：跳转地址和到期时间显示为'--'")
            usm_page.goto_list_page()

        with allure_step_log(f"步骤3: 执行授权操作（选择3个月时长）"):
            usm_page.usm_authorize(name, "3个月")
            row_data = usm_page.assert_usm_status(name, service_status="运行", vm_status="运行", timeout=120)
            # 使用模糊匹配查找到期时间字段，避免编码问题
            expire_time_after_auth = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_time_after_auth = v
                    break
            logger.info(f"DEBUG row_data keys: {list(row_data.keys())}")
            logger.info(f"USM 实例 {name} 授权（3个月）完成，到期时间: {expire_time_after_auth}")
            assert expire_time_after_auth and expire_time_after_auth != "--", \
                f"到期时间字段未更新: {expire_time_after_auth}"

        with allure_step_log(f"步骤4: 进入详情页验证授权后跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning("授权后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert (
                    "u-s-m-" in new_page.url
                    or "/dashboard" in new_page.url
                    or "openapiOAuth" in new_page.url
                ), f"新页面未进入 USM 平台，当前 URL: {new_page.url}"
                # 验证跳转页面许可证信息中的过期时间与授权后一致
                if expire_time_after_auth and expire_time_after_auth != "--":
                    usm_page.verify_jump_page_license_expire(new_page, expire_time_after_auth)
                if new_page != usm_page.page:
                    new_page.close()
                logger.info("授权后跳转地址验证通过")
            usm_page.goto_list_page()

        with allure_step_log(f"步骤5: 执行续期操作（延长2个月）"):
            row_data = usm_page.get_row_data(name)
            expire_before = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_before = v
                    break
            logger.info(f"USM 实例 {name} 续期前到期时间: {expire_before}")
            usm_page.usm_renewal(name, "2个月")
            usm_page.wait_for_operation_complete(timeout=30)
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            expire_after = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    expire_after = v
                    break
            logger.info(f"USM 实例 {name} 续期（2个月）后到期时间: {expire_after}")
            assert expire_after and expire_after != expire_before, \
                f"到期时间未变化: 续期前={expire_before}, 续期后={expire_after}"

        with allure_step_log(f"步骤6: 进入详情页验证续期后到期时间和跳转地址"):
            usm_page.usm_to_details(name)
            new_page = usm_page.usm_open_jump_address()
            if new_page is None:
                logger.warning("续期后跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                # 验证跳转页面许可证信息中的过期时间与续期后一致
                if expire_after and expire_after != "--":
                    usm_page.verify_jump_page_license_expire(new_page, expire_after)
                if new_page != usm_page.page:
                    new_page.close()
                logger.info("续期后跳转地址验证通过")
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            detail_expire = ""
            for k, v in row_data.items():
                if "到期时间" in k:
                    detail_expire = v
                    break
            assert detail_expire and detail_expire != "--", \
                f"详情页到期时间异常: {detail_expire}"
            logger.info(f"USM 实例 {name} 续期后验证通过，到期时间: {detail_expire}")

        # 注意：本测试不删除实例，供后续场景复用
        logger.info(f"场景二完成，实例 {name} 保留供后续场景复用")
