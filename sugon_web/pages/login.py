from sugon_web.common.base import BasePage

class LoginPage(BasePage):

    def __init__(self, page, env):
        super().__init__(page, env, auto_login=False)  # 登录页面跳过自动登录

    def login(self, name: str, pwd: str):
        """执行登录操作
        
        Args:
            name: 登录用户名
            pwd: 登录密码
        """
        self._input_username.fill(name)
        self._input_password.fill(pwd)
        self._btn_login.click()

