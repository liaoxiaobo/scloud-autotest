import os
import shutil
import tempfile
import time
from typing import Any

from sugon_web.config.config import Config
from sugon_web.utils.logger import allure_step_log, logger


def find_normal_sfs_instance_by_protocol(sfs_page, protocol: str, max_pages: int = 10) -> str | None:
    """在 SFS 实例列表中按协议查找状态为正常的实例，自动翻页。

    Args:
        sfs_page: SfsPage 页面对象。
        protocol: 文件协议，"nfs" 或 "cifs"。
        max_pages: 最大翻页数，默认 10。

    Returns:
        第一个匹配的正常状态实例名称；未找到返回 None。
    """
    sfs_page.goto_service("文件存储")
    sfs_page.goto_submenu("实例管理")
    sfs_page.wait_for_page_ready()
    try:
        sfs_page.page.wait_for_selector(".el-table__header-wrapper", state="attached", timeout=10000)
    except Exception:
        pass

    for page_idx in range(max_pages):
        names = sfs_page.get_column_data("名称", context="main") or []
        protocols = sfs_page.get_column_data("文件协议", context="main") or []
        statuses = sfs_page.get_column_data("状态", context="main") or []
        count = min(len(names), len(protocols), len(statuses))
        for idx in range(count):
            name = names[idx].strip()
            proto = protocols[idx].strip().lower()
            status = statuses[idx].strip()
            if proto == protocol.lower() and "正常" in status:
                logger.info(f"找到 {protocol.upper()} 实例: {name} (状态: {status}, 第 {page_idx + 1} 页)")
                return name
        logger.info(f"第 {page_idx + 1} 页未找到状态正常的 {protocol.upper()} 实例")

        next_btn = sfs_page.page.locator(".el-pagination .btn-next").first
        if next_btn.count() == 0 or next_btn.is_disabled():
            logger.info("已到达最后一页，停止翻页")
            break
        next_btn.click()
        sfs_page.wait_for_page_ready()
        try:
            sfs_page.page.wait_for_selector(".el-table__header-wrapper", state="attached", timeout=10000)
        except Exception:
            pass

    logger.warning(f"未找到状态正常的 {protocol.upper()} 实例")
    return None


def create_sfs_instance(sfs_page, name: str, protocol="nfs", cluster="Autotest",
                        network="Autotest", subnet=None, volume_type=None,
                        volume_size=10, cpu_cores=8, ram_gb=8,
                        status_timeout: int = 300) -> dict[str, Any]:
    """创建文件存储实例并等待状态收敛到正常。

    Args:
        sfs_page: SfsPage 页面对象。
        name: 实例名称。
        protocol: 文件协议，"nfs" 或 "cifs"，默认 "nfs"。
        cluster: 集群名称，默认 "Autotest"。
        network: 专有网络名称，默认 "Autotest"。
        subnet: 子网名称，默认 None（自动选择第一个可用子网）。
        volume_type: 云硬盘类型，默认 None（自动选择第一个可用类型）。
        volume_size: 云硬盘大小（GiB），默认 10。
        cpu_cores: CPU 核数筛选，默认 8。
        ram_gb: 内存 GiB 筛选，默认 8。
        status_timeout: 等待状态收敛到正常的超时时间（秒），默认 300。

    Returns:
        dict: 包含 name 及所有实际使用参数的完整字典。
    """

    with allure_step_log(f"创建文件存储实例: {name}"):
        sfs_page.goto_service("文件存储")
        sfs_page.wait_for_page_ready()
        sfs_page.sfs_instance_create(
            name=name,
            protocol=protocol,
            cluster=cluster,
            network=network,
            subnet=subnet,
            volume_type=volume_type,
            volume_size=volume_size,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
        )

        # 立即断言成功弹窗：Toast 自动消失较快，用较长超时一次性等待
        sfs_page.assert_popup_success("创建文件存储实例成功", timeout=60)

        # 等待页面就绪
        sfs_page.wait_for_page_ready()

        # 检查是否有错误弹窗（创建失败时对话框内可能显示错误）
        try:
            error_popup = sfs_page.page.locator(".el-message--error .el-message__content")
            if error_popup.count() > 0 and error_popup.is_visible():
                error_text = error_popup.inner_text()
                raise AssertionError(f"[PopupAssertion] 创建实例失败弹窗: {error_text}")
        except AssertionError:
            raise
        except Exception:
            pass

        sfs_page.assert_list_contain(name)
        sfs_page.sfs_wait_for_status(name, status="正常", timeout=status_timeout)

    return {
        "name": name,
        "protocol": protocol,
        "cluster": cluster,
        "network": network,
        "subnet": subnet,
        "volume_type": volume_type,
        "volume_size": volume_size,
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
    }


