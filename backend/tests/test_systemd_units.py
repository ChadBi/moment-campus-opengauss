from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPIRE_POSTS_TIMER = (
    PROJECT_ROOT / "deploy" / "bare-metal" / "moment-expire-posts.timer"
)


def test_expire_posts_timer_runs_five_minutes_after_boot_then_every_thirty_minutes():
    """自动过期 timer 应在启动后 5 分钟首次执行，之后每 30 分钟执行。"""
    timer_content = EXPIRE_POSTS_TIMER.read_text(encoding="utf-8")

    assert "OnBootSec=5min" in timer_content
    assert "OnUnitActiveSec=30min" in timer_content
    assert "OnCalendar=" not in timer_content
    assert "Persistent=true" in timer_content
    assert "Unit=moment-expire-posts.service" in timer_content
