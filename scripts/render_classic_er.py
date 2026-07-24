"""渲染经典 E-R 图（方框实体、椭圆主码、菱形联系、基数标注）。

输出：
  docs/image/ER图_经典格式.png
  docs/image/ER图_1_用户子系统_经典格式.png
  ...
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "docs" / "image"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def render(html: str, output: Path, viewport_w: int):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": viewport_w, "height": 800}, device_scale_factor=2.0)
        page = context.new_page()
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(output), full_page=True)
        browser.close()
    print(f"  -> {output.name}  ({output.stat().st_size//1024} KB)")


# ============================================================
# 经典 E-R 图 SVG 组件
# ============================================================
def entity(x: int, y: int, w: int, h: int, name: str) -> str:
    """实体（矩形）。"""
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="#1F2937" stroke-width="2" rx="0"/>
      <text x="{x+w//2}" y="{y+h//2+4}" text-anchor="middle" font-size="14" font-weight="700" fill="#1F2937">{name}</text>
    </g>"""


def pk_attr(x: int, y: int, name: str) -> str:
    """主码属性（椭圆，下划线）。"""
    rx, ry = 25, 14
    return f"""
    <g>
      <ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="white" stroke="#1F2937" stroke-width="1.5"/>
      <text x="{x}" y="{y+4}" text-anchor="middle" font-size="12" font-weight="600" fill="#1F2937">{name}</text>
      <line x1="{x-rx+4}" y1="{y+8}" x2="{x+rx-4}" y2="{y+8}" stroke="#1F2937" stroke-width="1.5"/>
    </g>"""


def relationship(x: int, y: int, name: str) -> str:
    """联系（菱形）。"""
    size = 35
    return f"""
    <g>
      <polygon points="{x},{y-size} {x+size},{y} {x},{y+size} {x-size},{y}" fill="white" stroke="#1F2937" stroke-width="2"/>
      <text x="{x}" y="{y+5}" text-anchor="middle" font-size="12" font-weight="700" fill="#1F2937">{name}</text>
    </g>"""


def connect(x1: int, y1: int, x2: int, y2: int, label: str = "", label_pos: str = "mid") -> str:
    """无向线，旁标基数。"""
    lbl = ""
    if label:
        if label_pos == "mid":
            mx, my = (x1+x2)//2, (y1+y2)//2 - 8
        elif label_pos == "start":
            mx, my = x1 + (x2-x1)*0.25, y1 + (y2-y1)*0.25 - 8
        elif label_pos == "end":
            mx, my = x1 + (x2-x1)*0.75, y1 + (y2-y1)*0.75 - 8
        lbl = f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="12" font-weight="600" fill="#1F2937">{label}</text>'
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#1F2937" stroke-width="1.5"/>{lbl}'


def wrap(title: str, content: str, W: int, H: int) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#FAFAFA;}}svg{{display:block;}}
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, sans-serif" font-size="12" width="{W}" height="{H}">
  <rect width="{W}" height="{H}" fill="#FAFAFA"/>
  <text x="{W//2}" y="40" text-anchor="middle" font-size="20" font-weight="700" fill="#1F2937">{title}</text>
  {content}