def delete_sfs_instance(sfs_page, name: str) -> None:
    """删除文件存储实例（若实例已不存在则跳过）。

    Args:
        sfs_page: SfsPage 页面对象。
        name: 实例名称。
    """
    with allure_step_log(f"删除文件存储实例: {name}"):
        # 先关闭可能存在的弹窗，避免遮挡导航
        sfs_page.close_dialog_if_exists()
        sfs_page.goto_service("文件存储")
        sfs_page.goto_submenu("实例管理")
        sfs_page.wait_for_page_ready()
        try:
            if not sfs_page.get_row_by_name(name).count():
                logger.info(f"实例 {name} 已不在列表中，跳过删除")
                return
        except Exception:
            logger.info(f"实例 {name} 未找到，跳过删除")
            return

        sfs_page.sfs_instance_delete(name)
        sfs_page.assert_deleted(name, timeout=60, refresh=True, refresh_interval=3)


def delete_sfs_instances(sfs_page, names: list[str]) -> None:
    """批量删除文件存储实例（若实例已不存在则跳过）。

    Args:
        sfs_page: SfsPage 页面对象。
        names: 实例名称列表。
    """
    with allure_step_log(f"批量删除文件存储实例: {names}"):
        sfs_page.goto_service("文件存储")
        sfs_page.goto_submenu("实例管理")
        sfs_page.wait_for_page_ready()

        existing_names = []
        for name in names:
            try:
                if sfs_page.get_row_by_name(name).count():
                    existing_names.append(name)
            except Exception:
                pass

        if not existing_names:
            logger.info(f"实例 {names} 均已不在列表中，跳过删除")
            return

        sfs_page.sfs_instance_batch_delete(existing_names)
        sfs_page.assert_deleted(existing_names, timeout=60, refresh=True, refresh_interval=3)


def wait_for_sfs_instance_deleted(ssh_host, name: str, timeout: int = 120, interval: int = 5) -> None:
    """通过后台 CLI 轮询等待 SFS 实例真正删除。

    Args:
        ssh_host: SSH 连接 fixture。
        name: 实例名称。
        timeout: 最长等待秒数，默认 120。
        interval: 轮询间隔秒数，默认 5。
    """
    start = time.time()
    while time.time() - start < timeout:
        result = ssh_host.run(f"scli guest list --name={name}", return_rc=True)
        if result["rc"] != 0:
            raise AssertionError(f"[BackendAssertion] scli guest list 命令执行失败: {result.get('stderr', '')}")
        if name not in result["stdout"]:
            logger.info(f"后台确认实例 {name} 已删除")
            return
        if "deleting" in result.get("stdout", ""):
            logger.info(f"实例 {name} 后台状态为 deleting，继续轮询...")
        time.sleep(interval)
    raise AssertionError(f"[BackendAssertion] 实例 {name} 在后台未在 {timeout} 秒内删除完成")


def create_ecs_for_sfs(page, name: str, network: str = "Autotest", subnet: str = "Autotest(10",
                       bind_eip: bool = True) -> dict[str, Any]:
    """创建用于 SFS 挂载验证的 ECS，并等待状态变为运行中。

    默认使用与 SFS 实例相同的网络和子网，确保 ECS 与 SFS 实例在同一网段。
    默认绑定弹性公网 IP（EIP），用于从 ECS 访问 SFS 服务。

    Args:
        page: Playwright 页面实例。
        name: ECS 名称。
        network: 网络名称，默认 "Autotest"。
        subnet: 子网名称，默认 "Autotest(10"。
        bind_eip: 是否绑定弹性公网 IP，默认 True。

    Returns:
        dict: 包含 name、id、ip、eip（若绑定）、project、network、subnet、host 的字典。
    """
    from sugon_web.pages.compute import EcsPage
    from sugon_web.pages.network import VpcPage

    ecs_page = EcsPage(page)
    ecs_page.goto_service("弹性云服务器")
    ecs_page.ecs_create(
        basic={"name": name, "count": 1, "cluster": "Autotest", "flavor": {"base": "ecs.c6.Autotest"}},
        storage={
            "storage_pool": f"{Config.get('stor')}-test",
            "image": {"source": "镜像", "name": f"{Config.get('stor')}-test"},
            "system_disk": 25,
        },
        network={"networks": [{"network": network, "subnet": subnet}], "enable_ipv6": False},
        manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
    )
    ecs_page.assert_popup_success("创建实例命令下发成功")
    ecs_page.assert_status(name, timeout=600)

    row_data = ecs_page.get_row_data(name)
    ip = row_data["IP地址"].split("固定: ")[-1].strip()
    project = row_data["项目名称"]
    host = row_data["物理机"]
    ecs_id = row_data["名称/ID"].split(":")[1].strip()

    metadata = {
        "name": name,
        "id": ecs_id,
        "ip": ip,
        "project": project,
        "network": network,
        "subnet": subnet,
        "host": host,
    }

    if bind_eip:
        # 分配弹性公网 IP
        vpc_page = VpcPage(page)
        vpc_page.goto_service("虚拟私有云")
        vpc_page.goto_submenu("弹性公网IPv4")
        eip_ips = vpc_page.eip_allocate(pool="public_net(基础版)", count=1, method="快速选择")
        vpc_page.assert_popup_success("执行成功")
        eip_ip = eip_ips[0]

        # 将 EIP 绑定到 ECS
        ecs_page.goto_service("弹性云服务器")
        ecs_page.goto_submenu("弹性云服务器")
        bound_eip = ecs_page.ecs_bind_pub_ip(
            name, subnet=ip, pub_net="public_net(基础版)", eip_ip=eip_ip
        )
        metadata["eip"] = bound_eip
        logger.info(f"ECS {name} 绑定 EIP: {metadata['eip']}")

    return metadata


