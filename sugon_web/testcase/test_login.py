import time
import allure

@allure.title("用户登录失败场景-用户名输入错误")
def test_login_user_error(login_page):
    # 步骤1：输入错误账号密码并提交
    login_page.login("wrong_user", "wrong_pwd")

    # 步骤2：结果断言
    login_page.assert_popup_error("用户名/密码错误")


@allure.title("用户登录失败场景-密码输入错误，且错误次数超过默认限制")
def test_login_pwd_error(login_page):
    for attempt in range(1, 8):
        login_page.login("admin", f"wrong_pwd_{attempt}")
        if attempt < 5:
            login_page.assert_popup_error(f"10分钟内，用户名/密码连续错误5次将被锁定1分钟，已错误{attempt}次")
        elif attempt == 5:
            login_page.assert_popup_error("用户名/密码错误次数达到上限，锁定1分钟")
            time.sleep(50)
        elif attempt == 6:
            login_page.assert_popup_error("用户名/密码错误次数达到上限，锁定1分钟")
            time.sleep(65)
        else:
            login_page.assert_popup_error(f"10分钟内，用户名/密码连续错误5次将被锁定1分钟，已错误1次")

