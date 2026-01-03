from sugon_web.common.base import BasePage

class LoginPage(BasePage):

    def __init__(self, page):
        super().__init__(page)

    def login(self, name: str, pwd: str):
        """执行登录操作
        
        Args:
            name: 登录用户名
            pwd: 登录密码
        """
        self._input_username.fill(name)
        self._input_password.fill(pwd)
        self._btn_login.click()

    @property
    def _input_username(self):
        """登录页面元素:用户名输入框"""
        return self.get_by_placeholder("请输入登录账号")

    @property
    def _input_password(self):
        """登录页面元素:密码输入框"""
        return self.get_by_placeholder("请输入登录密码")

    @property
    def _btn_login(self):
        """登录页面元素:登录按钮"""
        return self.get_by_text("登 录")

    def logout(self):
        """执行登出操作"""
        self.get_by_role("definition").filter(has_text="admin").click()
        self.get_by_text("退出系统").click()
