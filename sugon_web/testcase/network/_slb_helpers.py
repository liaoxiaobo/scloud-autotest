"""SLB TCP/HTTP/UDP 测试场景共用的辅助函数。

本模块封装三类能力：

1. 在后端虚机上准备或停止用于验证负载均衡的 HTTP/UDP 服务。
2. 采集 HTTP 负载均衡返回结果，并将结果归一化为可断言的统计信息。
3. 通过 UDP server 日志统计哪些 backend 收到了哪些消息。

整体风格保持为轻量级测试辅助模块：

- 对外暴露的函数直接服务测试步骤。
- 以下划线开头的函数仅负责内部归一化和断言拆分。
- 断言失败时尽量附带完整上下文，便于定位场景问题。
"""

from collections import Counter
import shlex
import time

from sugon_web.utils.logger import logger
from sugon_web.assertions.helpers import (
    assert_lb_algorithm,
    assert_udp_source_ip_sticky,
    assert_udp_all_rejected,
)


def _get_vm_name(vm_info):
    """返回用于日志和报错的虚机标识。

    `vm_info` 既可以是包含 `name`、`mfip` 的字典，也可以直接是字符串。
    当缺少 `name` 时，回退为管理浮动 IP。

    Args:
        vm_info: 虚机信息字典，或可直接转为字符串的虚机标识。

    Returns:
        str: 适合展示在日志和异常消息中的虚机名称。
    """
    if isinstance(vm_info, dict):
        return vm_info.get("name") or vm_info["mfip"]
    return str(vm_info)


def _get_vm_mfip(vm_info):
    """返回虚机的管理浮动 IP。

    Args:
        vm_info: 虚机信息字典，或直接可用的管理地址字符串。

    Returns:
        str: 用于 SSH 连接的管理浮动 IP 或等效地址。
    """
    if isinstance(vm_info, dict):
        return vm_info["mfip"]
    return str(vm_info)
def prepare_http_backend_ipv6(ssh_vm, vm_info, backend_key, port=4040, content=None):
    """在后端虚机上启动支持IPv6的HTTP服务。

    使用python3 http.server绑定到::（所有接口），支持IPv4和IPv6访问。
    启动后轮询检查端口监听状态，最多等待60秒。

    Args:
        ssh_vm: 用于连接后端虚机的SSH客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        backend_key: 后端唯一标识，通常用于区分 ``ecs1``、``ecs2`` 等节点。
        port: HTTP服务监听端口。
        content: 自定义首页内容；未提供时默认使用 ``this is {backend_key}``。

    Raises:
        AssertionError: 后端服务在等待时间内未成功监听目标端口。
    """
    backend_content = content or f"this is {backend_key}"
    workdir = f"/root/slb-http-{backend_key}-{port}"
    quoted_workdir = shlex.quote(workdir)
    quoted_content = shlex.quote(backend_content)

    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(f"rm -rf {quoted_workdir} && mkdir -p {quoted_workdir}", check_rc=True)
    ssh_vm.run(
        f"printf '%s\n' {quoted_content} > {quoted_workdir}/index.html",
        check_rc=True,
    )
    # Python 3.6 的 http.server --bind :: 可能因 hostname 解析失败。
    # 先将脚本写入文件，再用 nohup 执行，避免引号嵌套问题。
    script_path = f"/tmp/slb_http_{backend_key}_{port}.py"
    server_script = (
        f"import os, socket, http.server, socketserver\n"
        f"os.chdir({repr(workdir)})\n"
        f"socketserver.TCPServer.address_family = socket.AF_INET6\n"
        f"httpd = socketserver.TCPServer(('::', {port}), http.server.SimpleHTTPRequestHandler)\n"
        f"httpd.serve_forever()\n"
    )
    ssh_vm.run(
        f"cat > {script_path} << 'EOF'\n{server_script}EOF",
        check_rc=True,
    )
    ssh_vm.run(
        f"nohup python3 {script_path} > /tmp/{backend_key}-{port}.log 2>&1 &",
        check_rc=False,
        wait_for_exit=False,
    )

    end_time = time.time() + 60
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lntp | grep ':{port} '", check_rc=False, return_rc=True
        )
        if result["rc"] == 0 and f":{port}" in result["stdout"]:
            logger.info(
                "后端IPv6服务启动成功: %s -> %s",
                _get_vm_name(vm_info),
                backend_key,
            )
            return
        time.sleep(2)

    py_check = ssh_vm.run(
        "command -v python3 || command -v python", check_rc=False, return_rc=True
    )
    log_result = ssh_vm.run(
        f"cat /tmp/{backend_key}-{port}.log 2>/dev/null || true",
        check_rc=False,
        return_rc=True,
    )
    ss_result = ssh_vm.run("ss -lntp", check_rc=False, return_rc=True)
    raise AssertionError(
        f"虚机 {_get_vm_name(vm_info)} 上的IPv6 http.server {port} 在60秒内未启动; "
        f"python3/python 路径: rc={py_check.get('rc')} "
        f"stdout={py_check.get('stdout', '').strip()}; "
        f"启动日志: {log_result.get('stdout', '').strip()}; "
        f"ss -lntp: rc={ss_result.get('rc')} "
        f"stdout={ss_result.get('stdout', '').strip()[:500]}"
    )


