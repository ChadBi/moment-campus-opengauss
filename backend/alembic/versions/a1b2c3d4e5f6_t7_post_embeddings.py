"""T7: posts 原生向量列与 HNSW 索引。

Revision ID: a1b2c3d4e5f6
Revises: 0898a6eeb570
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0898a6eeb570"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE posts ADD COLUMN embedding vector(384)")
    op.execute(
        "CREATE INDEX idx_posts_embedding_hnsw "
        "ON posts USING hnsw (embedding vector_l2_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_posts_embedding_hnsw")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS embedding")

