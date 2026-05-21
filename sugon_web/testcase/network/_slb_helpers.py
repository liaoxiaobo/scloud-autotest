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

    该函数按端口匹配 `python3 -m http.server` 进程。
    若目标进程不存在，不视为错误。

    Args:
        ssh_vm: 用于连接后端虚机的 SSH 客户端。
        vm_info: 虚机信息字典或可直接连接的地址字符串。
        port: HTTP 服务监听端口。

    Returns:
        None.
    """
    ssh_vm.connect(_get_vm_mfip(vm_info))
    ssh_vm.run(f"pkill -f 'python3 -m http.server {port}'", check_rc=False)


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
    ssh_client, target_url, count=30, interval_sec=1, connect_timeout=10
):
    """连续 curl 指定 URL，并返回原始响应列表。

    采样结果保留响应顺序，适合后续做轮询、加权轮询等分布断言。

    Args:
        ssh_client: 用于执行远端命令的 SSH 客户端。
        target_url: 需要访问的负载均衡 URL。
        count: 采样次数。
        interval_sec: 两次采样之间的等待秒数。
        connect_timeout: curl 连接超时时间，单位为秒。

    Returns:
        list[str]: 按采样顺序保存的 HTTP 响应文本列表。

    使用说明:
        当测试需要验证调度分布时，优先使用本函数保留完整响应序列，
        再交给 `assert_lb_algorithm()` 做策略断言。
    """
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


def _normalize_lb_responses(responses, backend_markers):
    """将原始响应映射为统一的后端标识。

    Args:
        responses: 负载均衡原始响应列表。
        backend_markers: `后端标识 -> 页面内容标识` 的映射。

    Returns:
        一个二元组 `(normalized_hits, unexpected_responses)`：

        - `normalized_hits` 是已识别的后端标识列表。
        - `unexpected_responses` 是无法映射到任何后端的响应内容。
    """
    marker_to_backend = {
        marker.strip(): backend_key for backend_key, marker in backend_markers.items()
    }
    normalized_hits = []
    unexpected_responses = []

    for response in responses:
        normalized_response = response.strip()
        backend_key = marker_to_backend.get(normalized_response)
        if backend_key is None:
            unexpected_responses.append(normalized_response)
            continue
        normalized_hits.append(backend_key)

    return normalized_hits, unexpected_responses


def _build_lb_hit_stats(responses, backend_markers):
    """构造统一的负载均衡命中统计结果。

    Args:
        responses: 负载均衡原始响应列表。
        backend_markers: `后端标识 -> 页面内容标识` 的映射。

    Returns:
        dict: 标准化统计结果，供不同调度算法断言共享，主要字段包括：

        - `total`：成功识别的响应总数。
        - `backend_keys`：参与断言的后端标识列表。
        - `counts`：每个后端的命中次数。
        - `ratios`：每个后端的命中比例。
        - `unexpected_responses`：无法识别的响应内容。
        - `missing_backends`：完全未命中的后端列表。
        - `raw_responses`：去除首尾空白后的原始响应列表。
    """
    backend_keys = list(backend_markers)
    normalized_hits, unexpected_responses = _normalize_lb_responses(responses, backend_markers)
    counts = Counter(normalized_hits)
    total = len(normalized_hits)

    stats = {
        "total": total,
        "backend_keys": backend_keys,
        "counts": {backend_key: counts.get(backend_key, 0) for backend_key in backend_keys},
        "ratios": {
            backend_key: (counts.get(backend_key, 0) / total if total else 0)
            for backend_key in backend_keys
        },
        "unexpected_responses": unexpected_responses,
        "missing_backends": [backend_key for backend_key in backend_keys if counts.get(backend_key, 0) == 0],
        "raw_responses": [response.strip() for response in responses],
    }
    logger.info("SLB命中统计: %s", stats)
    return stats


def _assert_common_lb_expectations(stats, scene_name):
    """校验所有调度算法都应满足的公共约束。

    Args:
        stats: 由 `_build_lb_hit_stats()` 生成的标准化命中统计结果。
        scene_name: 当前断言场景名称，用于拼接错误信息。

    Raises:
        AssertionError: 当未采集到有效响应、存在未知响应，
            或有后端完全未命中时抛出。

    这些约束与具体调度策略无关，只要求：

    - 至少采集到一个有效响应。
    - 不存在未知响应内容。
    - 所有预期后端至少被命中一次。
    """
    assert stats["total"] > 0, f"{scene_name} 未采集到任何有效响应，原始结果: {stats['raw_responses']}"
    assert not stats["unexpected_responses"], (
        f"{scene_name} 返回了非预期内容: {stats['unexpected_responses']}, "
        f"全量结果: {stats['raw_responses']}"
    )
    assert not stats["missing_backends"], (
        f"{scene_name} 存在未命中的后端: {stats['missing_backends']}, "
        f"统计结果: {stats['counts']}"
    )


def _assert_round_robin(stats, scene_name, tolerance):
    """断言普通轮询分布接近均分。

    Args:
        stats: 由 `_build_lb_hit_stats()` 生成的标准化命中统计结果。
        scene_name: 当前断言场景名称，用于拼接错误信息。
        tolerance: 每个后端命中比例相对理论均值的允许偏差。

    Raises:
        AssertionError: 当公共约束不满足，或任一后端命中比例偏离
            理论均值超过允许范围时抛出。
    """
    _assert_common_lb_expectations(stats, scene_name)

    backend_count = len(stats["backend_keys"])
    expected_ratio = 1 / backend_count
    for backend_key in stats["backend_keys"]:
        actual_ratio = stats["ratios"][backend_key]
        deviation = abs(actual_ratio - expected_ratio)
        assert deviation <= tolerance, (
            f"{scene_name} 轮询分布异常，后端 '{backend_key}' 期望比例约为 {expected_ratio:.4f}，"
            f"实际比例为 {actual_ratio:.4f}，允许偏差 {tolerance:.4f}，"
            f"统计结果: counts={stats['counts']}, total={stats['total']}"
        )


def _assert_weighted_round_robin(stats, scene_name, weights, tolerance):
    """断言加权轮询分布接近期望权重比。

    Args:
        stats: 由 `_build_lb_hit_stats()` 生成的标准化命中统计结果。
        scene_name: 当前断言场景名称，用于拼接错误信息。
        weights: `后端标识 -> 权重值` 的映射。
        tolerance: 每个后端命中比例相对理论权重占比的允许偏差。

    Raises:
        ValueError: 当 `weights` 为空、缺少后端配置，或总权重不大于 0 时抛出。
        AssertionError: 当公共约束不满足，或任一后端命中比例偏离
            理论权重占比超过允许范围时抛出。

    使用说明:
        `weights` 必须覆盖 `stats["backend_keys"]` 中的所有后端，
        否则无法计算期望比例。
    """
    _assert_common_lb_expectations(stats, scene_name)

    if not weights:
        raise ValueError("weighted_round_robin 断言要求提供 weights 参数")

    missing_weights = [backend_key for backend_key in stats["backend_keys"] if backend_key not in weights]
    if missing_weights:
        raise ValueError(f"weights 缺少后端配置: {missing_weights}")

    total_weight = sum(weights[backend_key] for backend_key in stats["backend_keys"])
    if total_weight <= 0:
        raise ValueError(f"weights 总和必须大于 0，当前: {weights}")

    for backend_key in stats["backend_keys"]:
        expected_ratio = weights[backend_key] / total_weight
        actual_ratio = stats["ratios"][backend_key]
        deviation = abs(actual_ratio - expected_ratio)
        assert deviation <= tolerance, (
            f"{scene_name} 加权轮询分布异常，后端 '{backend_key}' 权重为 {weights[backend_key]}，"
            f"期望比例约为 {expected_ratio:.4f}，实际比例为 {actual_ratio:.4f}，"
            f"允许偏差 {tolerance:.4f}，统计结果: counts={stats['counts']}, total={stats['total']}"
        )


def assert_lb_algorithm(policy, responses, backend_markers, scene_name, tolerance=0.15, weights=None):
    """按指定调度算法校验负载均衡命中分布。

    Args:
        policy: 调度算法名称，目前支持 `round_robin` 和
            `weighted_round_robin`。
        responses: 原始响应列表。
        backend_markers: `后端标识 -> 页面内容标识` 的映射。
        scene_name: 用于断言报错的场景名称。
        tolerance: 命中比例允许偏差。
        weights: 加权轮询时使用的权重映射。

    Returns:
        标准化统计结果字典，便于测试在断言后继续复用统计信息。

    Raises:
        ValueError: 当 `policy` 不受支持，或加权轮询缺少必要配置时抛出。
        AssertionError: 当负载均衡命中分布不符合预期时抛出。

    使用说明:
        - 普通轮询场景传入 `policy="round_robin"`。
        - 加权轮询场景传入 `policy="weighted_round_robin"`，并同时提供
          `weights` 参数。
        - 返回值可用于后续日志打印或额外断言，无需重复统计。
    """
    stats = _build_lb_hit_stats(responses, backend_markers)

    if policy == "round_robin":
        _assert_round_robin(stats, scene_name, tolerance=tolerance)
    elif policy == "weighted_round_robin":
        _assert_weighted_round_robin(stats, scene_name, weights=weights, tolerance=tolerance)
    else:
        raise ValueError(f"不支持的调度算法断言: {policy}")

    return stats


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


def assert_udp_source_ip_sticky(hit_map, scene_name, expected_count=None):
    """断言 UDP 消息全部命中同一后端（源 IP 算法效果）。

    Args:
        hit_map: ``collect_udp_recipients()`` 返回的命中字典。
        scene_name: 用于断言报错的场景名称。
        expected_count: 期望命中的消息数量，默认与 hit_map 长度一致。

    Returns:
        str: 实际命中的 backend 名称。

    Raises:
        AssertionError: 存在未命中的消息，或命中分布到多台后端。
    """
    if expected_count is None:
        expected_count = len(hit_map)
    missing = [msg for msg, backend in hit_map.items() if backend is None]
    assert not missing, (
        f"{scene_name} 存在未命中任何后端的消息: {missing}，完整命中分布: {hit_map}"
    )
    hit_backends = {backend for backend in hit_map.values() if backend is not None}
    assert len(hit_backends) == 1, (
        f"{scene_name} 源 IP 算法命中多台后端: {hit_backends}，完整命中分布: {hit_map}"
    )
    assert len(hit_map) >= expected_count, (
        f"{scene_name} 命中消息数 {len(hit_map)} 少于期望值 {expected_count}"
    )
    return next(iter(hit_backends))


def assert_udp_all_rejected(hit_map, scene_name):
    """断言所有 UDP 消息均未命中任何后端（被访问控制拒绝）。

    Args:
        hit_map: ``collect_udp_recipients()`` 返回的命中字典。
        scene_name: 用于断言报错的场景名称。

    Raises:
        AssertionError: 存在被后端接收的消息。
    """
    received = {msg: backend for msg, backend in hit_map.items() if backend is not None}
    assert not received, (
        f"{scene_name} 期望全部被拒绝，但以下消息被后端接收: {received}"
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

    candidate_ips = []

    route_result = ssh_host.run(
        f"ip route get {shlex.quote(target_ip)} | grep -oP 'src \\K\\S+'",
        check_rc=False,
        return_rc=True,
    )
    route_src_ip = (route_result.get("stdout") or "").strip()
    if route_src_ip:
        candidate_ips.append(route_src_ip)

    fallback_result = ssh_host.run(
        "hostname -I; ip -4 addr show scope global | awk '{print $2}'",
        check_rc=False,
        return_rc=True,
    )
    fallback_output = fallback_result.get("stdout") or ""
    for ip in _re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", fallback_output):
        if ip and ip not in candidate_ips:
            candidate_ips.append(ip)

    logger.info("ssh_host 访问 %s 的源 IP 候选: %s", target_ip, candidate_ips)
    return candidate_ips