def prepare_http_backend(ssh_vm, vm_info, backend_key, port=8080, content=None):
    """在后端虚机上启动一个带标识内容的 HTTP 服务。

    该函数会创建独立工作目录、写入 `index.html`，随后后台启动
    `python3 -m http.server`。启动后会轮询端口监听状态，最多等待 60 秒。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        backend_key: 后端唯一标识，通常用于区分 `ecs1`、`ecs2` 等节点。
        port: HTTP 服务监听端口。
        content: 自定义首页内容；未提供时默认使用 `this is {backend_key}`。

    Raises:
        AssertionError: 后端服务在等待时间内未成功监听目标端口。
    """
    backend_content = content or f"this is {backend_key}"
    workdir = f"/root/slb-http-{backend_key}-{port}"
    quoted_workdir = shlex.quote(workdir)
    quoted_content = shlex.quote(backend_content)

    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(f"rm -rf {quoted_workdir} && mkdir -p {quoted_workdir}", check_rc=True)
    ssh_vm.run(
        f"printf '%s\\n' {quoted_content} > {quoted_workdir}/index.html",
        check_rc=True,
    )
    ssh_vm.run(
        f"cd {quoted_workdir} && nohup python3 -m http.server {port} > /tmp/{backend_key}-{port}.log 2>&1 &",
        check_rc=False,
        wait_for_exit=False,
    )

    end_time = time.time() + 60
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lntp | grep ':{port} '", check_rc=False, return_rc=True
        )
        if result["rc"] == 0 and f":{port}" in result["stdout"]:
            logger.info("后端服务启动成功: %s -> %s", _get_vm_name(vm_info), backend_key)
            return
        time.sleep(10)

    raise AssertionError(
        f"虚机 {_get_vm_name(vm_info)} 上的 http.server {port} 在 60 秒内未启动"
    )


def stop_http_backend(ssh_vm, vm_info, port=8080):
    """停止后端虚机上的 HTTP 服务。

    该函数按端口匹配 `python3 -m http.server` 进程，
    先发送 SIGTERM，若端口仍未释放则追加 SIGKILL，
    确保 TCP 健康检查能正确感知成员离线。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: HTTP 服务监听端口。

    Returns:
        None.
    """
    ssh_vm.connect(_get_vm_mfip(vm_info))
    # 1. 先尝试优雅终止
    ssh_vm.run(f"pkill -f 'python3 -m http.server {port}'", check_rc=False)

    # 2. 轮询等待端口释放（最多 10 秒）
    end_time = time.time() + 10
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lntp | grep ':{port} '", check_rc=False, return_rc=True
        )
        if result["rc"] != 0 or f":{port}" not in result["stdout"]:
            logger.info("后端服务已停止: %s port=%s", _get_vm_name(vm_info), port)
            return
        time.sleep(1)

    # 3. 端口仍未释放，强制 SIGKILL
    logger.warning(
        "后端服务 SIGTERM 后端口仍未释放，执行 SIGKILL: %s port=%s",
        _get_vm_name(vm_info), port
    )
    ssh_vm.run(f"pkill -9 -f 'python3 -m http.server {port}'", check_rc=False)
    time.sleep(2)

    # 4. 最终确认
    result = ssh_vm.run(
        f"ss -lntp | grep ':{port} '", check_rc=False, return_rc=True
    )
    if result["rc"] != 0 or f":{port}" not in result["stdout"]:
        logger.info("后端服务已强制停止: %s port=%s", _get_vm_name(vm_info), port)
    else:
        logger.error(
            "后端服务停止失败，端口仍被占用: %s port=%s",
            _get_vm_name(vm_info), port
        )