</svg></body></html>"""


# ============================================================
# 总体 E-R 图
# ============================================================
def er_overall() -> tuple[str, int]:
    W, H = 2000, 1500

    # 实体定义（坐标 + 尺寸）
    ENT = {
        'schools': (100, 80, 100, 50),
        'users': (100, 250, 100, 50),
        'locations': (100, 420, 100, 50),
        'categories': (350, 80, 100, 50),
        'post_types': (350, 200, 100, 50),
        'posts': (550, 200, 100, 50),
        'tags': (780, 80, 100, 50),
        'post_tags': (780, 200, 100, 50),
        'post_images': (780, 340, 100, 50),
        'drafts': (100, 580, 100, 50),
        'topic_collections': (350, 340, 120, 50),
        'topic_collection_posts': (350, 470, 140, 50),
        'comments': (1000, 200, 100, 50),
        'likes': (1000, 340, 100, 50),
        'validation_records': (1000, 480, 130, 50),
        'reports': (1250, 200, 100, 50),
        'notifications': (1250, 340, 110, 50),
        'browse_histories': (1500, 80, 130, 50),
        'search_histories': (1500, 230, 130, 50),
        'admin_operation_logs': (1500, 380, 150, 50),
        'admin_operation_logs_archive': (1500, 530, 160, 50),
    }

    # 主码定义
    PK = {
        'schools': 'id',
        'users': 'id',
        'locations': 'id',
        'categories': 'id',
        'post_types': 'id',
        'posts': '(id,creat_at)',
        'tags': 'id',
        'post_tags': 'id',
        'post_images': 'id',
        'drafts': 'id',
        'topic_collections': 'id',
        'topic_collection_posts': 'id',
        'comments': '(id,creat_at)',
        'likes': 'id',
        'validation_records': '(id,creat_at)',
        'reports': 'id',
        'notifications': '(id,creat_at)',
        'browse_histories': '(id,creat_at)',
        'search_histories': '(id,creat_at)',
        'admin_operation_logs': '(id,creat_at)',
        'admin_operation_logs_archive': 'id',
    }

    content = ""

    # 绘制实体
    for name, (x, y, w, h) in ENT.items():
        content += entity(x, y, w, h, name)
        # 主码椭圆（实体下方）
        pk_name = PK[name]
        pk_x = x + w//2
        pk_y = y + h + 25
        content += pk_attr(pk_x, pk_y, pk_name)
        # 连线：实体 -> 主码
        content += connect(x + w//2, y + h, pk_x, pk_y - 14)

    # 绘制联系和关系
    # users -注册-> schools (1:n)
    content += relationship(150, 180, "注册")
    content += connect(150, 130, 150, 145, "n", "start")
    content += connect(150, 215, 150, 250, "1", "end")

    # locations -包含-> schools (1:n)
    content += relationship(150, 350, "包含")
    content += connect(150, 470, 150, 425, "n", "start")
    content += connect(150, 385, 150, 330, "1", "end")

    # posts -发布-> users (1:n)
    content += relationship(300, 225, "发布")
    content += connect(550, 225, 300, 225, "n", "end")
    content += connect(200, 225, 300, 225, "1", "start")

    # posts -归类-> categories (1:n)
    content += relationship(475, 165, "归类")
    content += connect(550, 200, 475, 200, "n", "start")
    content += connect(450, 130, 475, 130, "1", "end")

    # posts -类型-> post_types (1:n)
    content += connect(450, 225, 550, 225, "1:n")

    # posts -定位-> locations (0..1:n)
    content += connect(150, 445, 550, 200, "0..1:n")

    # posts -附图-> post_images (1:n)
    content += connect(880, 225, 880, 340, "1:n")

    # posts -关联-> post_tags (1:n)
    content += connect(650, 225, 780, 225, "1:n")

    # tags -关联-> post_tags (1:n)
    content += connect(880, 130, 880, 200, "1:n")

    # posts -评论-> comments (1:n)
    content += connect(1000, 200, 650, 225, "1:n")

    # users -评论-> comments (1:n)
    content += connect(200, 275, 1000, 225, "1:n")

    # comments -自引用-> comments (0..1:n)
    content += relationship(1100, 275, "回复")
    content += connect(1100, 250, 1100, 240, "1", "end")
    content += connect(1100, 300, 1000, 275, "n", "start")

    # posts -点赞-> likes (1:n)
    content += connect(650, 250, 1000, 340, "1:n")

    # users -点赞-> likes (1:n)
    content += connect(200, 275, 1000, 365, "1:n")

    # posts -验证-> validation_records (1:n)
    content += connect(650, 250, 1065, 480, "1:n")

    # users -验证-> validation_records (1:n)
    content += connect(200, 275, 1065, 505, "1:n")

    # posts -被举报-> reports (1:n)
    content += connect(650, 250, 1250, 225, "1:n")

    # users -举报-> reports (1:n)
    content += connect(200, 275, 1250, 250, "1:n")

    # comments -被举报-> reports (0..1:n)
    content += connect(1100, 225, 1350, 200, "0..1:n")

    # posts -通知-> notifications (1:n)
    content += connect(650, 250, 1305, 340, "1:n")

    # users -接收-> notifications (1:n)
    content += connect(200, 275, 1305, 365, "1:n")

    # users -浏览-> browse_histories (1:n)
    content += connect(200, 275, 1565, 80, "1:n")

    # posts -被浏览-> browse_histories (1:n)
    content += connect(650, 250, 1565, 105, "1:n")

    # users -搜索-> search_histories (1:n)
    content += connect(200, 275, 1565, 230, "1:n")

    # users(admin) -操作-> admin_operation_logs (1:n)
    content += connect(200, 275, 1575, 380, "1:n")

    # admin_operation_logs -归档-> admin_operation_logs_archive (1:n)
    content += connect(1650, 430, 1580, 530, "1:n")

    # drafts -草稿-> users (1:n)
    content += connect(150, 605, 200, 275, "1:n")

    # topic_collections -创建-> users (1:n)
    content += connect(410, 365, 200, 275, "1:n")

    # posts -合集-> topic_collection_posts (1:n)
    content += connect(650, 250, 420, 470, "1:n")

    # topic_collections -包含-> topic_collection_posts (1:n)
    content += connect(410, 390, 420, 500, "1:n")

    # 图例
    ly = H - 120
    content += f"""
    <g transform="translate(40, {ly})">
      <rect x="0" y="0" width="600" height="100" rx="6" fill="white" stroke="#D1D5DB"/>
      <text x="14" y="20" font-size="12" font-weight="700">图例</text>
      <rect x="14" y="32" width="60" height="30" fill="white" stroke="#1F2937" stroke-width="2"/>
      <text x="44" y="52" text-anchor="middle" font-size="11">实体</text>
      <ellipse cx="110" cy="47" rx="20" ry="12" fill="white" stroke="#1F2937" stroke-width="1.5"/>
      <text x="110" y="51" text-anchor="middle" font-size="10">属性(主码)</text>
      <line x1="90" y1="56" x2="130" y2="56" stroke="#1F2937" stroke-width="1.5"/>
      <polygon points="175,32 195,47 175,62 155,47" fill="white" stroke="#1F2937" stroke-width="2"/>
      <text x="175" y="51" text-anchor="middle" font-size="10">联系</text>
      <line x1="220" y1="47" x2="280" y2="47" stroke="#1F2937" stroke-width="1.5"/>
      <text x="250" y="43" text-anchor="middle" font-size="10">1:n</text>
      <text x="320" y="47" font-size="11">无向线旁标基数比</text>
    </g>"""

    title = "此刻校园 数据库总体 E-R 图（经典格式）"
    return wrap(title, content, W, H), W


# ============================================================
# 子系统 E-R 图
# ============================================================
def er_user_subsystem() -> tuple[str, int]:
    W, H = 1000, 700

    content = ""
    # 实体
    content += entity(150, 150, 100, 50, "schools")
    content += entity(450, 150, 100, 50, "users")
    content += entity(750, 150, 100, 50, "locations")
    # 主码
    content += pk_attr(200, 230, "id")
    content += pk_attr(500, 230, "id")
    content += pk_attr(800, 230, "id")
    # 连线：实体-主码
    content += connect(200, 200, 200, 216)
    content += connect(500, 200, 500, 216)
    content += connect(800, 200, 800, 216)
    # 关系：schools -注册-> users (1:n)
    content += relationship(300, 175, "注册")
    content += connect(250, 175, 300, 175, "1")
    content += connect(450, 175, 300, 175, "n")
    # 关系：schools -包含-> locations (1:n)
    content += relationship(600, 175, "包含")
    content += connect(550, 175, 600, 175, "1")
    content += connect(750, 175, 600, 175, "n")

    title = "A. 用户子系统 E-R 图"
    return wrap(title, content, W, H), W


def er_post_subsystem() -> tuple[str, int]:
    W, H = 1600, 1000

    content = ""
    # 实体
    content += entity(100, 100, 100, 50, "categories")
    content += entity(100, 250, 100, 50, "post_types")
    content += entity(350, 200, 100, 50, "posts")
    content += entity(600, 100, 100, 50, "tags")
    content += entity(600, 250, 100, 50, "post_tags")
    content += entity(600, 400, 100, 50, "post_images")
    content += entity(100, 450, 100, 50, "drafts")
    content += entity(850, 100, 120, 50, "topic_collections")
    content += entity(850, 250, 140, 50, "topic_collection_posts")
    # 外部实体（虚线）
    content += '<rect x="350" y="450" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="400" y="477" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">users</text>'
    content += '<rect x="550" y="450" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="600" y="477" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">locations</text>'
    # 主码
    content += pk_attr(150, 170, "id")
    content += pk_attr(150, 320, "id")
    content += pk_attr(400, 270, "(id,creat_at)")
    content += pk_attr(650, 170, "id")
    content += pk_attr(650, 320, "id")
    content += pk_attr(650, 470, "id")
    content += pk_attr(150, 520, "id")
    content += pk_attr(910, 170, "id")
    content += pk_attr(920, 320, "id")
    # 连线：实体-主码
    content += connect(150, 150, 150, 156)
    content += connect(150, 300, 150, 306)
    content += connect(400, 250, 400, 256)
    content += connect(650, 150, 650, 156)
    content += connect(650, 300, 650, 306)
    content += connect(650, 450, 650, 456)
    content += connect(150, 500, 150, 506)
    content += connect(910, 150, 910, 156)
    content += connect(920, 300, 920, 306)
    # 关系
    content += connect(200, 125, 350, 125, "1:n")
    content += connect(200, 275, 350, 275, "1:n")
    content += connect(450, 225, 600, 225, "1:n")
    content += connect(700, 150, 700, 250, "1:n")
    content += connect(450, 250, 600, 400, "1:n")
    content += connect(150, 475, 400, 450, "1:n", "end")
    content += connect(450, 225, 550, 450, "0..1:n", "end")
    content += connect(450, 225, 850, 250, "1:n")
    content += connect(970, 150, 920, 250, "1:n")

    title = "B. 信息核心子系统 E-R 图"
    return wrap(title, content, W, H), W


def er_inter_subsystem() -> tuple[str, int]:
    W, H = 1200, 700

    content = ""
    # 实体
    content += entity(150, 150, 100, 50, "comments")
    content += entity(450, 150, 100, 50, "likes")
    content += entity(750, 150, 130, 50, "validation_records")
    # 外部实体
    content += '<rect x="300" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="350" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">posts</text>'
    content += '<rect x="500" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="550" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">users</text>'
    # 主码
    content += pk_attr(200, 230, "(id,creat_at)")
    content += pk_attr(500, 230, "id")
    content += pk_attr(815, 230, "(id,creat_at)")
    # 连线：实体-主码
    content += connect(200, 200, 200, 216)
    content += connect(500, 200, 500, 216)
    content += connect(815, 200, 815, 216)
    # 关系
    content += connect(250, 175, 350, 350, "1:n")
    content += connect(250, 175, 550, 350, "1:n")
    content += connect(550, 175, 350, 350, "1:n")
    content += connect(550, 175, 550, 350, "1:n")
    content += connect(880, 175, 350, 350, "1:n")
    content += connect(880, 175, 550, 350, "1:n")
    # comments 自引用
    content += relationship(300, 175, "回复")
    content += connect(250, 175, 300, 175, "n")
    content += connect(300, 175, 250, 175, "0..1")

    title = "C. 互动子系统 E-R 图"
    return wrap(title, content, W, H), W


def er_gov_subsystem() -> tuple[str, int]:
    W, H = 1000, 700

    content = ""
    # 实体
    content += entity(200, 150, 100, 50, "reports")
    content += entity(600, 150, 110, 50, "notifications")
    # 外部实体
    content += '<rect x="350" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="400" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">posts</text>'
    content += '<rect x="500" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="550" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">users</text>'
    # 主码
    content += pk_attr(250, 230, "id")
    content += pk_attr(655, 230, "(id,creat_at)")
    # 连线：实体-主码
    content += connect(250, 200, 250, 216)
    content += connect(655, 200, 655, 216)
    # 关系
    content += connect(300, 175, 400, 350, "1:n")
    content += connect(300, 175, 550, 350, "1:n")
    content += connect(710, 175, 400, 350, "1:n")
    content += connect(710, 175, 550, 350, "1:n")

    title = "D. 治理子系统 E-R 图"
    return wrap(title, content, W, H), W


def er_log_subsystem() -> tuple[str, int]:
    W, H = 1400, 700

    content = ""
    # 实体
    content += entity(150, 150, 130, 50, "browse_histories")
    content += entity(400, 150, 130, 50, "search_histories")
    content += entity(650, 150, 150, 50, "admin_operation_logs")
    content += entity(950, 150, 160, 50, "admin_operation_logs_archive")
    # 外部实体
    content += '<rect x="300" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="350" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">users</text>'
    content += '<rect x="500" y="350" width="100" height="50" fill="white" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="4,3"/>'
    content += '<text x="550" y="377" text-anchor="middle" font-size="12" font-weight="700" fill="#9CA3AF">posts</text>'
    # 主码
    content += pk_attr(215, 230, "(id,creat_at)")
    content += pk_attr(465, 230, "(id,creat_at)")
    content += pk_attr(725, 230, "(id,creat_at)")
    content += pk_attr(1030, 230, "id")
    # 连线：实体-主码
    content += connect(215, 200, 215, 216)
    content += connect(465, 200, 465, 216)
    content += connect(725, 200, 725, 216)
    content += connect(1030, 200, 1030, 216)
    # 关系
    content += connect(280, 175, 350, 350, "1:n")
    content += connect(280, 175, 550, 350, "1:n")
    content += connect(530, 175, 350, 350, "1:n")
    content += connect(800, 175, 350, 350, "1:n")
    content += connect(800, 200, 950, 200, "1:n")

    title = "E. 历史与日志子系统 E-R 图"
    return wrap(title, content, W, H), W


if __name__ == "__main__":
    print("开始生成经典格式 E-R 图...\n")

    tasks = [
        ("ER图_经典格式.png", er_overall),
        ("ER图_1_用户子系统_经典格式.png", er_user_subsystem),
        ("ER图_2_信息核心子系统_经典格式.png", er_post_subsystem),
        ("ER图_3_互动子系统_经典格式.png", er_inter_subsystem),
        ("ER图_4_治理子系统_经典格式.png", er_gov_subsystem),
        ("ER图_5_历史与日志子系统_经典格式.png", er_log_subsystem),
    ]
    for i, (filename, fn) in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {filename}")
        html, w = fn()
        render(html, IMG_DIR / filename, viewport_w=w)

    print("\n全部完成。输出目录：", IMG_DIR)
