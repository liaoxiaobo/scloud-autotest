import os
from openai import OpenAI

try:
    client = OpenAI(
        # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        # 各地域的base_url不同
        base_url="https://coding.dashscope.aliyuncs.com/v1",
    )

    completion = client.chat.completions.create(
        model="glm-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "你是谁"},
        ],
    )
    print(completion.choices[0].message.content)
    # 如需查看完整响应，请取消下列注释
    print(completion.model_dump_json())
except Exception as e:
    print(f"错误信息：{e}")
    print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")