def wait_for_ping_reachable(ssh_client, host, timeout_sec=180, interval_sec=10):
    """等待目标地址对当前 SSH 客户端所在主机变为可 ping 通。

    该函数适用于公网 IP 绑定后的异步收敛等待。只有在网络层确认可达后，
    再继续执行 HTTP 访问验证，可减少刚绑定公网 IP 时的瞬时失败。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        host: 需要检测连通性的目标地址。
        timeout_sec: 最大等待时间，单位为秒。
        interval_sec: 轮询间隔，单位为秒。

    Returns:
        None.

    Raises:
        AssertionError: 在等待时间内目标地址始终不可 ping 通时抛出。
    """
    ping_cmd = f"ping -c 5 -W 2 {shlex.quote(host)}"
    end_time = time.time() + timeout_sec
    last_result = None

    while time.time() < end_time:
        last_result = ssh_client.run(ping_cmd, check_rc=False, return_rc=True)
        if last_result["rc"] == 0:
            logger.info("目标地址已可 ping 通: host=%s", host)
            return

        logger.info(
            "等待目标地址可达: host=%s rc=%s stdout=%r stderr=%r",
            host,
            last_result.get("rc"),
            str(last_result.get("stdout", "")).strip(),
            str(last_result.get("stderr", "")).strip(),
        )
        time.sleep(interval_sec)

    raise AssertionError(
        f"目标地址 {host} 在 {timeout_sec} 秒内仍不可 ping 通，"
        f"最后结果: rc={last_result.get('rc') if last_result else None}, "
        f"stdout={str(last_result.get('stdout', '')).strip() if last_result else ''}, "
        f"stderr={str(last_result.get('stderr', '')).strip() if last_result else ''}"
    )


def wait_for_curl_match(ssh_client, curl_cmd, match_text, timeout_sec=180, interval_sec=10):
    """轮询执行 curl 命令，直到响应中包含目标文本。

    该函数适用于需要等待网络配置生效后再继续断言的场景，
    例如 ACL 规则同步、服务注册收敛等。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        curl_cmd: curl 命令字符串。
        match_text: 期望响应中包含的文本。
        timeout_sec: 最大等待时间，单位为秒。
        interval_sec: 轮询间隔，单位为秒。

    Returns:
        None.

    Raises:
        AssertionError: 在等待时间内响应始终未包含目标文本。
    """
    end_time = time.time() + timeout_sec
    last_response = None

    while time.time() < end_time:
        result = ssh_client.run(curl_cmd, check_rc=False, return_rc=True)
        stdout = (result.get("stdout") or "").strip()
        last_response = stdout
        if match_text in stdout:
            logger.info("curl 响应已匹配目标文本: match_text=%s", match_text)
            return

        logger.info(
            "等待 curl 响应匹配: match_text=%s rc=%s stdout=%r",
            match_text,
            result.get("rc"),
            stdout[:200] if stdout else "",
        )
        time.sleep(interval_sec)

    raise AssertionError(
        f"curl 响应在 {timeout_sec} 秒内仍未包含目标文本 {match_text!r}，"
        f"最后响应: {last_response[:500] if last_response else ''}"
    )


