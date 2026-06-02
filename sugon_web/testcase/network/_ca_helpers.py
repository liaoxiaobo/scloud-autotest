"""证书管理与HTTPS监听器场景共用的辅助函数。"""

from sugon_web.utils.logger import logger


def generate_certificates_on_vm(ssh_vm, vm_mfip, cn_value="localhost"):
    """在虚机上生成证书文件，返回证书内容字典。

    Args:
        ssh_vm: 用于连接虚机的SSH客户端。
        vm_mfip: 虚机管理浮动IP地址。
        cn_value: 服务器证书CN字段值，默认"localhost"。

    Returns:
        dict: 包含以下键的字典：
            - ca_crt: CA证书内容
            - server_key: 服务器私钥内容
            - server_crt: 服务器证书内容
    """
    ssh_vm.connect(vm_mfip)

    # 创建工作目录
    ssh_vm.run("mkdir -p /root/mtls-certificates", check_rc=True)

    # 生成根CA
    ssh_vm.run(
        "cd /root/mtls-certificates && openssl genrsa -out ca.key 2048 && "
        "openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt "
        '-subj "/C=CN/ST=Beijing/L=Beijing/O=MyOrg/CN=MyRootCA"',
        check_rc=True,
    )

    # 获取ca.crt内容
    ca_crt = ssh_vm.run("cat /root/mtls-certificates/ca.crt", check_rc=True).strip()

    # 生成服务器私钥
    ssh_vm.run(
        "cd /root/mtls-certificates && openssl genrsa -out server.key 2048",
        check_rc=True,
    )

    # 获取server.key内容
    server_key = ssh_vm.run("cat /root/mtls-certificates/server.key", check_rc=True).strip()

    # 生成服务器CSR和证书
    ssh_vm.run(
        f'cd /root/mtls-certificates && openssl req -new -key server.key -out server.csr '
        f'-subj "/C=CN/ST=Beijing/L=Beijing/O=MyOrg/CN={cn_value}" && '
        "openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial "
        "-out server.crt -days 365 -sha256",
        check_rc=True,
    )

    # 获取server.crt内容
    server_crt = ssh_vm.run("cat /root/mtls-certificates/server.crt", check_rc=True).strip()

    # 生成客户端证书
    ssh_vm.run(
        "cd /root/mtls-certificates && openssl genrsa -out client.key 2048 && "
        "openssl req -new -key client.key -out client.csr "
        '-subj "/C=CN/ST=Beijing/L=Beijing/O=MyOrg/CN=myclient" && '
        "openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial "
        "-out client.crt -days 365 -sha256",
        check_rc=True,
    )

    # 获取客户端证书内容
    client_crt = ssh_vm.run("cat /root/mtls-certificates/client.crt", check_rc=True).strip()
    client_key = ssh_vm.run("cat /root/mtls-certificates/client.key", check_rc=True).strip()

    logger.info("证书生成完成: ca_crt=%s..., server_crt=%s...", ca_crt[:20], server_crt[:20])

    return {
        "ca_crt": ca_crt,
        "server_key": server_key,
        "server_crt": server_crt,
        "client_crt": client_crt,
        "client_key": client_key,
    }


def create_certificate(vpc_page, certs, cert_type, name, desc):
    """在证书管理页面创建指定类型的证书。

    Args:
        vpc_page: VpcPage 实例。
        certs: mtls_certs 返回的字典，需包含 server_crt、server_key、ca_crt。
        cert_type: "国际服务器证书" 或 "CA证书"。
        name: 证书名称。
        desc: 证书描述。
    """
    kwargs = {
        "name": name,
        "cert_type": cert_type,
        "cert_content": certs["server_crt"] if cert_type == "国际服务器证书" else certs["ca_crt"],
        "desc": desc,
    }
    if cert_type == "国际服务器证书":
        kwargs["private_key"] = certs["server_key"]

    vpc_page.cert_create(**kwargs)
    vpc_page.assert_popup_success()
