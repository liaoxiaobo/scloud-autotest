"""证书管理与 HTTPS 场景专用的 pytest fixture。"""

import pytest

from sugon_web.testcase.network._ca_helpers import create_certificate, generate_certificates_on_vm
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.util import random_data

CERT_DESC = "As1234567890-中文"


@pytest.fixture(scope="class")
def mtls_certs(ssh_vm, vm, request):
    """在虚机上预生成证书，类内所有方法共用。

    返回包含多套证书的字典，键为 CN 标识：
    - "localhost": CN=localhost 的证书
    - "slb_vip": CN=SLB VIP 的证书（仅在存在 slb fixture 时生成）
    """
    vm_info = vm[0] if isinstance(vm, list) else vm
    vm_mfip = vm_info["mfip"]

    certs = {}
    with allure_step_log("Setup: 生成 localhost 证书"):
        certs["localhost"] = generate_certificates_on_vm(ssh_vm, vm_mfip, cn_value="localhost")

    try:
        slb = request.getfixturevalue("slb")
        slb_vip = slb.get("vip")
        if slb_vip:
            with allure_step_log(f"Setup: 生成 SLB VIP 证书 (CN={slb_vip})"):
                certs["slb_vip"] = generate_certificates_on_vm(ssh_vm, vm_mfip, cn_value=slb_vip)
    except pytest.FixtureLookupError:
        pass

    return certs


@pytest.fixture(scope="function")
def server_cert(vpc_page, mtls_certs):
    """创建服务器证书，测试结束后自动删除。"""
    certs = mtls_certs.get("slb_vip") or mtls_certs["localhost"]
    name = f"server-crt-{random_data()}"
    with allure_step_log(f"Setup: 创建服务器证书 {name}"):
        create_certificate(vpc_page, certs, "国际服务器证书", name, CERT_DESC)
    yield name
    with allure_step_log(f"Teardown: 删除服务器证书 {name}"):
        vpc_page.cert_delete(name)


@pytest.fixture(scope="function")
def ca_cert(vpc_page, mtls_certs):
    """创建 CA 证书，测试结束后自动删除。"""
    certs = mtls_certs.get("slb_vip") or mtls_certs["localhost"]
    name = f"ca-crt-{random_data()}"
    with allure_step_log(f"Setup: 创建 CA 证书 {name}"):
        create_certificate(vpc_page, certs, "CA证书", name, CERT_DESC)
    yield name
    with allure_step_log(f"Teardown: 删除 CA 证书 {name}"):
        vpc_page.cert_delete(name)