def collect_lb_responses(ssh_client, curl_cmd, count, interval_sec=0, check_rc=True):
    """连续执行给定命令并收集原始响应文本。

    该函数不关心命令语义，只负责顺序执行、去除首尾空白并返回结果列表。
    它是更高层 HTTP 采样函数的通用底座。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        curl_cmd: 待执行的命令字符串，通常是 curl 命令。
        count: 采样次数。
        interval_sec: 两次采样之间的等待秒数。
        check_rc: 是否要求命令返回码为 0。

    Returns:
        list[str]: 按采样顺序保存的原始响应文本列表。

    Raises:
        Exception: 当 `check_rc=True` 且底层 SSH 执行失败时，透传底层异常。
    """
    responses = []
    for index in range(count):
        response = ssh_client.run(curl_cmd, check_rc=check_rc).strip()
        responses.append(response)
        if interval_sec > 0 and index < count - 1:
            time.sleep(interval_sec)
    return responses


def collect_lb_http_responses(
    ssh_client, target_url, count=30, interval_sec=1, connect_timeout=10,
    use_cookie=False
):
    """连续 curl 指定 URL，并返回原始响应列表。

    采样结果保留响应顺序，适合后续做轮询、加权轮询等分布断言。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        target_url: 需要访问的负载均衡 URL。
        count: 采样次数。
        interval_sec: 两次采样之间的等待秒数。
        connect_timeout: curl 连接超时时间，单位为秒。
        use_cookie: 是否使用 cookie jar 保存/发送 cookie，用于 HTTP COOKIE
            会话保持验证。默认 False。

    Returns:
        list[str]: 按采样顺序保存的 HTTP 响应文本列表。

    使用说明:
        当测试需要验证调度分布时，优先使用本函数保留完整响应序列，
        再交给 `assert_lb_algorithm()` 做策略断言。
    """
    if use_cookie:
        curl_cmd = (
            f"curl -s -c /tmp/lb_test_cookie -b /tmp/lb_test_cookie "
            f"--connect-timeout {connect_timeout} {shlex.quote(target_url)}"
        )
    else:
        curl_cmd = f"curl -s --connect-timeout {connect_timeout} {shlex.quote(target_url)}"
    return collect_lb_responses(
        ssh_client,
        curl_cmd,
        count=count,
        interval_sec=interval_sec,
        check_rc=False,
    )


def count_lb_responses(ssh_client, target_url, count, interval_sec=0, connect_timeout=5):
    """连续 curl 指定 URL，并按响应内容聚合计数。

    返回 `collections.Counter`，适合“某个后端是否命中”这类存在性断言。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        target_url: 需要访问的负载均衡 URL。
        count: 采样次数。
        interval_sec: 两次采样之间的等待秒数。
        connect_timeout: curl 连接超时时间，单位为秒。

    Returns:
        Counter: 以响应文本为键、命中次数为值的计数对象。

    使用说明:
        当测试只关心“是否命中某个后端”或“某类响应是否出现”时，
        使用本函数比保留完整响应序列更直接。
    """
    return Counter(
        collect_lb_http_responses(
            ssh_client,
            target_url,
            count=count,
            interval_sec=interval_sec,
            connect_timeout=connect_timeout,
        )
    )




UDP_SERVER_SCRIPT = "/opt/network_tool/UDP_server.py"
UDP_CLIENT_SCRIPT = "/opt/network_tool/UDP_client.py"


def _udp_server_log_path(port):
    """生成 UDP server 日志路径，按端口区分。"""
    return f"/tmp/udp_server_{port}.log"


