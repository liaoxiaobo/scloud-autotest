"""通用断言辅助函数。

纯函数形式的断言工具，不依赖 page 对象，
适用于 helper 层和测试步骤中的独立校验。
"""

from collections import Counter

from sugon_web.utils.logger import logger


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
