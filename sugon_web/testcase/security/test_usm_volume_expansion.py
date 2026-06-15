import re
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.decorators import only_stor


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('xbd存储池-云硬盘扩容基本功能验证')
class TestUsmVolumeExpansion:

    @allure.title("USM-xbd存储池-云硬盘扩容验证")
    @only_stor("xbd")
    def test_usm_volume_expansion(self, usm_instance, usm_page, ssh_host):
        """通过 fixture 获取共享 USM 实例，执行云硬盘从 300GiB 扩容到 350GiB，
        通过 SSH 后端验证扩容结果。"""

        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪")

        with allure_step_log("步骤2: 进入详情页查看当前云硬盘大小"):
            usm_page.usm_to_details(name)
            usm_page.wait_for_detail_page_ready()
            body_text = usm_page.get_detail_body_text()
            vol_match = re.search(r"(\d+)\s*GiB", body_text)
            current_size = int(vol_match.group(1)) if vol_match else None
            logger.info(f"USM 实例 {name} 当前云硬盘大小: {current_size}GiB")

        with allure_step_log("步骤3: 执行云硬盘扩容（300GiB → 350GiB）"):
            server_id = usm_page.usm_volume_expand(name, 350)
            assert server_id, f"未提取到 USM 实例 {name} 的 server_id"
            logger.info(f"USM 实例 {name} server_id: {server_id}")

        with allure_step_log("步骤4: SSH 连接环境后台，验证云硬盘扩容结果"):
            # scli guest show 获取云堡垒机信息
            cmd = f"scli guest show {server_id}"
            output = ssh_host.run(cmd, check_rc=True)
            logger.info(f"SSH 执行 {cmd} 输出:\n{output}")

            # 从 volume JSON 字段中直接解析 size
            size_match = re.search(r'"size"\s*:\s*(\d+)', output)
            assert size_match is not None, \
                f"scli guest show 输出中未找到 volume size, 输出前500字符: {output[:500]}"
            actual_size = int(size_match.group(1))
            logger.info(f"scli guest show 解析结果: size={actual_size}GiB")

            assert actual_size == 350, \
                f"云硬盘大小不匹配: scli返回={actual_size}GiB, 期望=350GiB"
            logger.info("云硬盘扩容 SSH 后端验证通过: 350GiB")

            # 从 volume JSON 字段中提取 volume_uuid
            vol_json_match = re.search(
                r'"volume"\s*:\s*(\{.*?"uuid"\s*:\s*"[0-9a-fA-F-]+".*?\})',
                output, re.DOTALL
            )
            volume_uuid = ""
            if vol_json_match:
                vol_uuid_in_json = re.search(
                    r'"uuid"\s*:\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"',
                    vol_json_match.group(1)
                )
                if vol_uuid_in_json:
                    volume_uuid = vol_uuid_in_json.group(1)
            logger.info(f"USM 实例 {name} volume_uuid: {volume_uuid}")

            # 用例规格要求：scli volume show <uuid> 验证 size 为 350
            if volume_uuid:
                vol_output = ssh_host.run(f"scli volume show {volume_uuid}", check_rc=True)
                vol_size_match = re.search(r'(?i)size\s*[:|]\s*(\d+)', vol_output)
                if vol_size_match:
                    vol_size = int(vol_size_match.group(1))
                    logger.info(f"scli volume show 解析结果: size={vol_size}GiB")
                    assert vol_size == 350, \
                        f"scli volume show 云硬盘大小不匹配: 实际={vol_size}GiB, 期望=350GiB"
                    logger.info("scli volume show 验证通过: 350GiB")