def _ensure_vm_dns(ssh_vm) -> None:
    """在虚拟机中配置公共 DNS，确保 yum 能够解析外网仓库域名。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
    """
    for ns in ("114.114.114.114", "8.8.8.8"):
        ssh_vm.run(
            f"grep -q 'nameserver {ns}' /etc/resolv.conf || "
            f"echo 'nameserver {ns}' >> /etc/resolv.conf"
        )


def _vm_has_outbound_http(ssh_vm) -> bool:
    """探测虚拟机是否可以通过 HTTP 访问外网（vault.centos.org）。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。

    Returns:
        True 表示可访问外网，False 表示不可访问。
    """
    result = ssh_vm.run(
        "curl --connect-timeout 5 -sI http://vault.centos.org/centos/7.9.2009/os/x86_64/ | head -n1",
        return_rc=True,
        return_stderr=False,
    )
    stdout = result.get("stdout", "") if isinstance(result, dict) else ""
    return result.get("rc") == 0 and ("200" in stdout or "302" in stdout or "301" in stdout)


def _ensure_rpm_cache_on_host(ssh_host) -> str:
    """在测试主机上准备包含 nfs-utils 和 cifs-utils 及其依赖的 RPM 缓存。

    使用 CentOS 7.9 vault 仓库，通过 dnf download --resolve 下载完整依赖树，
    并用 createrepo 生成 repodata，供 VM 作为本地 yum 源使用。

    Args:
        ssh_host: 直连测试主机的 SSH fixture。

    Returns:
        主机上的缓存目录路径。
    """
    cache_dir = "/tmp/sfs_rpm_cache"
    installroot = "/tmp/sfs_rpm_installroot"
    marker = f"{cache_dir}/.ready"

    ready = ssh_host.run(f"test -f {marker} && echo READY", return_rc=True)
    if ready.get("rc") == 0 and "READY" in ready.get("stdout", ""):
        logger.info("主机 RPM 缓存已存在，跳过下载")
        return cache_dir

    logger.info("开始在主机下载 SFS 客户端 RPM 缓存")
    ssh_host.run(f"rm -rf {cache_dir} {installroot}")
    ssh_host.run(f"mkdir -p {cache_dir} {installroot}")
    dnf_cmd = (
        "dnf download --resolve "
        f"--destdir={cache_dir} "
        "--repofrompath=centos7-os,http://vault.centos.org/7.9.2009/os/x86_64/ "
        "--disablerepo=* --enablerepo=centos7-os "
        f"--installroot={installroot} --releasever=7 --nogpgcheck "
        "nfs-utils cifs-utils"
    )
    result = ssh_host.run(dnf_cmd, return_rc=True, return_stderr=True, timeout=900)
    if result.get("rc") != 0:
        raise AssertionError(f"主机 RPM 缓存下载失败: {result.get('stderr', '')}")
    ssh_host.run(f"createrepo {cache_dir}", timeout=300)
    ssh_host.run(f"touch {marker}")
    logger.info("主机 RPM 缓存准备完成")
    return cache_dir


