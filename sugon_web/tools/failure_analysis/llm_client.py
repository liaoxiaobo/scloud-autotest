"""
LLM 调用客户端封装。

统一对接 DeepSeek / DashScope 等 OpenAI 兼容 API，以及 Anthropic 兼容 API，
支持超时、SSL 验证控制与基础用量统计。
"""

import os
from dataclasses import dataclass

import httpx


@dataclass
class LLMResponse:
    """LLM 响应封装。"""

    content: str
    model: str = ""
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0


PROVIDER_CONFIG = {
    "deepseek": {
        "env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-pro",
        "timeout": 600,
        "protocol": "openai",
    },
    "dashscope": {
        "env": "DASHSCOPE_API_KEY",
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "default_model": "glm-5",
        "timeout": 600,
        "protocol": "openai",
    },
    "sugoncloud": {
        "env": "SUGON_API_KEY",
        "base_url": "https://172.22.6.9:8765",
        "default_model": "k3",
        "timeout": 600,
        "protocol": "anthropic",
        "verify_ssl": False,
    },
}


def _resolve_provider_config(provider: str, model: str) -> tuple[str, str, str]:
    """解析 provider 配置，返回 (api_key, base_url, model)。"""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"不支持的 provider: {provider}")
    api_key = os.environ.get(config["env"])
    resolved_model = model or config["default_model"]
    return api_key or "", config["base_url"], resolved_model


def _partition_messages(
    messages: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    """从消息列表中提取 system 内容与普通消息。"""
    system_content = ""
    chat_messages = []
    for message in messages:
        if message.get("role") == "system":
            system_content = message.get("content", "")
        else:
            chat_messages.append(message)
    return system_content, chat_messages


def _call_openai(
    messages: list[dict[str, str]],
    provider: str,
    model: str,
    timeout: int,
    verify_ssl: bool = True,
) -> LLMResponse:
    """调用 OpenAI 兼容 API。"""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 openai SDK，请先执行 `pip install openai`") from exc

    config = PROVIDER_CONFIG.get(provider, {})
    api_key, base_url, resolved_model = _resolve_provider_config(provider, model)
    if not api_key:
        env_name = config.get("env", f"{provider.upper()}_API_KEY")
        raise RuntimeError(f"未检测到 {env_name} 环境变量")

    client_kwargs: dict[str, object] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if not verify_ssl:
        client_kwargs["http_client"] = httpx.Client(verify=False)
    client = OpenAI(**client_kwargs)

    try:
        response = client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            timeout=timeout,
        )
    except Exception as exc:
        raise RuntimeError(f"{provider} 调用失败: {exc}") from exc

    choice = response.choices[0].message
    usage = response.usage
    return LLMResponse(
        content=choice.content or "",
        model=response.model or resolved_model,
        usage_prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        usage_completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
    )


def _call_anthropic(
    messages: list[dict[str, str]],
    provider: str,
    model: str,
    timeout: int,
    verify_ssl: bool = True,
) -> LLMResponse:
    """调用 Anthropic 兼容 API。"""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "未安装 anthropic SDK，请先执行 `pip install anthropic`"
        ) from exc

    config = PROVIDER_CONFIG.get(provider, {})
    api_key, base_url, resolved_model = _resolve_provider_config(provider, model)
    if not api_key:
        env_name = config.get("env", f"{provider.upper()}_API_KEY")
        raise RuntimeError(f"未检测到 {env_name} 环境变量")

    system_content, chat_messages = _partition_messages(messages)

    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url,
        http_client=httpx.Client(verify=verify_ssl),
    )

    try:
        response = client.messages.create(
            model=resolved_model,
            messages=chat_messages,
            system=system_content,
            max_tokens=4096,
            timeout=timeout,
        )
    except Exception as exc:
        raise RuntimeError(f"{provider} 调用失败: {exc}") from exc

    content = ""
    if response.content:
        for block in response.content:
            block_text = getattr(block, "text", None)
            if block_text:
                content = block_text
                break
    usage = response.usage
    return LLMResponse(
        content=content,
        model=response.model or resolved_model,
        usage_prompt_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
        usage_completion_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
    )


def call_llm(
    messages: list[dict[str, str]],
    provider: str = "deepseek",
    model: str = "",
    timeout: int | None = None,
) -> LLMResponse:
    """调用 LLM 生成回复。

    Args:
        messages: OpenAI 格式消息列表，例如
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        provider: 模型提供商，支持 deepseek / dashscope / sugoncloud。
        model: 模型名称；默认使用 provider 默认模型。
        timeout: 超时秒数；默认使用 provider 配置。

    Returns:
        LLMResponse 对象。

    Raises:
        RuntimeError: 未配置 API Key 或调用失败。
    """
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"不支持的 provider: {provider}")

    resolved_timeout = timeout or config.get("timeout", 600)
    protocol = config.get("protocol", "openai")
    verify_ssl = config.get("verify_ssl", True)

    if protocol == "anthropic":
        return _call_anthropic(messages, provider, model, resolved_timeout, verify_ssl)
    return _call_openai(messages, provider, model, resolved_timeout, verify_ssl)
