"""
LLM 调用客户端封装。

统一对接 DeepSeek / DashScope 等 OpenAI 兼容 API，支持超时与基础用量统计。
"""

import os
from dataclasses import dataclass


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
    },
    "dashscope": {
        "env": "DASHSCOPE_API_KEY",
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "default_model": "glm-5",
        "timeout": 600,
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
        provider: 模型提供商，支持 deepseek / dashscope。
        model: 模型名称；默认使用 provider 默认模型。
        timeout: 超时秒数；默认使用 provider 配置。

    Returns:
        LLMResponse 对象。

    Raises:
        RuntimeError: 未配置 API Key 或调用失败。
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("未安装 openai SDK，请先执行 `pip install openai`") from exc

    config = PROVIDER_CONFIG.get(provider, {})
    api_key, base_url, resolved_model = _resolve_provider_config(provider, model)
    if not api_key:
        env_name = config.get("env", f"{provider.upper()}_API_KEY")
        raise RuntimeError(f"未检测到 {env_name} 环境变量")

    client = OpenAI(api_key=api_key, base_url=base_url)
    timeout = timeout or config.get("timeout", 600)

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