def _transfer_rpm_cache_to_vm(ssh_host, ssh_vm, host_cache_dir: str = "/tmp/sfs_rpm_cache") -> str:
    """将主机上的 RPM 缓存打包、经本地中转后上传到虚拟机。

    Args:
        ssh_host: 直连测试主机的 SSH fixture。
        ssh_vm: 虚拟机 SSH fixture。
        host_cache_dir: 主机缓存目录。

    Returns:
        虚拟机上的缓存目录路径。
    """
    host_tar = "/tmp/sfs_rpm_cache.tar.gz"
    vm_tar = "/tmp/sfs_rpm_cache.tar.gz"
    vm_cache_dir = "/tmp/sfs_rpm_cache"
    local_dir = tempfile.mkdtemp(prefix="sfs_rpm_cache_")
    local_tar = os.path.join(local_dir, "sfs_rpm_cache.tar.gz")

    try:
        logger.info("打包主机 RPM 缓存")
        ssh_host.run(f"tar czf {host_tar} -C {host_cache_dir} .")
        logger.info("下载 RPM 缓存到本地")
        ssh_host.get_file(host_tar, local_tar)
        logger.info("上传 RPM 缓存到虚拟机")
        ssh_vm.put_file(local_tar, vm_tar)
        logger.info("在虚拟机解压 RPM 缓存")
        ssh_vm.run(f"rm -rf {vm_cache_dir} && mkdir -p {vm_cache_dir} && tar xzf {vm_tar} -C {vm_cache_dir}")
        return vm_cache_dir
    finally:
        shutil.rmtree(local_dir, ignore_errors=True)


def _install_package_from_local_repo(ssh_vm, package_name: str, vm_cache_dir: str = "/tmp/sfs_rpm_cache") -> None:
    """通过本地 yum 源安装指定 RPM 包。

    Args:
        ssh_vm: 虚拟机 SSH fixture。
        package_name: 包名。
        vm_cache_dir: 本地 yum 源目录。
    """
    repo_path = "/etc/yum.repos.d/sfs_local.repo"
    repo_content = (
        "[sfs_local]\n"
        "name=SFS Local Repo\n"
        f"baseurl=file://{vm_cache_dir}\n"
        "enabled=1\n"
        "gpgcheck=0\n"
    )
    ssh_vm.run(f"cat > {repo_path} <<'EOF'\n{repo_content}EOF")
    try:
        result = ssh_vm.run(
            f"yum install {package_name} -y --disablerepo=* --enablerepo=sfs_local",
            return_rc=True,
            return_stderr=True,
            timeout=300,
        )
        if result.get("rc") != 0:
            raise AssertionError(f"{package_name} 本地安装失败: {result.get('stderr', '')}")
        logger.info(f"{package_name} 本地安装成功")
    finally:
        ssh_vm.run(f"rm -f {repo_path}")


def _offline_install_sfs_client(ssh_vm, ssh_host, package_name: str) -> None:
    """离线安装 SFS 客户端 RPM 包（先确保主机缓存，再上传到 VM 安装）。

    Args:
        ssh_vm: 虚拟机 SSH fixture。
        ssh_host: 直连测试主机的 SSH fixture。
        package_name: 包名，如 "nfs-utils" 或 "cifs-utils"。
    """
    cache_dir = _ensure_rpm_cache_on_host(ssh_host)
    vm_cache_dir = _transfer_rpm_cache_to_vm(ssh_host, ssh_vm, cache_dir)
    _install_package_from_local_repo(ssh_vm, package_name, vm_cache_dir)


def install_nfs_client(ssh_vm, ssh_host=None) -> None:
    """在虚拟机中安装 NFS 客户端工具（nfs-utils），优先使用系统已有包或本地仓库。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        ssh_host: 直连测试主机的 SSH fixture，用于离线安装兜底。
    """
    check = ssh_vm.run("rpm -q nfs-utils || which mount.nfs4", return_rc=True)
    if check["rc"] == 0:
        logger.info("nfs-utils 已安装或 mount.nfs4 已存在，跳过安装")
        return

    _ensure_vm_dns(ssh_vm)

    if _vm_has_outbound_http(ssh_vm):
        result = ssh_vm.run("yum install nfs-utils -y", return_rc=True, return_stderr=True, timeout=300)
        if result["rc"] == 0:
            logger.info("nfs-utils 通过 yum 安装成功")
            return
        logger.warning(f"在线 yum 安装 nfs-utils 失败: {result.get('stderr', '')}")

    if ssh_host is None:
        raise AssertionError("nfs-utils 安装失败且无 ssh_host 可用，无法进行离线安装")

    logger.info("切换到离线 RPM 安装 nfs-utils")
    _offline_install_sfs_client(ssh_vm, ssh_host, "nfs-utils")

    check2 = ssh_vm.run("which mount.nfs4", return_rc=True)
    if check2["rc"] != 0:
        raise AssertionError("离线安装后仍找不到 mount.nfs4")


