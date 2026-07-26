"""REC-01: 用户推荐偏好（个性化开关）

业务规则：
- 每用户一行（user_id 唯一），记录是否启用个性化推荐
- personalization_enabled 默认 True；用户可关闭后清除浏览历史（不再用于画像）
- 关闭个性化后：不再基于浏览/搜索历史打分，但仍可看本校热门/最新/管理员推荐（冷启动路径）
- 偏好按 user_id 隔离，跨校共用同一份开关（隐私设置不应随学校切换而变）
"""
from sqlalchemy import BigInteger, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.database import Base


class UserRecommendationPreference(Base):
    """REC-01.2: 用户推荐隐私偏好

    每用户一行（user_id 唯一），记录个性化推荐开关。
    关闭后：不再使用浏览/搜索画像做打分；浏览历史可由用户手动清除或随关闭操作一并清除。
    """

    __tablename__ = "user_recommendation_preferences"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    # 个性化推荐开关；True=启用画像打分，False=仅冷启动（热门/最新/管理员推荐）
    personalization_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="REC-01.2: 是否启用个性化推荐；关闭后改用冷启动（本校热门/最新/管理员推荐）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="recommendation_preference")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_recommendation_preference_user"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserRecommendationPreference(user_id={self.user_id}, "
            f"personalization_enabled={self.personalization_enabled})>"
        )
