import json
import os
import urllib.request
from sugon_web.utils.logger import logger


class FeishuNotifier:
    """飞书消息通知器。测试完成后发送结果到飞书群。"""

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID")
        self.app_secret = os.getenv("FEISHU_APP_SECRET")
        self.chat_id = os.getenv("FEISHU_CHAT_ID", "oc_01bb3fd055745c0baf39552b95e97851")

        # 如果环境变量未设置，尝试从 .mcp.json 读取（开发便利）
        if not self.app_id or not self.app_secret:
            self._load_from_mcp_config()

    def _load_from_mcp_config(self):
        try:
            mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", ".mcp.json")
            with open(mcp_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            server = config.get("mcpServers", {}).get("feishu", {})
            args = server.get("args", [])
            for i, arg in enumerate(args):
                if arg == "--app-id" and i + 1 < len(args):
                    self.app_id = args[i + 1]
                elif arg == "--app-secret" and i + 1 < len(args):
                    self.app_secret = args[i + 1]
        except Exception:
            pass

    def _get_token(self) -> str | None:
        if not self.app_id or not self.app_secret:
            return None
        try:
            req = urllib.request.Request(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                data=json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())["tenant_access_token"]
        except Exception as e:
            logger.warning(f"获取飞书 token 失败: {e}")
            return None

    def send(self, text: str) -> bool:
        token = self._get_token()
        if not token:
            return False
        try:
            req = urllib.request.Request(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                data=json.dumps({
                    "receive_id": self.chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                }).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0:
                    logger.info("飞书消息发送成功")
                    return True
                logger.warning(f"飞书消息发送失败: {result}")
                return False
        except Exception as e:
            logger.warning(f"飞书消息发送异常: {e}")
            return False

    def send_report(self, stats: dict) -> bool:
        """发送测试报告。

        stats 格式: {"passed": int, "failed": int, "skipped": int, "error": int,
                     "duration": str, "case_results": [{"name": str, "outcome": str}, ...]}
        """
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        skipped = stats.get("skipped", 0)
        error = stats.get("error", 0)
        duration = stats.get("duration", "未知")
        case_results = stats.get("case_results", [])
        total = passed + failed + skipped + error

        if failed > 0 or error > 0:
            status = "❌ 存在失败"
            status_icon = "❌"
        elif total == 0:
            status = "⚠️ 未执行测试"
            status_icon = "⚠️"
        else:
            status = "✅ 全部通过"
            status_icon = "✅"

        lines = [
            f"📋 自动化测试完成汇报",
            f"",
            f"执行结果：{status_icon} {status}",
            f"",
            f"━━━━━━━━━━━━━━━",
            f"📊 测试统计",
            f"━━━━━━━━━━━━━━━",
            f"  📝 总计用例: {total}",
            f"  ✅ 通过:     {passed}",
            f"  ❌ 失败:     {failed}",
            f"  ⏭️ 跳过:     {skipped}",
            f"  💥 错误:     {error}",
            f"",
            f"⏱️ 总耗时: {duration}",
        ]

        # 用例明细
        if case_results:
            lines.extend([
                f"",
                f"━━━━━━━━━━━━━━━",
                f"📋 用例明细",
                f"━━━━━━━━━━━━━━━",
            ])
            for i, case in enumerate(case_results, 1):
                outcome = case.get("outcome", "unknown")
                name = case.get("name", "unknown")
                title = case.get("title", name)
                case_duration = case.get("duration", "未知")
                steps = case.get("steps", [])
                icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "💥"}.get(outcome, "❓")
                lines.append(f"  {i}. {icon} {title}")
                lines.append(f"     🆔 {name}  |  ⏱️ {case_duration}")
                if steps:
                    for step in steps:
                        lines.append(f"        · {step}")
                lines.append("")

        if failed > 0:
            lines.extend([
                f"",
                f"⚠️ 注意：存在 {failed} 个失败用例，请查看 Allure 报告和日志定位问题。",
            ])

        text = "\n".join(lines)
        return self.send(text)


def send_feishu_report(stats: dict) -> bool:
    """便捷函数：发送测试报告到飞书。"""
    return FeishuNotifier().send_report(stats)
