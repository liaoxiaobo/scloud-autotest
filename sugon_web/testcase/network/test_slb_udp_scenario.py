import random
import time

import allure
import pytest

from sugon_web.testcase.network._lb_fixtures import clean_lb_listener, clean_ip_group
from sugon_web.testcase.network._slb_helpers import (
    assert_udp_all_rejected,
    assert_udp_source_ip_sticky,
    clear_udp_server_log,
    collect_udp_recipients,
    get_ssh_host_source_ip,
    prepare_udp_backend,
    send_udp_message,
    stop_udp_backend,
    wait_for_ping_reachable,
)
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


PORT = 5050
DESC = "1234567890edwqWDWQ中文~"


def _send_udp_batch(ssh_client, target_ip, target_port, prefix, count=3):
    """从指定客户端连续发送多条 UDP 消息，返回发送的消息列表。"""
    base = random.randint(1000, 9999)
    messages = [str(base + idx) for idx in range(count)]
    for message in messages:
        send_udp_message(ssh_client, target_ip, target_port, message)
        time.sleep(0.3)
    return messages


@pytest.mark.parametrize("vm", [{"basic": {"count": 4}, "bind_mfip": True}], indirect=True)
@allure.epic("网络服务")
@allure.feature("负载均衡")
@allure.story("监听器场景验证")
class _BaseTestLbUdpScenario:
    """负载均衡 UDP 监听器场景验证基类。

    覆盖 CSV 中 4 个场景:
    - V1: 4327/4932/410797/411010
    - V2: 436730/436731/436738/436739
    """

    SLB_VERSION = ""

    def test_lb_udp_source_ip(
        self, vpc_page, slb, vm, ssh_vm, ssh_host, clean_lb_listener
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-新建监听器-UDP+源IP基本功能验证")
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-udp-{random_data()}"
        pool_name = f"pool-{random_data()}"
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 创建UDP监听器"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="UDP",
                port=PORT,
                desc=DESC,
                pool_name=pool_name,
                balance_method="源IP",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤2: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], port=PORT, resource_status="运行中"
                )

        with allure_step_log("步骤3: 后端启动UDP server"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤4: 内网VIP发送UDP消息(源IP算法)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(requester["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"vip-{random_data(length=4)}", count=5
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            sticky_backend = assert_udp_source_ip_sticky(
                hit_map, f"{self.SLB_VERSION} UDP 内网 VIP 源IP算法"
            )
            allure.attach(
                f"VIP 源 IP 算法命中后端: {sticky_backend}\n命中分布: {hit_map}",
                name="VIP 源 IP 命中信息",
                attachment_type=allure.attachment_type.TEXT,
            )

        with allure_step_log("步骤5: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")
            actual_eip = vpc_page.get_slb_eip(slb["name"])
            assert actual_eip == eip, f"绑定公网IP不一致: 期望{eip}, 实际{actual_eip}"

        with allure_step_log("步骤6: 公网FIP发送UDP消息"):
            # EIP 绑定后网络收敛需要较长时间，给予充足等待；ICMP 可能被安全组拦截，不依赖 ping
            time.sleep(60)
            # Warm-up: UDP 首包可能触发 conntrack/NAT 建立并被丢弃，先发一个预热包
            warmup_result = send_udp_message(ssh_host, eip, PORT, "0")
            assert warmup_result.get("rc") == 0, f"warm-up UDP 发送失败: {warmup_result}"
            time.sleep(10)
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            time.sleep(5)
            base = random.randint(1000, 9999)
            messages = [str(base + idx) for idx in range(5)]
            for message in messages:
                result = send_udp_message(ssh_host, eip, PORT, message)
                assert result.get("rc") == 0, f"UDP 消息 {message} 发送失败: {result}"
                time.sleep(1)
            time.sleep(10)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            sticky_backend = assert_udp_source_ip_sticky(
                hit_map, f"{self.SLB_VERSION} UDP 公网 FIP 源IP算法"
            )
            allure.attach(
                f"FIP 源 IP 算法命中后端: {sticky_backend}\n命中分布: {hit_map}",
                name="FIP 源 IP 命中信息",
                attachment_type=allure.attachment_type.TEXT,
            )

    def test_lb_udp_health_check(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-健康检查器-UDP基本功能验证")
        cleanup = clean_lb_listener
        requester = vm[0]
        backends = vm[1:4]
        lb_name = f"lb-udp-hc-{random_data()}"
        pool_name = f"pool-{random_data()}"
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("步骤1: 后端启动UDP server"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤2: 创建UDP监听器(开启健康检查)"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="UDP",
                port=PORT,
                desc=DESC,
                pool_name=pool_name,
                balance_method="源IP",
                health_check=True,
                health_type="UDP",
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

        with allure_step_log("步骤3: 添加资源池成员"):
            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤4: 确认Real-Server初始状态为运行中"):
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            for backend in backends:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )

        with allure_step_log("步骤5: 停止ecs1、ecs2的UDP server"):
            stop_udp_backend(ssh_vm, backends[0], port=PORT)
            stop_udp_backend(ssh_vm, backends[1], port=PORT)

        with allure_step_log("步骤6: 确认仅ecs3保持运行中"):
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="离线", timeout=120,
                )
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], resource_status="运行中"
            )

        with allure_step_log("步骤7: 内网VIP发送UDP消息(仅ecs3应接收)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(requester["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"hc-rs3-{random_data(length=4)}", count=5
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            received = {msg: backend for msg, backend in hit_map.items() if backend is not None}
            assert received, f"健康检查场景未在任一后端收到消息: {hit_map}"
            assert all(backend == backends[2]["name"] for backend in received.values()), (
                f"健康检查场景下消息应仅落在 ecs3，但实际命中: {received}"
            )

        with allure_step_log("步骤8: 恢复ecs1、ecs2的UDP server"):
            prepare_udp_backend(ssh_vm, backends[0], port=PORT)
            prepare_udp_backend(ssh_vm, backends[1], port=PORT)
            cleanup.add_backend_server(backends[0], port=PORT)
            cleanup.add_backend_server(backends[1], port=PORT)

        with allure_step_log("步骤9: 确认全部恢复运行中"):
            for backend in backends:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )

        with allure_step_log("步骤10: 关闭健康检查"):
            vpc_page.lb_pool_config_health_check(lb_name, pool_name, enable=False)

        with allure_step_log("步骤11: 停止ecs1、ecs2的UDP server,状态不变"):
            stop_udp_backend(ssh_vm, backends[0], port=PORT)
            stop_udp_backend(ssh_vm, backends[1], port=PORT)
            time.sleep(10)
            vpc_page.goto_lb_pool_detail(lb_name, pool_name)
            vpc_page.assert_lb_pool_basic_info(pool_name, health_check="未开启")
            for backend in backends:
                vpc_page.assert_lb_pool_member_info(
                    backend["name"], resource_status="运行中"
                )

        with allure_step_log("步骤12: 重新开启健康检查(UDP类型)"):
            vpc_page.lb_pool_config_health_check(
                lb_name, pool_name, enable=True, health_type="UDP",
                health_request="", health_expected_response="",
            )
            for backend in backends[:2]:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="离线", timeout=120,
                )
            vpc_page.assert_lb_pool_member_info(
                backends[2]["name"], resource_status="运行中"
            )

        with allure_step_log("步骤13: 恢复ecs1、ecs2的UDP server"):
            prepare_udp_backend(ssh_vm, backends[0], port=PORT)
            prepare_udp_backend(ssh_vm, backends[1], port=PORT)
            cleanup.add_backend_server(backends[0], port=PORT)
            cleanup.add_backend_server(backends[1], port=PORT)

        with allure_step_log("步骤14: 确认全部恢复运行中"):
            for backend in backends:
                vpc_page.wait_lb_pool_member_status(
                    lb_name, pool_name, backend["name"],
                    expected_status="运行中", timeout=120,
                )

        with allure_step_log("步骤15: 再次内网VIP发送UDP消息(源IP一致)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(requester["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"hc-recover-{random_data(length=4)}", count=5
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            assert_udp_source_ip_sticky(
                hit_map, f"{self.SLB_VERSION} UDP 健康检查恢复后源IP算法"
            )

    def test_lb_udp_acl_blacklist_internal(
        self, vpc_page, slb, vm, ssh_vm, clean_lb_listener, clean_ip_group
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-访问控制-黑名单场景（内网）")
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        excluded = vm[1]
        backends = vm[2:4]
        lb_name = f"lb-udp-acl-{random_data()}"
        pool_name = f"pool-{random_data()}"
        ip_group_name = f"ipg-{random_data()}"
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("前置: 创建IP地址组(包含ecs0的IP)"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 后端启动UDP server(ecs2/ecs3)"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤2: 创建UDP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="UDP",
                port=PORT,
                desc=DESC,
                pool_name=pool_name,
                balance_method="源IP",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 配置访问控制(黑名单,包含ecs0)"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(
                lb_name,
                "access_control",
                enable=True,
                access_policy="黑名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("黑名单")

        with allure_step_log("步骤4: 黑名单内客户端访问(ecs0,应被拒绝)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(requester["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"acl-blocked-{random_data(length=4)}", count=3
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            assert_udp_all_rejected(hit_map, f"{self.SLB_VERSION} UDP 黑名单ecs0被拒绝")

        with allure_step_log("步骤5: 黑名单外客户端访问(ecs1,可达)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(excluded["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"acl-allowed-{random_data(length=4)}", count=3
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            received = {msg: backend for msg, backend in hit_map.items() if backend is not None}
            assert received, f"黑名单外ecs1访问应被后端接收，但全部未命中: {hit_map}"

        with allure_step_log("步骤6: IP地址组追加ecs1的IP"):
            vpc_page.ip_group_add_ip_addresses(ip_group_name, [excluded["ip"]])
            vpc_page.assert_popup_success()
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert excluded["ip"] in actual_ips

        with allure_step_log("步骤7: ecs1加入黑名单后再次访问(应被拒绝)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(excluded["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"acl-blocked2-{random_data(length=4)}", count=3
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            assert_udp_all_rejected(hit_map, f"{self.SLB_VERSION} UDP 黑名单ecs1被拒绝")

        with allure_step_log("步骤8: IP地址组移除ecs1的IP"):
            vpc_page.ip_group_delete_ip_addresses(ip_group_name, [excluded["ip"]])
            actual_ips = vpc_page.get_detail_ip_addresses()
            assert excluded["ip"] not in actual_ips

        with allure_step_log("步骤9: ecs1再次访问(应恢复)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(excluded["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"acl-recover-{random_data(length=4)}", count=3
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            received = {msg: backend for msg, backend in hit_map.items() if backend is not None}
            assert received, f"移除黑名单后ecs1访问应被后端接收: {hit_map}"

        with allure_step_log("步骤10: 修改为允许所有IP"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(lb_name, "access_control", enable=False)
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("允许所有IP访问")

        with allure_step_log("步骤11: 允许所有IP后各客户端访问"):
            for vm_data in [requester, excluded]:
                for backend in backends:
                    clear_udp_server_log(ssh_vm, backend, port=PORT)
                ssh_vm.connect(vm_data["mfip"])
                messages = _send_udp_batch(
                    ssh_vm,
                    lb_vip,
                    PORT,
                    prefix=f"acl-open-{vm_data['name']}-{random_data(length=4)}",
                    count=3,
                )
                time.sleep(3)
                hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
                received = {msg: b for msg, b in hit_map.items() if b is not None}
                assert received, (
                    f"允许所有IP后 {vm_data['name']} 访问应被后端接收: {hit_map}"
                )

    def test_lb_udp_acl_blacklist_external(
        self, vpc_page, slb, vm, ssh_vm, ssh_host,
        clean_lb_listener, clean_ip_group,
    ):
        allure.dynamic.title(f"{self.SLB_VERSION.lower()}-访问控制-黑名单场景-外网LB")
        cleanup = clean_lb_listener
        ip_group_cleanup = clean_ip_group
        requester = vm[0]
        backends = vm[2:4]
        lb_name = f"lb-udp-acl-ext-{random_data()}"
        pool_name = f"pool-{random_data()}"
        ip_group_name = f"ipg-{random_data()}"
        lb_vip = vpc_page.get_slb_vip(slb["name"])

        with allure_step_log("前置: 创建IP地址组(包含ecs0的IP)"):
            vpc_page.ip_group_create(
                name=ip_group_name,
                ip_addresses=[requester["ip"]],
            )
            ip_group_cleanup.add(ip_group_name)
            vpc_page.assert_popup_success()

        with allure_step_log("步骤1: 后端启动UDP server(ecs2/ecs3)"):
            for backend in backends:
                prepare_udp_backend(ssh_vm, backend, port=PORT)
                cleanup.add_backend_server(backend, port=PORT)

        with allure_step_log("步骤2: 创建UDP监听器并添加资源池成员"):
            vpc_page.slb_lb_create(
                slb_name=slb["name"],
                lb_name=lb_name,
                protocol="UDP",
                port=PORT,
                desc=DESC,
                pool_name=pool_name,
                balance_method="源IP",
                health_check=False,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_listener_exists(lb_name)
            cleanup.add_listener({"slb_name": slb["name"], "lb_name": lb_name, "pool_name": pool_name})

            vpc_page.lb_pool_add_vm(
                vm_names=[b["name"] for b in backends],
                lb_name=lb_name,
                pool_name=pool_name,
                ports=PORT,
            )
            vpc_page.assert_popup_success()

        with allure_step_log("步骤3: 配置访问控制(黑名单)"):
            vpc_page.slb_list_goto_lb_detail(slb["name"], lb_name)
            vpc_page.lb_edit_basic_info(
                lb_name,
                "access_control",
                enable=True,
                access_policy="黑名单",
                ip_group=ip_group_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_lb_basic_info("黑名单")

        with allure_step_log("步骤4: 黑名单内ecs0访问(应被拒绝)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            ssh_vm.connect(requester["mfip"])
            messages = _send_udp_batch(
                ssh_vm, lb_vip, PORT, prefix=f"ext-blocked-{random_data(length=4)}", count=3
            )
            time.sleep(3)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            assert_udp_all_rejected(hit_map, f"{self.SLB_VERSION} UDP 外网黑名单ecs0被拒绝")

        with allure_step_log("步骤5: 绑定公网IP"):
            eip = vpc_page.slb_bind_eip(slb["name"])
            cleanup.add_eip(slb["name"])
            vpc_page.assert_popup_success("执行成功")

        with allure_step_log("步骤6: 外网客户端访问(黑名单外,应可达)"):
            # EIP 绑定后网络收敛需要较长时间，给予充足等待（与源IP测试保持一致）
            time.sleep(60)
            # Warm-up: UDP 首包可能触发 conntrack/NAT 建立并被丢弃，先发一个预热包
            send_udp_message(ssh_host, eip, PORT, "0")
            time.sleep(5)
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            time.sleep(5)
            base = random.randint(1000, 9999)
            messages = [str(base + idx) for idx in range(3)]
            for message in messages:
                send_udp_message(ssh_host, eip, PORT, message)
                time.sleep(0.3)
            time.sleep(10)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            received = {msg: backend for msg, backend in hit_map.items() if backend is not None}
            assert received, f"外网客户端访问应被后端接收，但实际未命中: {hit_map}"

        with allure_step_log("步骤7: 识别并将本机源IP加入黑名单"):
            candidates = get_ssh_host_source_ip(ssh_host, eip)
            assert candidates, "未能从 ssh_host 识别访问公网IP的源IP候选"
            # 仅使用 ip route get 推导出的第一个源IP（最可能的源IP），避免虚拟网卡/link-local 干扰
            primary_ip = candidates[0]
            actual_ips = vpc_page.get_detail_ip_addresses()
            if primary_ip not in actual_ips:
                vpc_page.ip_group_add_ip_addresses(ip_group_name, [primary_ip])
                vpc_page.assert_popup_success()
                actual_ips = vpc_page.get_detail_ip_addresses()
            assert primary_ip in actual_ips, f"IP {primary_ip} 未成功加入黑名单"

        with allure_step_log("步骤8: 外网客户端再次访问(应被拒绝)"):
            for backend in backends:
                clear_udp_server_log(ssh_vm, backend, port=PORT)
            time.sleep(10)
            base = random.randint(1000, 9999)
            messages = [str(base + idx) for idx in range(3)]
            for message in messages:
                send_udp_message(ssh_host, eip, PORT, message)
                time.sleep(0.3)
            time.sleep(10)
            hit_map = collect_udp_recipients(ssh_vm, backends, port=PORT, messages=messages)
            assert_udp_all_rejected(
                hit_map, f"{self.SLB_VERSION} UDP 外网黑名单加入本机源IP后被拒绝"
            )


@pytest.mark.parametrize("slb", [{"version": "V1"}], indirect=True)
class TestLbV1UdpScenario(_BaseTestLbUdpScenario):
    SLB_VERSION = "V1"


@pytest.mark.parametrize("slb", [{"version": "V2"}], indirect=True)
class TestLbV2UdpScenario(_BaseTestLbUdpScenario):
    SLB_VERSION = "V2"
