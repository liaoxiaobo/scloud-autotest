class SSHAssertionMixin:
    """SSH 后端断言 Mixin。

    验证 scli guest show 等后端命令的输出字段。
    属于 L3 Consistency 层断言。
    """

    def assert_guest_fields(self, ecs_id, expected_fields, error_prefix):
        """校验 scli guest show 中的字段值。"""
        stdout = self.guest_show(ecs_id)
        for field, expected in expected_fields.items():
            actual = stdout.get(field)
            assert actual == expected, f"{error_prefix}，期望 {field}:{expected}，实际 {field}:{actual}"
        return stdout

    def assert_guest_node(self, ecs_id, expected_node, error_prefix):
        """校验虚机后端节点。"""
        self.assert_guest_fields(ecs_id, {"node": expected_node}, error_prefix)