def install_cifs_client(ssh_vm, ssh_host=None) -> None:
    """在虚拟机中安装 CIFS 客户端工具（cifs-utils），优先使用系统已有包或本地仓库。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        ssh_host: 直连测试主机的 SSH fixture，用于离线安装兜底。
    """
    check = ssh_vm.run("rpm -q cifs-utils || which mount.cifs", return_rc=True)
    if check["rc"] == 0:
        logger.info("cifs-utils 已安装或 mount.cifs 已存在，跳过安装")
        return

    _ensure_vm_dns(ssh_vm)

    if _vm_has_outbound_http(ssh_vm):
        result = ssh_vm.run("yum install cifs-utils -y", return_rc=True, return_stderr=True, timeout=300)
        if result["rc"] == 0:
            logger.info("cifs-utils 通过 yum 安装成功")
            return
        logger.warning(f"在线 yum 安装 cifs-utils 失败: {result.get('stderr', '')}")

    if ssh_host is None:
        raise AssertionError("cifs-utils 安装失败且无 ssh_host 可用，无法进行离线安装")

    logger.info("切换到离线 RPM 安装 cifs-utils")
    _offline_install_sfs_client(ssh_vm, ssh_host, "cifs-utils")

    check2 = ssh_vm.run("which mount.cifs", return_rc=True)
    if check2["rc"] != 0:
        raise AssertionError("离线安装后仍找不到 mount.cifs")


def mount_nfs(ssh_vm, mount_path: str, local_dir: str) -> None:
    """在虚拟机中执行 NFS 挂载。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        mount_path: NFS 挂载点路径，如 "x.x.x.x:/share"。
        local_dir: 本地挂载目录。
    """
    ssh_vm.run(f"mkdir -p {local_dir}")
    result = ssh_vm.run(f"mount -t nfs4 {mount_path} {local_dir}", return_rc=True, return_stderr=True)
    assert result["rc"] == 0, f"NFS 挂载失败: {result.get('stderr', '')}"


def mount_cifs(ssh_vm, mount_ip: str, share_name: str, local_dir: str) -> None:
    """在虚拟机中执行 CIFS 挂载。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        mount_ip: CIFS 挂载点 IP 地址。
        share_name: CIFS 共享名。
        local_dir: 本地挂载目录。
    """
    ssh_vm.run(f"mkdir -p {local_dir}")
    result = ssh_vm.run(
        f"mount -t cifs -o guest,vers=2.0 //{mount_ip}/{share_name} {local_dir}",
        return_rc=True,
        return_stderr=True,
    )
    assert result["rc"] == 0, f"CIFS 挂载失败: {result.get('stderr', '')}"


def umount_dirs(ssh_vm, *dirs: str) -> None:
    """在虚拟机中卸载指定目录，忽略未挂载错误。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        dirs: 要卸载的目录路径。
    """
    if not dirs:
        return
    result = ssh_vm.run(f"umount {' '.join(dirs)} || true", return_rc=True, return_stderr=True)
    logger.info(f"umount {dirs} result: rc={result.get('rc')}")


def assert_df_contains(ssh_vm, *expected_paths: str) -> str:
    """执行 df -h 并断言输出中包含预期的挂载点路径。

    Args:
        ssh_vm: SSH 虚拟机连接 fixture。
        expected_paths: 期望在 df -h 输出中出现的挂载点路径。

    Returns:
        str: df -h 命令的输出内容。
    """
    output = ssh_vm.run("df -h")
    for path in expected_paths:
        assert path in output, f"df -h 输出中未找到挂载点: {path}\n实际输出:\n{output}"
    return output


def parse_cifs_mount_target(mount_path: str) -> tuple[str, str]:
    """从 CIFS 挂载点路径中解析 IP 和共享名。

    支持 Windows UNC 格式（如 "\\\\ip\\share"）和普通斜杠格式（如 "//ip/share"）。

    Args:
        mount_path: 挂载点路径，如 "\\\\x.x.x.x\\share" 或 "//x.x.x.x/share"。

    Returns:
        tuple: (ip, share_name)
    """
    cleaned = mount_path.strip().replace("\\", "/")
    while cleaned.startswith("//"):
        cleaned = cleaned[2:]
    if ":/" in cleaned:
        ip, share_name = cleaned.split(":/", 1)
    elif "/" in cleaned:
        ip, share_name = cleaned.split("/", 1)
    else:
        raise ValueError(f"无法解析 CIFS 挂载点路径: {mount_path}")
    return ip.strip(), share_name.strip()
