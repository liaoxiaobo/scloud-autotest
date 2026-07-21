import os
from openai import OpenAI

try:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": "你是一位自动化测试专家，擅长分析测试失败根因。"},
            {"role": "user", "content": "你支持根据失败截图分析吗"},
        ],
        timeout=60,
    )
    print(response.choices[0].message.content)
    # 如需查看完整响应，请取消下列注释
    # print(response.model_dump_json())
except Exception as e:
    print(f"错误信息：{e}")
    print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")