def prepare_udp_backend(ssh_vm, vm_info, port=5050):
    """在后端虚机上启动 UDP server。

    使用 nohup 后台启动 `/opt/network_tool/UDP_server.py`，将 stdout/stderr
    重定向到 `/tmp/udp_server_{port}.log`，便于后续通过日志识别接收到的消息。
    启动后会轮询端口监听状态，最多等待 60 秒。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: UDP server 监听端口。

    Raises:
        AssertionError: 后端服务在等待时间内未成功监听目标端口。
    """
    log_path = _udp_server_log_path(port)
    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(
        f"pkill -f 'UDP_server.py.*{port}' || true",
        check_rc=False,
    )
    ssh_vm.run(f": > {shlex.quote(log_path)}", check_rc=False)
    ssh_vm.run(
        f"nohup python -u {UDP_SERVER_SCRIPT} 0.0.0.0 {port} > {shlex.quote(log_path)} 2>&1 &",
        check_rc=False,
        wait_for_exit=False,
    )

    end_time = time.time() + 60
    while time.time() < end_time:
        result = ssh_vm.run(
            f"ss -lnup | grep ':{port} ' || netstat -lnup 2>/dev/null | grep ':{port} '",
            check_rc=False,
            return_rc=True,
        )
        if result["rc"] == 0 and f":{port}" in result["stdout"]:
            logger.info("UDP server 启动成功: %s -> port %s", _get_vm_name(vm_info), port)
            return
        time.sleep(5)

    raise AssertionError(
        f"虚机 {_get_vm_name(vm_info)} 上的 UDP server 端口 {port} 在 60 秒内未启动"
    )


def stop_udp_backend(ssh_vm, vm_info, port=5050):
    """停止后端虚机上的 UDP server 进程。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: UDP server 监听端口。
    """
    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(f"pkill -f 'UDP_server.py.*{port}'", check_rc=False)


def clear_udp_server_log(ssh_vm, vm_info, port=5050):
    """清空指定后端的 UDP server 日志，便于下一轮采样。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: UDP server 监听端口。
    """
    log_path = _udp_server_log_path(port)
    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(f": > {shlex.quote(log_path)}", check_rc=False)


def read_udp_server_log(ssh_vm, vm_info, port=5050):
    """读取后端 UDP server 日志内容。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: UDP server 监听端口。

    Returns:
        str: UDP server 日志内容（stdout），若日志不存在返回空字符串。
    """
    log_path = _udp_server_log_path(port)
    ssh_vm.connect(_get_vm_mfip(vm_info))
    result = ssh_vm.run(
        f"cat {shlex.quote(log_path)} 2>/dev/null || true",
        check_rc=False,
        return_rc=True,
    )
    if isinstance(result, dict):
        return result.get("stdout", "") or ""
    return result or ""


def send_udp_message(ssh_client, target_ip, target_port, message, timeout=5):
    """通过内联 Python 向负载均衡发送一条 UDP 消息。

    不依赖远程机器上预置的 UDP_client.py，使用内联 Python 代码直接发送 UDP 包，
    兼容 Python 2 和 Python 3，并通过 ``timeout`` 限制执行时长。

    Args:
        ssh_client: 已连接到客户端的 SSH 客户端（ssh_vm 或 ssh_host）。
        target_ip: 目标 IP 地址（VIP 或 FIP）。
        target_port: 目标端口。
        message: 待发送的消息内容。
        timeout: client 执行超时秒数，默认 5 秒。

    Returns:
        dict: SSH 命令执行结果，包含 ``rc``、``stdout``、``stderr``。
    """
    cmd = (
        f"timeout {timeout} python -c \"import socket, sys; "
        f"msg = '{message}'; "
        f"msg = msg.encode() if sys.version_info[0] >= 3 else msg; "
        f"s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
        f"s.sendto(msg, ('{target_ip}', {target_port}))\""
    )
    return ssh_client.run(cmd, check_rc=False, return_rc=True)


def collect_udp_recipients(ssh_vm, backends, port, messages):
    """采集 UDP 消息在各后端的接收命中分布。

    在消息发送结束后，统一读取每个 backend 的 UDP server 日志，
    比对发送内容，统计每条消息落在哪台 backend。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        backends: 后端虚机信息列表，每项需包含 ``name``、``mfip``。
        port: UDP server 监听端口。
        messages: 已发送的消息内容列表（按发送顺序）。

    Returns:
        dict: 形如 ``{message: backend_name}``，未匹配的消息映射为 ``None``。
    """
    backend_logs = {}
    for backend in backends:
        backend_logs[backend["name"]] = read_udp_server_log(ssh_vm, backend, port=port)

    hit_map = {}
    for message in messages:
        matched_backend = None
        for backend_name, log_text in backend_logs.items():
            if message in (log_text or ""):
                matched_backend = backend_name
                break
        hit_map[message] = matched_backend
    logger.info("UDP 消息命中分布: %s", hit_map)
    return hit_map



