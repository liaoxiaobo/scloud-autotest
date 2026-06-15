import pytest
import allure

from sugon_web.common.remote import SSH
from sugon_web.utils.logger import allure_step_log, logger


@allure.epic("计算")
@allure.feature("裸金属BMS-软装版")
@allure.story("软装版裸金属BMS实例-操作绑定公网IP")
class TestBmsBindEip:

    @allure.title("裸金属BMS-绑定公网IP")
    def test_bms_bind_eip(self, bms_page, eip, ssh_host, bms_env):
        """验证裸金属实例绑定公网IP后网络连通性正常。

        注意：验证步骤失败时不解绑，保留绑定状态便于排查。
        仅当所有验证通过后，在测试末尾执行解绑。
        """
        instance_name = bms_env["instance_name"]
        bms_password = bms_env["password"]
        bound_ip = ""

        # 步骤1：搜索裸金属实例
        with allure_step_log("步骤1: 搜索裸金属实例"):
            bms_page._goto_submenu_safe("裸金属实例")
            bms_page.search(instance_name)
            bms_page.assert_list_contain(instance_name, "名称", exact_match=False)

        # 步骤2：绑定公网IP
        with allure_step_log("步骤2: 绑定公网IP"):
            # 若实例已绑定公网IP，先解绑
            row = bms_page._get_row_by_name(instance_name)
            if row:
                row_text = row.text_content() or ""
                # 行文本包含"公网:"说明已有公网IP
                if "公网:" in row_text:
                    try:
                        bms_page.bms_instance_unbind_eip(instance_name)
                        logger.info("已解绑已有公网IP")
                    except Exception as e:
                        logger.warning(f"解绑已有公网IP失败（可能未绑定或无权限）: {e}")
            bound_ip = bms_page.bms_instance_bind_eip(instance_name, eip_ip=eip)
            assert bound_ip, "绑定公网IP失败，未获取到IP地址"

        # 步骤3：验证详情页公网IP
        with allure_step_log("步骤3: 验证详情页公网IP"):
            bms_page.search(instance_name)
            row_data = bms_page.get_row_data(instance_name)
            # 验证列表页显示公网IP
            assert bound_ip in str(row_data), f"列表页未显示绑定的公网IP {bound_ip}"

        # 步骤4：公网IP连通性验证（ping）
        with allure_step_log("步骤4: 公网IP连通性验证"):
            ssh_host.ping(bound_ip, connected=True, count=10, retries=5)

        # 步骤5：SSH登录验证（通过跳板机 172.22.3.160 连接 BMS FIP）
        with allure_step_log("步骤5: SSH登录验证"):
            bms_ssh = SSH()
            try:
                bms_ssh.jumphost_client = ssh_host.ssh_client
                bms_ssh.connect(bound_ip, username="root", pwd=bms_password, use_jumphost=True)
                logger.info(f"SSH连接裸金属实例 {bound_ip} 成功")

                # 步骤6：系统信息验证
                with allure_step_log("步骤6: 系统信息验证"):
                    ip_output = bms_ssh.run("ip a", check_rc=True)
                    assert ip_output, "ip a 命令未返回结果"
                    # 裸金属公网IP通过网关映射，不一定直接显示在网卡上

                    lsblk_output = bms_ssh.run("lsblk", check_rc=True)
                    assert lsblk_output, "lsblk 命令未返回结果"
            finally:
                bms_ssh.close()

        # 步骤7：解绑公网IP（仅在全部验证通过后执行，失败时保留现场）
        with allure_step_log("步骤7: 解绑公网IP"):
            bms_page.bms_instance_unbind_eip(instance_name)
