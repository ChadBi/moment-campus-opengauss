"""T-B-01 Post 状态机单元测试

覆盖验收标准第 5 项：单元测试覆盖所有合法/非法流转。
"""
import pytest

from app.core.post_status import (
    PostStatus,
    can_transition,
    get_allowed_transitions,
    is_valid_status,
    normalize_status,
)


class TestPostStatusConstants:
    """6 态常量定义完整性"""

    def test_all_six_states_defined(self):
        """6 态全部定义"""
        assert PostStatus.DRAFT == "draft"
        assert PostStatus.PENDING == "pending"
        assert PostStatus.PUBLISHED == "published"
        assert PostStatus.EXPIRED == "expired"
        assert PostStatus.CONFLICT == "conflict"
        assert PostStatus.ARCHIVED == "archived"

    def test_all_tuple_contains_exactly_six(self):
        """ALL 元组恰好包含 6 个状态，无重复"""
        assert len(PostStatus.ALL) == 6
        assert len(set(PostStatus.ALL)) == 6

    def test_all_states_fit_in_string_20(self):
        """所有状态值长度 <= 20（数据库字段为 String(20)）"""
        for status in PostStatus.ALL:
            assert len(status) <= 20, f"状态 {status} 长度超过 20"


class TestIsValidStatus:
    """is_valid_status 函数"""

    @pytest.mark.parametrize("status", list(PostStatus.ALL))
    def test_valid_states(self, status):
        """6 个正式状态全部有效"""
        assert is_valid_status(status) is True

    def test_alias_pending_review_valid(self):
        """别名 pending_review 有效"""
        assert is_valid_status("pending_review") is True

    def test_invalid_status(self):
        """非法状态值无效"""
        assert is_valid_status("unknown") is False
        assert is_valid_status("") is False
        assert is_valid_status("PUBLISHED") is False  # 大小写敏感
        assert is_valid_status("published ") is False  # 含空格


class TestNormalizeStatus:
    """normalize_status 函数"""

    def test_normalize_alias(self):
        """别名归一化为正式名"""
        assert normalize_status("pending_review") == "pending"

    def test_normalize_formal_unchanged(self):
        """正式名归一化后不变"""
        for status in PostStatus.ALL:
            assert normalize_status(status) == status

    def test_normalize_unknown_unchanged(self):
        """未知值原样返回"""
        assert normalize_status("unknown") == "unknown"


class TestCanTransitionLegal:
    """合法流转（验收标准：覆盖所有合法流转）"""

    def test_draft_to_pending(self):
        """draft → pending：用户提交审核"""
        assert can_transition("draft", "pending") is True

    def test_draft_to_archived(self):
        """draft → archived：用户放弃草稿"""
        assert can_transition("draft", "archived") is True

    def test_pending_to_published(self):
        """pending → published：管理员审核通过"""
        assert can_transition("pending", "published") is True

    def test_pending_to_draft(self):
        """pending → draft：管理员驳回"""
        assert can_transition("pending", "draft") is True

    def test_pending_to_archived(self):
        """pending → archived：放弃审核"""
        assert can_transition("pending", "archived") is True

    def test_published_to_expired(self):
        """published → expired：自动过期"""
        assert can_transition("published", "expired") is True

    def test_published_to_conflict(self):
        """published → conflict：冲突检测"""
        assert can_transition("published", "conflict") is True

    def test_published_to_archived(self):
        """published → archived：管理员归档"""
        assert can_transition("published", "archived") is True

    def test_expired_to_published(self):
        """expired → published：用户续期"""
        assert can_transition("expired", "published") is True

    def test_expired_to_archived(self):
        """expired → archived：归档过期信息"""
        assert can_transition("expired", "archived") is True

    def test_conflict_to_published(self):
        """conflict → published：管理员裁定后恢复"""
        assert can_transition("conflict", "published") is True

    def test_conflict_to_archived(self):
        """conflict → archived：管理员裁定后归档"""
        assert can_transition("conflict", "archived") is True

    def test_alias_pending_review_to_published(self):
        """别名：pending_review → published 合法"""
        assert can_transition("pending_review", "published") is True