def wait_for_curl_match(ssh_client, curl_cmd, match_text, timeout_sec=60, interval_sec=5):
    """轮询执行 curl 命令，直到响应包含匹配文本或超时。

    适用于 ACL 规则同步、后端服务就绪等需要等待后端状态收敛的场景。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        curl_cmd: curl 命令字符串。
        match_text: 期望响应中包含的文本。
        timeout_sec: 最大等待时间（秒），默认 60 秒。
        interval_sec: 轮询间隔（秒），默认 5 秒。

    Returns:
        None

    Raises:
        AssertionError: 超时后仍未匹配到期望文本。
    """
    end_time = time.time() + timeout_sec
    last_result = None
    while time.time() < end_time:
        last_result = ssh_client.run(curl_cmd, check_rc=False, return_rc=True)
        stdout = (last_result.get("stdout") or "").strip()
        if last_result["rc"] == 0 and match_text in stdout:
            logger.info("curl 匹配成功: match_text=%s", match_text)
            return
        time.sleep(interval_sec)

    raise AssertionError(
        f"curl 命令在 {timeout_sec} 秒内未匹配到 '{match_text}'，"
        f"最后结果: rc={last_result.get('rc') if last_result else None}, "
        f"stdout={str(last_result.get('stdout', '')).strip()[:200] if last_result else ''}"
    )


def get_ssh_host_source_ip(ssh_host, target_ip):
    """识别 ssh_host 访问目标 IP 时实际使用的源 IP 候选集。

    Args:
        ssh_host: 已连接到测试环境物理机的 SSH 客户端。
        target_ip: 目标 IP 地址（通常是负载均衡的公网 IP）。

    Returns:
        list[str]: 源 IP 候选列表，优先返回 ``ip route get`` 推导值，
            其后追加 ``hostname -I`` / ``ip -4 addr`` 中发现的额外 IP。
    """
    import re as _re

    route_result = ssh_host.run(
        f"ip route get {shlex.quote(target_ip)} | grep -oP 'src \\K\\S+'",
        check_rc=False,
        return_rc=True,
    )
    route_src_ip = (route_result.get("stdout") or "").strip()
    if route_src_ip:
        logger.info("ssh_host 访问 %s 的源 IP: %s", target_ip, route_src_ip)
        return [route_src_ip]

    # 路由推导失败时，取 hostname -I 第一个公网IP作为兜底
    fallback = ssh_host.run("hostname -I", check_rc=False, return_rc=True)
    fallback_ip = (fallback.get("stdout") or "").strip().split()[0]
    if fallback_ip:
        logger.info("ssh_host 访问 %s 的源 IP(兜底): %s", target_ip, fallback_ip)
        return [fallback_ip]

    return []


def is_http_reachable(ssh_client, url, timeout_sec=60, interval_sec=5, connect_timeout=5):
    """轮询检查 HTTP 服务是否可达，返回布尔值。

    适用于公网IP绑定后的网络收敛等待，避免在测试层使用 time.sleep。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        url: 需要访问的 URL。
        timeout_sec: 最大等待时间（秒），默认 60 秒。
        interval_sec: 轮询间隔（秒），默认 5 秒。
        connect_timeout: curl 连接超时时间（秒），默认 5 秒。

    Returns:
        bool: 可达返回 True，超时返回 False。
    """
    curl_cmd = f"curl -s --connect-timeout {connect_timeout} {shlex.quote(url)}"
    end_time = time.time() + timeout_sec
    while time.time() < end_time:
        result = ssh_client.run(curl_cmd, check_rc=False, return_rc=True)
        if result["rc"] == 0 and result["stdout"].strip():
            return True
        time.sleep(interval_sec)
    return False


