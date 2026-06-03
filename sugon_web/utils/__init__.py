"""sugon_web.utils —— 基础设施工具包。

按职责拆分为以下子模块，新代码请按需导入：
- data:    随机数据生成、YAML 加载、Jinja2 渲染
- retry:   重试检查辅助
- logger:  日志与 Allure 步骤桥接

旧的全局导入（from utils.util import *）仍通过 util.py 的转发保持兼容，
但建议逐步迁移到新的子模块路径。
"""