class TestCanTransitionIllegal:
    """非法流转（验收标准：覆盖所有非法流转）"""

    def test_archived_is_terminal_state(self):
        """archived 为终态，不可流转到任何状态"""
        for target in PostStatus.ALL:
            assert can_transition("archived", target) is False, \
                f"archived → {target} 应为非法"

    def test_draft_cannot_directly_publish(self):
        """draft 不能直接 published（必须先 pending 审核）"""
        assert can_transition("draft", "published") is False

    def test_draft_cannot_to_expired_or_conflict(self):
        """draft 不能直接 expired/conflict"""
        assert can_transition("draft", "expired") is False
        assert can_transition("draft", "conflict") is False

    def test_pending_cannot_to_expired(self):
        """pending 不能直接 expired（必须先 published）"""
        assert can_transition("pending", "expired") is False

    def test_pending_cannot_to_conflict(self):
        """pending 不能直接 conflict"""
        assert can_transition("pending", "conflict") is False

    def test_published_cannot_back_to_draft(self):
        """published 不能回退到 draft"""
        assert can_transition("published", "draft") is False

    def test_published_cannot_back_to_pending(self):
        """published 不能回退到 pending"""
        assert can_transition("published", "pending") is False

    def test_expired_cannot_to_draft_or_pending(self):
        """expired 不能回到 draft/pending"""
        assert can_transition("expired", "draft") is False
        assert can_transition("expired", "pending") is False

    def test_expired_cannot_to_conflict(self):
        """expired 不能直接转 conflict"""
        assert can_transition("expired", "conflict") is False

    def test_conflict_cannot_to_draft_or_pending(self):
        """conflict 不能回到 draft/pending"""
        assert can_transition("conflict", "draft") is False
        assert can_transition("conflict", "pending") is False

    def test_conflict_cannot_to_expired(self):
        """conflict 不能直接转 expired"""
        assert can_transition("conflict", "expired") is False

    def test_unknown_current_status(self):
        """未知当前状态返回 False"""
        assert can_transition("unknown", "published") is False

    def test_unknown_target_status(self):
        """未知目标状态返回 False"""
        assert can_transition("draft", "unknown") is False

    def test_same_status_self_transition(self):
        """同状态自流转：除终态外，所有状态不能自流转"""
        # archived 已在 test_archived_is_terminal_state 覆盖
        for status in [PostStatus.DRAFT, PostStatus.PENDING, PostStatus.PUBLISHED,
                       PostStatus.EXPIRED, PostStatus.CONFLICT]:
            assert can_transition(status, status) is False, \
                f"{status} → {status} 自流转应为非法"


class TestGetAllowedTransitions:
    """get_allowed_transitions 函数"""

    def test_draft_allowed(self):
        """draft 允许流转到 pending / archived"""
        allowed = get_allowed_transitions("draft")
        assert allowed == {"pending", "archived"}

    def test_pending_allowed(self):
        """pending 允许流转到 published / draft / archived"""
        allowed = get_allowed_transitions("pending")
        assert allowed == {"published", "draft", "archived"}

    def test_published_allowed(self):
        """published 允许流转到 expired / conflict / archived"""
        allowed = get_allowed_transitions("published")
        assert allowed == {"expired", "conflict", "archived"}

    def test_expired_allowed(self):
        """expired 允许流转到 published / archived"""
        allowed = get_allowed_transitions("expired")
        assert allowed == {"published", "archived"}

    def test_conflict_allowed(self):
        """conflict 允许流转到 published / archived"""
        allowed = get_allowed_transitions("conflict")
        assert allowed == {"published", "archived"}

    def test_archived_allowed_empty(self):
        """archived 无允许流转（终态）"""
        allowed = get_allowed_transitions("archived")
        assert allowed == set()

    def test_unknown_status_empty(self):
        """未知状态返回空集"""
        assert get_allowed_transitions("unknown") == set()

    def test_alias_normalized(self):
        """别名输入被归一化"""
        allowed = get_allowed_transitions("pending_review")
        assert allowed == {"published", "draft", "archived"}

    def test_returned_set_is_copy(self):
        """返回的集合是副本，修改不影响内部状态"""
        allowed = get_allowed_transitions("draft")
        allowed.add("hacked")
        # 再次获取应不受影响
        allowed2 = get_allowed_transitions("draft")
        assert "hacked" not in allowed2


class TestBackwardCompatibility:
    """向后兼容性测试（验收标准：不破坏现有 seed_data 与测试）"""

    def test_seed_data_published_compatible(self):
        """seed_data.py 中的 status='published' 仍为有效状态"""
        assert is_valid_status("published") is True
        assert normalize_status("published") == "published"

    def test_default_pending_compatible(self):
        """模型默认 status='pending' 仍为有效状态"""
        assert is_valid_status("pending") is True
        assert normalize_status("pending") == "pending"

    def test_published_can_transition_to_expired(self):
        """published → expired 流转可用（自动过期机制依赖）"""
        assert can_transition("published", "expired") is True

    def test_published_can_transition_to_archived(self):
        """published → archived 流转可用（管理员归档依赖）"""
        assert can_transition("published", "archived") is True