def verify_curl_backend(ssh_vm, requester_mfip, lb_vip, port, backend_markers,
                        expected_description, expected_backend=None, excluded_backend=None,
                        max_retries=8, retry_interval=0.8):
    """执行curl并验证结果中是否包含/排除指定后端，支持重试轮询。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        requester_mfip: 请求者虚机的MFIP。
        lb_vip: 负载均衡VIP。
        port: 访问端口。
        backend_markers: 后端标识字典。
        expected_description: 验证场景描述。
        expected_backend: 期望包含的后端名称，默认None。
        excluded_backend: 期望排除的后端名称，默认None。
        max_retries: 最大重试次数，默认8。
        retry_interval: 重试间隔秒数，默认0.8。

    Returns:
        list[str]: 响应列表。
    """
    for attempt in range(max_retries + 1):
        ssh_vm.connect(requester_mfip)
        responses = collect_lb_http_responses(
            ssh_vm, f"http://{lb_vip}:{port}/index.html", count=15
        )
        ok = True
        if excluded_backend:
            marker = backend_markers[excluded_backend]
            if any(marker in r for r in responses):
                ok = False
        if expected_backend:
            marker = backend_markers[expected_backend]
            if not any(marker in r for r in responses):
                ok = False
        if ok:
            return responses
        if attempt < max_retries:
            time.sleep(retry_interval)

    # 最后一次完整断言，产生清晰的失败信息
    ssh_vm.connect(requester_mfip)
    responses = collect_lb_http_responses(
        ssh_vm, f"http://{lb_vip}:{port}/index.html", count=15
    )
    if excluded_backend:
        marker = backend_markers[excluded_backend]
        for r in responses:
            assert marker not in r, (
                f"{expected_description}: 不应包含 {excluded_backend}"
            )
    if expected_backend:
        marker = backend_markers[expected_backend]
        found = any(marker in r for r in responses)
        assert found, f"{expected_description}: 应包含 {expected_backend}"
    return responses


def collect_and_assert_with_retry(ssh_vm, requester_mfip, lb_vip, port, backend_markers,
                                   policy, scene_name, weights=None, count=15, tolerance=0.15,
                                   max_retries=5, retry_interval=1.0):
    """采集HTTP响应并按算法策略断言，支持重试轮询（用于权重/算法变更后的验证）。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        requester_mfip: 请求者虚机的MFIP。
        lb_vip: 负载均衡VIP。
        port: 访问端口。
        backend_markers: 后端标识字典。
        policy: 算法策略名称。
        scene_name: 场景描述。
        weights: 权重字典，默认None。
        count: curl请求次数，默认15。
        tolerance: 命中比例允许偏差，默认0.15。
        max_retries: 断言失败时最大重试次数，默认5。
        retry_interval: 重试间隔秒数，默认1.0。

    Returns:
        list[str]: 响应列表。
    """
    for attempt in range(max_retries + 1):
        ssh_vm.connect(requester_mfip)
        responses = collect_lb_http_responses(
            ssh_vm, f"http://{lb_vip}:{port}/index.html", count=count
        )
        try:
            assert_lb_algorithm(
                policy,
                responses,
                backend_markers,
                scene_name,
                weights=weights,
                tolerance=tolerance,
            )
            return responses
        except AssertionError:
            if attempt < max_retries:
                time.sleep(retry_interval)
            else:
                raise


def verify_lb_unreachable(ssh_vm, requester_mfip, lb_vip, port,
                          max_retries=5, retry_interval=3):
    """验证负载均衡VIP在监听器删除后不可达，支持重试轮询。

    LB 删除后连接可能短暂保持，需轮询确认真正不可达。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        requester_mfip: 请求者虚机的MFIP。
        lb_vip: 负载均衡VIP。
        port: 访问端口。
        max_retries: 最大重试次数，默认5。
        retry_interval: 重试间隔秒数，默认3。

    Returns:
        dict: 最后一次 curl 的结果（含 rc, stdout）。
    """
    ssh_vm.connect(requester_mfip)
    for attempt in range(max_retries + 1):
        result = ssh_vm.run(
            f"curl -s --connect-timeout 10 http://{lb_vip}:{port}/index.html",
            return_rc=True,
        )
        if result["rc"] != 0:
            return result
        if attempt < max_retries:
            time.sleep(retry_interval)
    return result
