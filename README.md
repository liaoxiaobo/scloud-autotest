# Sugon Web 自动化测试框架

基于 Playwright + Pytest 的 Web 自动化测试框架，专为曙光云平台前端功能测试设计。

## 🚀 项目特性

- **测试技术栈**：基于 Playwright + Pytest，支持多浏览器并行测试
- **页面对象模式**：采用 POM 设计模式，提高代码复用性和维护性
- **内置服务导航**：自动识别多层级菜单结构，支持跨服务页面的快速切换
- **完善的断言体系**：内置丰富的断言方法，覆盖常见测试场景
- **详细测试报告**：集成 Allure 报告，支持失败截图和详细日志
- **灵活配置管理**：支持多环境配置和命令行参数定制
- **分布式执行**：支持 pytest-xdist 并行测试，提高执行效率
- **CI/CD集成**：提供完整的容器化部署方案，支持 Jenkins CI/CD
- **自动失败重试**：集成 pytest-rerunfailures，提高测试稳定性

## 📁 项目结构

```
sugon_web/
├── common/                 # 公共模块
│   ├── base.py            # 基础页面类
│   └── playwright.py      # Playwright 封装
├── pages/                 # 页面对象
│   ├── login.py          # 登录页面
│   └── evs.py            # 云硬盘页面
├── testcase/             # 测试用例
│   ├── conftest.py       # pytest 配置和 fixtures
│   ├── test_login.py     # 登录测试
│   └── test_evs.py       # 云硬盘测试
├── utils/                # 工具模块
│   ├── logger.py         # 日志工具
│   └── util.py           # 通用工具函数
└── requirements.txt      # 项目依赖
```

## 🛠️ 环境准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装浏览器

```bash
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

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 172.22.1.170 | 测试环境管理VIP |
| `--username` | admin | 登录用户名 |
| `--password` | keystone_sugon | 登录密码 |
| `--browser-type` | chromium | 浏览器类型 (chromium/firefox/webkit) |
| `--headless` | false | 是否无头模式运行 |

## 📝 编写测试用例

### 1. 创建页面对象

```python
from sugon_web.common.base import BasePage, submenu

class MyServicePage(BasePage):
    def __init__(self, page, env):
        super().__init__(page, env)
    
    @submenu("服务列表")
    def create_resource(self, name, **kwargs):
        """创建资源"""
        self.btn_create.click()
        self.input_name.fill(name)
        self.dialog_confirm.click()
    
    @property
    def input_name(self):
        return self.get_by_placeholder("请输入名称")
```

### 2. 编写测试用例

```python
import pytest
from sugon_web.utils.util import random_data

class TestMyService:
    def test_create_resource(self, my_service_page):
        """资源创建测试"""
        name = random_data()
        my_service_page.create_resource(name)
        my_service_page.assert_popup_success()
        my_service_page.assert_list_contain(name)
```

### 3. 配置 Fixture

```python
@pytest.fixture(scope="module")
def my_service_page(page, env):
    """初始化服务页面"""
    page = MyServicePage(page, env)
    page.goto_service('我的服务')
    return page
```

## 🔧 核心功能详解

### 智能导航系统

框架内置服务导航映射，支持自动识别多层级菜单：

```python
# 三层结构：资源中心 -> 计算 -> 云服务器
page.goto_service('云服务器')

# 两层结构：基础设施 -> 区域资源
page.goto_service('区域资源')
```

### 装饰器模式

使用 `@submenu` 装饰器确保方法在正确的子菜单页面执行：

```python
@submenu("云硬盘")
def evs_create(self, name):
    """自动切换到云硬盘子菜单后执行创建操作"""
    pass
```

### 断言方法

框架提供丰富的断言方法：

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

### 数据生成

使用 `random_data()` 生成测试数据：

```python
from sugon_web.utils.util import random_data

name = random_data()                    # 生成随机字符串
phone = random_data('phone')            # 生成手机号
email = random_data('email')            # 生成邮箱
cidr = random_data('cidr', version=4)   # 生成IPv4网段
```

## 📊 测试报告

### Allure 报告

```bash
# 生成报告数据
pytest --alluredir=reports

# 启动报告服务
allure serve reports
```

### 失败截图

测试失败时自动生成截图，保存到 `screenshots/` 目录并添加到 Allure 报告中。

## 🎨 最佳实践

### 1. 页面对象设计

- 各个页面对象继承 `base.py` 里的 `BasePage` 类
- 所有页面元素默认定义为私有属性，且优先复用`BasePage`中已定义的公共元素，避免在子类中重复定义
- 复杂的元素操作封装为私有方法（如 `_select_cluster()`）
- 只有业务操作可封装为公有方法，命名采用 `服务_操作` 格式（如 `evs_create`、`evs_delete`）
- 公有方法必须写docstrings，方便理解代码的用途和用法
- 使用 `@submenu` 装饰器确保公有方法在正确的子菜单页面执行


### 2. 测试用例组织

- 按服务模块组织测试类
- 测试方法命名清晰描述测试场景
- 使用框架内置的断言方法
- 使用参数化测试覆盖多种场景


### 3. 数据管理

- 使用 `random_data()` 生成唯一测试数据
- 合理使用 fixture 管理测试数据，比如使用 fixture 的 yield 机制管理测试用例的前置资源创建/清理等

### 4. 错误处理

- 充分利用框架的日志功能
- 测试失败时自动生成截图并添加到 Allure 报告
- 使用 `close_dialog_if_exists()` 处理意外弹窗

### 5. 元素定位

- 优先使用Playwright的语义化定位方法（`get_by_role`、`get_by_placeholder`）
- 使用 `click_dropdown_option()` 处理下拉菜单操作

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