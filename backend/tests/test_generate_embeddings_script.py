import pytest
from sqlalchemy.dialects import postgresql


@pytest.mark.asyncio
async def test_backfill_only_updates_missing_embeddings(monkeypatch):
    from scripts.generate_embeddings import backfill_embeddings

    class Post:
        def __init__(self, post_id, embedding=None):
            self.id = post_id
            self.title = f"标题{post_id}"
            self.content = f"正文{post_id}"
            self.embedding = embedding

    posts = [Post(1), Post(2, [1.0] * 512), Post(3)]
    generated = []

    async def generate(title, content):
        generated.append(title)
        return [0.1] * 512

    stats = await backfill_embeddings(posts, generate=generate)

    assert generated == ["标题1", "标题3"]
    assert stats == {
        "scanned": 3,
        "updated": 2,
        "generation_failed": 0,
        "skipped_existing": 1,
        "dry_run": 0,
        "write_conflict": 0,
        "school_not_found": 0,
    }
    assert posts[0].embedding == [0.1] * 512


@pytest.mark.asyncio
async def test_backfill_dry_run_counts_reason_without_calling_provider_or_writing():
    from scripts.generate_embeddings import backfill_embeddings

    class Post:
        id = 1
        title = "敏感标题不得输出"
        content = "敏感正文不得输出"
        embedding = None

    async def generate(title, content):
        raise AssertionError("dry-run 不应调用 Embedding Provider")

    stats = await backfill_embeddings([Post()], generate=generate, dry_run=True)

    assert stats["scanned"] == 1
    assert stats["dry_run"] == 1
    assert Post.embedding is None


@pytest.mark.asyncio
async def test_backfill_degrades_per_post_when_generator_raises():
    from scripts.generate_embeddings import backfill_embeddings

    class Post:
        def __init__(self, post_id):
            self.id = post_id
            self.title = f"标题{post_id}"
            self.content = f"正文{post_id}"
            self.embedding = None

    async def generate(title, content):
        if title == "标题1":
            raise TimeoutError("provider timeout")
        return [0.2] * 512

    posts = [Post(1), Post(2)]
    stats = await backfill_embeddings(posts, generate=generate)

    assert stats["generation_failed"] == 1
    assert stats["updated"] == 1
    assert posts[0].embedding is None
    assert posts[1].embedding == [0.2] * 512


def test_parser_supports_school_limit_and_dry_run():
    from scripts.generate_embeddings import build_parser

    args = build_parser().parse_args([
        "--school-code", "jiangnan", "--limit", "7", "--dry-run", "--batch-size", "3",
    ])

    assert args.school_code == "jiangnan"
    assert args.limit == 7
    assert args.dry_run is True
    assert args.batch_size == 3


def test_batch_query_keeps_school_boundary_and_limit():
    from scripts.generate_embeddings import build_batch_query

    statement = build_batch_query(last_id=10, batch_size=5, school_code="jiangnan")
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "JOIN schools" in sql
    assert "schools.code = 'jiangnan'" in sql
    assert "posts.embedding IS NULL" in sql
    assert "posts.id > 10" in sql
    assert "LIMIT 5" in sql


def test_stats_output_contains_only_counts(capsys):
    from scripts.generate_embeddings import empty_stats, print_stats

    print_stats(empty_stats())

    output = capsys.readouterr().out
    assert "scanned=" in output
    assert "updated=" in output
    assert "title" not in output
    assert "content" not in output
    assert "key" not in output.lower()
