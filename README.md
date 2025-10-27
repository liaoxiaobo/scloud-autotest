# Sugon Web 自动化测试框架

## 🚀 项目特性

- **测试技术栈**：基于 Playwright + Pytest 开发的Web自动化测试框架
- **页面对象模式**：采用 POM 设计模式，提高代码复用性和维护性
- **灵活配置管理**：支持多浏览器、多环境配置和命令行参数定制
- **详细测试报告**：集成 Allure 报告，支持失败截图和详细日志
- **内置服务导航**：自动识别多层级菜单结构，支持跨服务页面的快速切换
- **完善的断言体系**：内置丰富的断言方法，覆盖常见测试场景
- **分布式执行**：支持 pytest-xdist 并行测试，提高执行效率
- **CI/CD集成**：提供完整的容器化部署方案，支持 Jenkins CI/CD

## 📁 项目结构
```
sugon_web/
├── conftest.py
├── pytest.ini
├── common/
│   ├── base.py
│   └── playwright.py
├── pages/
│   ├── ecs.py
│   ├── evs.py
│   └── login.py
├── testcase/
│   ├── conftest.py
│   ├── test_ecs.py
│   ├── test_evs.py
│   ├── test_login.py
│   └── test_data/
│       └── test_data.yaml
└── utils/
    ├── logger.py
    └── util.py
```

## 项目目录说明

### 1. `common/`
- 公共模块：
  - `base.py`：页面基类，封装公共页面元素和操作方法。
  - `playwright.py`：封装底层Playwright API，统一提供元素定位器和操作方法，简化上层调用。

### 2. `pages/`
- 页面对象模型（POM）：将页面元素和操作封装在类中（如login.py），测试用例只调用方法

### 3. `testcase/`
- 测试用例：如 test_login.py （登录测试）、 test_ecs.py （云服务器测试）等
- 子目录 `test_data/` 存放测试数据文件（如 `test_data.yaml`）。

### 4. `utils/`
- 工具模块：如 logger.py （日志工具）、 util.py （通用工具函数）。

### 5. `conftest.py` 和 `pytest.ini`
- 全局 Fixture 定义和Pytest 配置文件。

## 🛠️ 环境准备

```bash
pip install -r requirements.txt

playwright install
```

## 🎯 快速开始

### 运行测试

```bash
# 运行所有测试
pytest sugon_web/testcase/

# 运行ecs模块测试
pytest -k "ecs" sugon_web/testcase/

# 指定环境和浏览器
pytest sugon_web/testcase/ --host=172.22.1.170 --browser-type=chromium

# 生成 Allure 报告
pytest sugon_web/testcase/ --alluredir=allure-result
allure serve allure-result
```

### 命令行参数

| 参数 | 示例值            | 说明 |
|------|----------------|------|
| `--host` | 172.22.1.170   | 测试环境管理VIP |
| `--username` | admin          | 登录用户名 |
| `--password` | keystone_sugon | 登录密码 |
| `--browser-type` | chromium       | 浏览器类型 (chromium/firefox/webkit) |
| `--headless` | false          | 是否无头模式运行 |


## 🔧 核心功能详解

### 智能导航系统

框架内置服务导航映射，支持自动识别多层级菜单：

```python
# 三层结构：资源中心 -> 计算 -> 云服务器
page.goto_service('云服务器')

# 两层结构：基础设施 -> 存储设施
page.goto_service('存储设施')
```

### 装饰器模式

使用 `@submenu` 装饰器确保方法在正确的子菜单页面执行：

```python
@submenu("弹性云服务器")
def ecs_create(self, name):
    """自动进入到'弹性云服务器'子菜单页面"""
    pass
```

### 断言体系

框架提供公共的断言方法：

```python
# 弹窗断言
page.assert_popup_success()
page.assert_popup_error("错误信息")

# 资源状态断言
page.assert_status(name, status="可用")

# 列表断言
page.assert_list_contain(keyword)
page.assert_deleted(name)
```

### 测试数据生成

使用 `random_data()` 随机生成测试数据，多用于资源名称：

```python
from sugon_web.utils.util import random_data

name = random_data()                    # 生成随机字符串
phone = random_data('phone')            # 生成手机号
email = random_data('email')            # 生成邮箱
cidr = random_data('cidr', version=4)   # 生成IPv4网段
```

## 🎨 最佳实践

### 1. 页面对象设计

- 页面对象继承 `base.py` 里的 `BasePage` 类
- 所有页面元素默认定义为私有属性，且优先复用`BasePage`中已定义的公共元素，避免在子类中重复定义
- 复杂的元素操作封装为私有方法（如 `_select_cluster()`）
- 只有业务操作可封装为公有方法，命名采用 `服务_操作` 格式（如 `evs_create`、`evs_delete`）
- 公有方法必须写docstrings，方便理解代码的用途和用法

### 2. 测试用例组织

- 添加 allure.title 描述测试用例，命名采用 `服务-xx功能验证` 格式（如 `云硬盘-创建功能验证`）
- 添加 allure.step，将测试步骤结构化，便于在报告中查看

### 3. 数据管理
- 使用 `random_data()` 生成唯一的测试数据
- 合理使用 fixture 管理测试数据，比如使用 fixture 的 yield 机制管理测试用例的前置资源创建/清理等

### 4. 元素定位
- 优先使用Playwright的语义化定位方法（`get_by_role`、`get_by_placeholder`）

## 🤝 贡献指南

1. Fork 项目到个人仓库
2. 创建功能分支：`git checkout -b feature/new-service`
3. 提交代码：`git commit -m 'Add new service tests'`
4. 推送分支：`git push origin feature/new-service`
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 添加必要的注释和文档字符串
- 确保新增测试用例通过
- 更新相关文档

---

**Happy Testing! 🎉**