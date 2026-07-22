"""数据库审计 VDB 新建实例生命周期验证（占位文件）。

原 `test_vdb_create_lifecycle.py` 中的创建、关机、开机、删除等场景
已经合并到 `test_vdb_operations.py`，按 14 个独立方法重新组织，
与日志审计 VER 的结构保持一致。

保留本文件是为了符合项目"不删除测试文件"的约束，
当前不再收集新的测试用例。
"""
import pytest

pytest.skip("VDB 创建生命周期已合并到 test_vdb_operations.py，本文件仅作占位保留", allow_module_level=True)
