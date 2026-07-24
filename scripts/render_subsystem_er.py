"""渲染 5 个子系统 ER 图为 PNG（画布自适应版）。

设计原则：
1. 每张表宽度根据最长字段名+类型自适应（最小 280，最大 380）
2. 表内部高度 = 标题(28) + 字段数*行高(20) + padding(8)
3. 画布尺寸 = 内容区域 + 标题区(100) + 图例区(110) + 边距(80)
4. 各图采用统一的视觉密度，避免留白过多或挤压
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "docs" / "image"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def render_html_to_png(html_content: str, output_path: Path, viewport_width: int, scale: float = 2.0):
    """渲染 HTML（包含 SVG）为 PNG。viewport_width 与 SVG 宽度一致。"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": viewport_width, "height": 800},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(output_path), full_page=True)
        browser.close()
    print(f"  -> {output_path.name}  ({output_path.stat().st_size // 1024} KB)")


# ============================================================
# 表尺寸计算
# ============================================================
ROW_H = 20        # 每行高度
HEADER_H = 28      # 标题栏高度
PAD_BOTTOM = 8    # 表底部留白

def table_height(fields: list[tuple]) -> int:
    """根据字段数计算表高度。"""
    return HEADER_H + len(fields) * ROW_H + PAD_BOTTOM


def table_width(name: str, fields: list[tuple]) -> int:
    """根据表名和最长字段计算表宽。"""
    # 字段行内容：[标记 22px] + [字段名] + [类型]
    # 字段名约 8px/字符，类型约 7px/字符（Consolas）
    max_content = 0
    for field, ftype, _ in fields:
        # 22(标记) + 8(间距) + len(field)*8 + 20(间距) + len(ftype)*7
        w = 30 + len(field) * 9 + 20 + len(ftype) * 7
        max_content = max(max_content, w)
    # 加上表名宽度
    name_w = len(name) * 11 + 40
    return max(280, max_content, name_w)


# ============================================================
# SVG 片段
# ============================================================
MARKERS = """
<defs>
  <marker id="crow" viewBox="0 0 14 14" refX="2" refY="7" markerWidth="14" markerHeight="14" orient="auto">
    <path d="M2,7 L14,1 M2,7 L14,7 M2,7 L14,13" stroke="#4B5563" stroke-width="1.4" fill="none"/>
  </marker>
  <marker id="tee" viewBox="0 0 6 14" refX="3" refY="7" markerWidth="6" markerHeight="14" orient="auto">
    <line x1="3" y1="0" x2="3" y2="14" stroke="#4B5563" stroke-width="2"/>
  </marker>
  <marker id="odot" viewBox="0 0 12 14" refX="6" refY="7" markerWidth="12" markerHeight="14" orient="auto">
    <circle cx="6" cy="7" r="3.5" fill="white" stroke="#4B5563" stroke-width="1.5"/>
  </marker>
</defs>
"""


def render_table(x: int, y: int, w: int, name: str, color: str, fields: list[tuple]) -> str:
    """绘制实体表框。fields: [(field, type, mark)]"""
    h = table_height(fields)
    rows = ""
    for i, (field, ftype, mark) in enumerate(fields):
        yy = y + HEADER_H + 4 + i * ROW_H
        # 标记
        if mark == "PK":
            rows += f'<rect x="{x+6}" y="{yy+1}" width="22" height="15" fill="#FEF3C7" rx="2"/>'
            rows += f'<text x="{x+17}" y="{yy+12}" font-size="9" font-weight="700" fill="#92400E" text-anchor="middle">PK</text>'
        elif mark == "FK":
            rows += f'<rect x="{x+6}" y="{yy+1}" width="22" height="15" fill="#DBEAFE" rx="2"/>'
            rows += f'<text x="{x+17}" y="{yy+12}" font-size="9" font-weight="700" fill="#1E40AF" text-anchor="middle">FK</text>'
        elif mark == "UQ":
            rows += f'<rect x="{x+6}" y="{yy+1}" width="22" height="15" fill="#D1FAE5" rx="2"/>'
            rows += f'<text x="{x+17}" y="{yy+12}" font-size="9" font-weight="700" fill="#065F46" text-anchor="middle">UQ</text>'
        rows += f'<text x="{x+34}" y="{yy+12}" font-size="11" fill="#1F2937" font-weight="600">{field}</text>'
        rows += f'<text x="{x+w-10}" y="{yy+12}" font-size="10" fill="#0E7490" text-anchor="end" font-family="Consolas,monospace">{ftype}</text>'
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="white" stroke="{color}" stroke-width="2"/>
      <rect x="{x}" y="{y}" width="{w}" height="{HEADER_H}" fill="{color}"/>
      <text x="{x+w//2}" y="{y+19}" text-anchor="middle" font-size="13" font-weight="700" fill="white">{name}</text>
      {rows}
    </g>"""


def render_ext_box(x: int, y: int, w: int, name: str, color: str = "#9CA3AF") -> str:
    """外部表简化框（虚线）。"""
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="{w}" height="30" rx="4" fill="white" stroke="{color}" stroke-width="1.5" stroke-dasharray="4,3"/>
      <text x="{x+w//2}" y="{y+19}" text-anchor="middle" font-size="11" font-weight="600" fill="{color}">{name}</text>
    </g>"""


def render_rel(x1: int, y1: int, x2: int, y2: int, color: str = "#4B5563", label: str = "", dashed: bool = False, m1: str = "tee", m2: str = "crow") -> str:
    """关系连线。"""
    dash = 'stroke-dasharray="5,3"' if dashed else ''
    ms = f'marker-start="url(#{m1})"' if m1 != "none" else ''
    me = f'marker-end="url(#{m2})"' if m2 != "none" else ''
    lbl = ""
    if label:
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2 - 6
        lbl = f'<text x="{mx}" y="{my}" font-size="10" fill="{color}" text-anchor="middle" font-weight="600">{label}</text>'
    return f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="1.5" fill="none" {dash} {ms} {me}/>{lbl}'


def render_legend(x: int, y: int) -> str:
    """图例。"""
    return f"""
    <g transform="translate({x}, {y})">
      <rect x="0" y="0" width="560" height="80" rx="6" fill="white" stroke="#D1D5DB"/>
      <text x="14" y="20" font-size="12" font-weight="700" fill="#1F2937">图例</text>
      <rect x="14" y="30" width="22" height="14" fill="#FEF3C7" rx="2"/><text x="42" y="42" font-size="11">PK 主键</text>
      <rect x="100" y="30" width="22" height="14" fill="#DBEAFE" rx="2"/><text x="128" y="42" font-size="11">FK 外键</text>
      <rect x="186" y="30" width="22" height="14" fill="#D1FAE5" rx="2"/><text x="214" y="42" font-size="11">UQ 唯一</text>
      <line x1="14" y1="62" x2="60" y2="62" stroke="#4B5563" stroke-width="1.5" marker-start="url(#tee)" marker-end="url(#crow)"/>
      <text x="68" y="66" font-size="11">1:N 强制</text>
      <line x1="160" y1="62" x2="206" y2="62" stroke="#4B5563" stroke-width="1.5" marker-start="url(#odot)" marker-end="url(#crow)"/>
      <text x="214" y="66" font-size="11">0/1:N 可选</text>
      <line x1="300" y1="62" x2="346" y2="62" stroke="#9CA3AF" stroke-width="1.5" stroke-dasharray="5,3"/>
      <text x="354" y="66" font-size="11">虚线=外部引用</text>
    </g>"""


def build_svg(title: str, subtitle: str, color: str, bg: str, W: int, H: int, content: str) -> str:
    """组装 SVG 文档。"""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:{bg};}}svg{{display:block;}}
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Microsoft YaHei, sans-serif" font-size="12" width="{W}" height="{H}">
  <rect width="{W}" height="{H}" fill="{bg}"/>
  <rect x="20" y="20" width="{W-40}" height="{H-40}" rx="8" fill="white" stroke="{color}" stroke-width="1" stroke-dasharray="5,3" opacity="0.4"/>
  <text x="{W//2}" y="50" text-anchor="middle" font-size="20" font-weight="700" fill="{color}">{title}</text>
  <text x="{W//2}" y="72" text-anchor="middle" font-size="12" fill="#6B7280">{subtitle}</text>
  {MARKERS}
  {content}
  {render_legend(40, H - 100)}
</svg></body></html>"""


# ============================================================
# 子系统 1：用户子系统（3 张表水平排列）
# ============================================================
def render_user_subsystem() -> str:
    C = "#1E40AF"
    BG = "#EFF6FF"
    schools = [
        ("id", "BIGINT", "PK"), ("code", "VARCHAR(20)", "UQ"),
        ("name", "VARCHAR(100)", ""), ("logo_url", "VARCHAR(500)", ""),
        ("province", "VARCHAR(50)", ""), ("city", "VARCHAR(50)", ""),
        ("address", "VARCHAR(255)", ""), ("center_lat", "FLOAT", ""),
        ("center_lng", "FLOAT", ""), ("map_zoom", "INT", ""),
        ("is_active", "BOOLEAN", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    users = [
        ("id", "BIGINT", "PK"), ("email", "VARCHAR(255)", "UQ"),
        ("school_id", "BIGINT", "FK"), ("nickname", "VARCHAR(50)", ""),
        ("password_hash", "VARCHAR(255)", ""), ("avatar_url", "VARCHAR(500)", ""),
        ("role", "VARCHAR(20)", ""), ("bio", "VARCHAR(500)", ""),
        ("is_active", "BOOLEAN", ""), ("last_login_at", "TIMESTAMP", ""),
        ("reputation_score", "NUMERIC(5,2)", ""), ("is_deleted", "BOOLEAN", ""),
        ("deleted_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    locations = [
        ("id", "BIGINT", "PK"), ("school_id", "BIGINT", "FK"),
        ("name", "VARCHAR(100)", ""), ("description", "VARCHAR(500)", ""),
        ("latitude", "NUMERIC(10,7)", ""), ("longitude", "NUMERIC(10,7)", ""),
        ("building", "VARCHAR", ""), ("floor", "VARCHAR", ""),
        ("post_count", "INT", ""), ("is_verified", "BOOLEAN", ""),
        ("is_deleted", "BOOLEAN", ""), ("deleted_at", "TIMESTAMP", ""),
        ("created_at", "TIMESTAMP", ""), ("updated_at", "TIMESTAMP", ""),
    ]
    # 计算每张表宽度
    w1 = table_width("schools  学校", schools)
    w2 = table_width("users  用户", users)
    w3 = table_width("locations  地点", locations)
    GAP = 60
    MARGIN_X = 50
    table_y = 130
    # 计算总宽
    W = MARGIN_X * 2 + w1 + GAP + w2 + GAP + w3
    # 计算高度（取最大表高）
    h_max = max(table_height(schools), table_height(users), table_height(locations))
    H = table_y + h_max + 130  # 图例区 100 + 边距 30

    # 表位置
    x1 = MARGIN_X
    x2 = x1 + w1 + GAP
    x3 = x2 + w2 + GAP

    content = ""
    content += render_table(x1, table_y, w1, "schools  学校", C, schools)
    content += render_table(x2, table_y, w2, "users  用户", C, users)
    content += render_table(x3, table_y, w3, "locations  地点", C, locations)

    # 关系：schools(中) -> users(左) 1:N 注册
    sx_center = x1 + w1 // 2
    ux_top = x2 + w2 // 2
    content += render_rel(sx_center, table_y, ux_top, table_y, C, "1:N 注册")
    # schools -> locations 1:N 包含
    lx_top = x3 + w3 // 2
    content += render_rel(sx_center, table_y, lx_top, table_y, C, "1:N 包含")

    title = "A. 用户子系统 ER 图"
    subtitle = f"3 张表  ·  schools 为配置核心  ·  表宽自适应"
    return build_svg(title, subtitle, C, BG, W, H, content), W


# ============================================================
# 子系统 2：信息核心子系统（posts 中心放射）
# ============================================================
def render_post_subsystem() -> str:
    C = "#C2410C"
    BG = "#FFF7ED"
    posts = [
        ("id, created_at", "BIGINT,TS", "PK"),
        ("user_id", "BIGINT", "FK"), ("school_id", "BIGINT", "FK"),
        ("category_id", "BIGINT", "FK"), ("post_type_id", "BIGINT", "FK"),
        ("location_id", "BIGINT", "FK"), ("title", "VARCHAR(200)", ""),
        ("content", "TEXT", ""), ("is_anonymous", "BOOLEAN", ""),
        ("status", "VARCHAR(20)", ""), ("view_count", "INT", ""),
        ("like_count", "INT", ""), ("comment_count", "INT", ""),
        ("valid_count", "INT", ""), ("invalid_count", "INT", ""),
        ("credibility_score", "NUMERIC(5,2)", ""), ("expire_at", "TIMESTAMP", ""),
        ("activity_start_at", "TIMESTAMP", ""), ("activity_end_at", "TIMESTAMP", ""),
        ("lost_type", "VARCHAR(10)", ""), ("contact_info", "VARCHAR(255)", ""),
        ("is_recommend", "BOOLEAN", ""), ("is_deleted", "BOOLEAN", ""),
        ("deleted_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    categories = [
        ("id", "BIGINT", "PK"), ("code", "VARCHAR(30)", "UQ"),
        ("name", "VARCHAR(50)", ""), ("icon", "VARCHAR(10)", ""),
        ("description", "VARCHAR(200)", ""), ("default_validity_days", "INT", ""),
        ("sort_order", "INT", ""), ("is_active", "BOOLEAN", ""),
        ("created_at", "TIMESTAMP", ""), ("updated_at", "TIMESTAMP", ""),
    ]
    post_types = [
        ("id", "BIGINT", "PK"), ("code", "VARCHAR(30)", "UQ"),
        ("name", "VARCHAR(50)", ""), ("description", "VARCHAR(200)", ""),
        ("sort_order", "INT", ""), ("is_active", "BOOLEAN", ""),
        ("created_at", "TIMESTAMP", ""), ("updated_at", "TIMESTAMP", ""),
    ]
    tags = [
        ("id", "BIGINT", "PK"), ("name", "VARCHAR(50)", "UQ"),
        ("slug", "VARCHAR(60)", "UQ"), ("usage_count", "INT", ""),
        ("is_official", "BOOLEAN", ""), ("is_deleted", "BOOLEAN", ""),
        ("deleted_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    post_tags = [
        ("id", "BIGINT", "PK"), ("post_id", "BIGINT", "FK"),
        ("tag_id", "BIGINT", "FK"), ("(post_id,tag_id)", "UQ", "UQ"),
        ("created_at", "TIMESTAMP", ""),
    ]
    post_images = [
        ("id", "BIGINT", "PK"), ("post_id", "BIGINT", "FK"),
        ("image_url", "VARCHAR(500)", ""), ("thumbnail_url", "VARCHAR(500)", ""),
        ("sort_order", "INT", ""), ("file_size", "INT", ""),
        ("width", "INT", ""), ("height", "INT", ""),
        ("is_deleted", "BOOLEAN", ""), ("deleted_at", "TIMESTAMP", ""),
        ("created_at", "TIMESTAMP", ""),
    ]
    drafts = [
        ("id", "BIGINT", "PK"), ("user_id", "BIGINT", "FK"),
        ("title", "VARCHAR(200)", ""), ("content", "TEXT", ""),
        ("category_id", "BIGINT", "FK"), ("post_type_id", "BIGINT", "FK"),
        ("location_id", "BIGINT", "FK"), ("is_anonymous", "BOOLEAN", ""),
        ("extra_data", "TEXT", ""), ("is_deleted", "BOOLEAN", ""),
        ("deleted_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    topic_collections = [
        ("id", "BIGINT", "PK"), ("school_id", "BIGINT", "FK"),
        ("creator_id", "BIGINT", "FK"), ("title", "VARCHAR", ""),
        ("description", "TEXT", ""), ("cover_url", "VARCHAR(500)", ""),
        ("post_count", "INT", ""), ("view_count", "INT", ""),
        ("status", "VARCHAR(20)", ""), ("sort_order", "INT", ""),
        ("published_at", "TIMESTAMP", ""), ("is_deleted", "BOOLEAN", ""),
        ("deleted_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    topic_collection_posts = [
        ("id", "BIGINT", "PK"), ("topic_collection_id", "BIGINT", "FK"),
        ("post_id", "BIGINT", "FK"), ("(tc_id,post_id)", "UQ", "UQ"),
        ("sort_order", "INT", ""), ("created_at", "TIMESTAMP", ""),
    ]

    # 表宽
    w_posts = table_width("posts  信息（分区表）", posts)
    w_cat = table_width("categories  分类", categories)
    w_pt = table_width("post_types  类型", post_types)
    w_tags = table_width("tags  标签", tags)
    w_ptags = table_width("post_tags  关联(M:N)", post_tags)
    w_pimg = table_width("post_images  信息图片", post_images)
    w_drafts = table_width("drafts  草稿", drafts)
    w_tc = table_width("topic_collections  合集", topic_collections)
    w_tcp = table_width("tc_posts (M:N)", topic_collection_posts)

    # 布局：posts 居中，左侧 categories/post_types/drafts，右侧 tags/post_tags/post_images/topic_collections/tc_posts
    MARGIN = 50
    LEFT_GAP = 60
    RIGHT_GAP = 60
    left_col_w = max(w_cat, w_pt, w_drafts)
    right_col_w = max(w_tags, w_ptags, w_pimg, w_tc, w_tcp)

    W = MARGIN + left_col_w + LEFT_GAP + w_posts + RIGHT_GAP + right_col_w + MARGIN

    # 行布局
    POSTS_Y = 130
    posts_h = table_height(posts)
    # 左列三表
    left_x = MARGIN
    cat_y = POSTS_Y
    pt_y = cat_y + table_height(categories) + 40
    drafts_y = pt_y + table_height(post_types) + 40

    # posts 位置
    posts_x = left_x + left_col_w + LEFT_GAP

    # 右列：tags / post_tags / post_images / topic_collections / tc_posts
    right_x = posts_x + w_posts + RIGHT_GAP
    tags_y = POSTS_Y
    ptags_y = tags_y + table_height(tags) + 40
    pimg_y = ptags_y + table_height(post_tags) + 40
    tc_y = pimg_y + table_height(post_images) + 40
    tcp_y = tc_y + table_height(topic_collections) + 40

    # 高度 = max(左列底, 右列底, posts底) + 图例
    left_bottom = drafts_y + table_height(drafts)
    right_bottom = tcp_y + table_height(topic_collection_posts)
    posts_bottom = POSTS_Y + posts_h
    H = max(left_bottom, right_bottom, posts_bottom) + 130

    content = ""
    # 左列
    content += render_table(left_x, cat_y, w_cat, "categories  分类", C, categories)
    content += render_table(left_x, pt_y, w_pt, "post_types  类型", C, post_types)
    content += render_table(left_x, drafts_y, w_drafts, "drafts  草稿", C, drafts)
    # 中心 posts
    content += render_table(posts_x, POSTS_Y, w_posts, "posts  信息（分区表）", C, posts)
    # 右列
    content += render_table(right_x, tags_y, w_tags, "tags  标签", C, tags)
    content += render_table(right_x, ptags_y, w_ptags, "post_tags  关联(M:N)", C, post_tags)
    content += render_table(right_x, pimg_y, w_pimg, "post_images  信息图片", C, post_images)
    content += render_table(right_x, tc_y, w_tc, "topic_collections  合集", C, topic_collections)
    content += render_table(right_x, tcp_y, w_tcp, "tc_posts (M:N)", C, topic_collection_posts)

    # 关系：categories -> posts
    content += render_rel(left_x + w_cat//2, cat_y + table_height(categories),
                          posts_x, POSTS_Y + 30, C, "1:N 归类")
    # post_types -> posts
    content += render_rel(left_x + w_pt//2, pt_y + table_height(post_types),
                          posts_x, POSTS_Y + 60, C, "1:N 类型")
    # drafts -> users (外部，虚线)
    content += render_rel(left_x + w_drafts//2, drafts_y, posts_x - 30, POSTS_Y,
                          "#9CA3AF", "FK→users", dashed=True, m1="crow", m2="odot")
    # posts -> post_images
    content += render_rel(posts_x + w_posts, POSTS_Y + 100, right_x, pimg_y + 20, C, "1:N 附图")
    # posts -> post_tags (M:N 一端)
    content += render_rel(posts_x + w_posts, POSTS_Y + 50, right_x, ptags_y + 10, C, "1:N (M:N)")
    # tags -> post_tags
    content += render_rel(right_x + w_tags//2, tags_y + table_height(tags),
                          right_x + w_ptags//2, ptags_y, C, "1:N (M:N)")
    # posts -> tc_posts (M:N 另一端)
    content += render_rel(posts_x + w_posts, POSTS_Y + 200, right_x, tcp_y + 10, C, "1:N (M:N)")
    # topic_collections -> tc_posts
    content += render_rel(right_x + w_tc//2, tc_y + table_height(topic_collections),
                          right_x + w_tcp//2, tcp_y, C, "1:N (M:N)")

    title = "B. 信息核心子系统 ER 图"
    subtitle = f"9 张表  ·  posts 为业务中心  ·  含 2 个 M:N 关联表"
    return build_svg(title, subtitle, C, BG, W, H, content), W


# ============================================================
# 子系统 3：互动子系统（3 张表水平排列）
# ============================================================
def render_inter_subsystem() -> str:
    C = "#15803D"
    BG = "#F0FDF4"
    comments = [
        ("id, created_at", "BIGINT,TS", "PK"), ("post_id", "BIGINT", "FK"),
        ("user_id", "BIGINT", "FK"), ("parent_id", "BIGINT", "FK"),
        ("reply_to_user_id", "BIGINT", "FK"), ("content", "TEXT", ""),
        ("like_count", "INT", ""), ("status", "VARCHAR(20)", ""),
        ("is_deleted", "BOOLEAN", ""), ("deleted_at", "TIMESTAMP", ""),
        ("created_at", "TIMESTAMP", ""), ("updated_at", "TIMESTAMP", ""),
    ]
    likes = [
        ("id", "BIGINT", "PK"), ("post_id", "BIGINT", "FK"),
        ("user_id", "BIGINT", "FK"), ("(post_id,user_id)", "UQ", "UQ"),
        ("created_at", "TIMESTAMP", ""),
    ]
    validation = [
        ("id, created_at", "BIGINT,TS", "PK"), ("post_id", "BIGINT", "FK"),
        ("user_id", "BIGINT", "FK"), ("(post_id,user_id)", "UQ", "UQ"),
        ("validation_type", "VARCHAR(20)", ""), ("comment", "VARCHAR(500)", ""),
        ("is_deleted", "BOOLEAN", ""), ("deleted_at", "TIMESTAMP", ""),
        ("created_at", "TIMESTAMP", ""),
    ]
    w1 = table_width("comments  评论（分区表）", comments)
    w2 = table_width("likes  点赞（M:N）", likes)
    w3 = table_width("validation_records  协同验证", validation)
    GAP = 60
    MARGIN = 50
    table_y = 130
    W = MARGIN * 2 + w1 + GAP + w2 + GAP + w3
    h_max = max(table_height(comments), table_height(likes), table_height(validation))
    H = table_y + h_max + 130

    x1 = MARGIN
    x2 = x1 + w1 + GAP
    x3 = x2 + w2 + GAP

    content = ""
    content += render_table(x1, table_y, w1, "comments  评论（分区表）", C, comments)
    content += render_table(x2, table_y, w2, "likes  点赞（M:N）", C, likes)
    content += render_table(x3, table_y, w3, "validation_records  协同验证", C, validation)

    # 外部引用（顶部）
    ext_w = 200
    ext_y = 95
    content += render_ext_box(x1 + (w1 - ext_w)//2, ext_y, ext_w, "posts / users (外部)")
    content += render_ext_box(x2 + (w2 - ext_w)//2, ext_y, ext_w, "posts / users (外部)")
    content += render_ext_box(x3 + (w3 - ext_w)//2, ext_y, ext_w, "posts / users (外部)")
    # 外部引用线
    content += render_rel(x1 + w1//2, table_y, x1 + w1//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")
    content += render_rel(x2 + w2//2, table_y, x2 + w2//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")
    content += render_rel(x3 + w3//2, table_y, x3 + w3//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")

    # comments 自引用
    self_x = x1 + w1
    self_y1 = table_y + 100
    self_y2 = table_y + 130
    content += f'<path d="M{self_x},{self_y1} C {self_x+30},{self_y1} {self_x+30},{self_y2} {self_x},{self_y2}" stroke="#15803D" stroke-width="1.5" fill="none" stroke-dasharray="3,2" marker-start="url(#odot)" marker-end="url(#crow)"/>'
    content += f'<text x="{self_x+10}" y="{(self_y1+self_y2)//2+4}" font-size="10" fill="#15803D">parent_id 自引用</text>'

    title = "C. 互动子系统 ER 图"
    subtitle = "3 张表  ·  全部依赖 posts/users（外部）  ·  comments 自引用父子评论"
    return build_svg(title, subtitle, C, BG, W, H, content), W


# ============================================================
# 子系统 4：治理子系统（2 张表水平排列）
# ============================================================
def render_gov_subsystem() -> str:
    C = "#B91C1C"
    BG = "#FEF2F2"
    reports = [
        ("id", "BIGINT", "PK"), ("post_id", "BIGINT", "FK"),
        ("comment_id", "BIGINT", "FK"), ("reporter_id", "BIGINT", "FK"),
        ("handler_id", "BIGINT", "FK"), ("(post_id,reporter_id)", "UQ", "UQ"),
        ("report_type", "VARCHAR(30)", ""), ("description", "TEXT", ""),
        ("status", "VARCHAR(20)", ""), ("handle_result", "TEXT", ""),
        ("handled_at", "TIMESTAMP", ""), ("created_at", "TIMESTAMP", ""),
        ("updated_at", "TIMESTAMP", ""),
    ]
    notif = [
        ("id, created_at", "BIGINT,TS", "PK"), ("user_id", "BIGINT", "FK"),
        ("actor_id", "BIGINT", "FK"), ("type", "VARCHAR(30)", ""),
        ("title", "VARCHAR(200)", ""), ("content", "VARCHAR(500)", ""),
        ("target_type", "VARCHAR(50)", ""), ("target_id", "BIGINT", ""),
        ("is_read", "BOOLEAN", ""), ("read_at", "TIMESTAMP", ""),
        ("is_deleted", "BOOLEAN", ""), ("deleted_at", "TIMESTAMP", ""),
        ("created_at", "TIMESTAMP", ""),
    ]
    w1 = table_width("reports  举报", reports)
    w2 = table_width("notifications  通知（分区表）", notif)
    GAP = 80
    MARGIN = 50
    table_y = 130
    W = MARGIN * 2 + w1 + GAP + w2
    h_max = max(table_height(reports), table_height(notif))
    H = table_y + h_max + 130

    x1 = MARGIN
    x2 = x1 + w1 + GAP

    content = ""
    content += render_table(x1, table_y, w1, "reports  举报", C, reports)
    content += render_table(x2, table_y, w2, "notifications  通知（分区表）", C, notif)

    # 外部表（上方）
    ext_w = 200
    ext_y = 95
    content += render_ext_box(x1 + (w1 - ext_w)//2, ext_y, ext_w, "posts / comments / users")
    content += render_ext_box(x2 + (w2 - ext_w)//2, ext_y, ext_w, "users (接收/触发)")
    # 引用线
    content += render_rel(x1 + w1//2, table_y, x1 + w1//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")
    content += render_rel(x2 + w2//2, table_y, x2 + w2//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")

    title = "D. 治理子系统 ER 图"
    subtitle = "2 张表  ·  reports 同时支持帖/评论举报  ·  notifications 分区表"
    return build_svg(title, subtitle, C, BG, W, H, content), W


# ============================================================
# 子系统 5：历史与日志子系统（4 张表水平排列）
# ============================================================
def render_log_subsystem() -> str:
    C = "#6D28D9"
    BG = "#F5F3FF"
    browse = [
        ("id, created_at", "BIGINT,TS", "PK"), ("user_id", "BIGINT", "FK"),
        ("post_id", "BIGINT", "FK"), ("created_at", "TIMESTAMP", ""),
    ]
    search = [
        ("id, created_at", "BIGINT,TS", "PK"), ("user_id", "BIGINT", "FK"),
        ("keyword", "VARCHAR(200)", ""), ("result_count", "INT", ""),
        ("created_at", "TIMESTAMP", ""),
    ]
    admin_log = [
        ("id, created_at", "BIGINT,TS", "PK"), ("admin_id", "BIGINT", "FK"),
        ("action", "VARCHAR(50)", ""), ("target_type", "VARCHAR(50)", ""),
        ("target_id", "BIGINT", ""), ("detail", "TEXT", ""),
        ("ip_address", "VARCHAR(45)", ""), ("user_agent", "VARCHAR(500)", ""),
        ("created_at", "TIMESTAMP", ""),
    ]
    archive = [
        ("id", "BIGINT", "PK"), ("admin_id", "BIGINT", ""),
        ("action", "VARCHAR(50)", ""), ("target_type", "VARCHAR(50)", ""),
        ("target_id", "BIGINT", ""), ("detail", "TEXT", ""),
        ("ip_address", "VARCHAR(45)", ""), ("user_agent", "VARCHAR(500)", ""),
        ("created_at", "TIMESTAMP", ""), ("archived_at", "TIMESTAMP", ""),
    ]
    w1 = table_width("browse_histories  浏览历史", browse)
    w2 = table_width("search_histories  搜索历史", search)
    w3 = table_width("admin_operation_logs  管理日志", admin_log)
    w4 = table_width("..._archive  日志归档", archive)
    GAP = 50
    MARGIN = 50
    table_y = 130
    W = MARGIN * 2 + w1 + GAP + w2 + GAP + w3 + GAP + w4
    h_max = max(table_height(browse), table_height(search), table_height(admin_log), table_height(archive))
    H = table_y + h_max + 130

    x1 = MARGIN
    x2 = x1 + w1 + GAP
    x3 = x2 + w2 + GAP
    x4 = x3 + w3 + GAP

    content = ""
    content += render_table(x1, table_y, w1, "browse_histories  浏览历史", C, browse)
    content += render_table(x2, table_y, w2, "search_histories  搜索历史", C, search)
    content += render_table(x3, table_y, w3, "admin_operation_logs  管理日志", C, admin_log)
    content += render_table(x4, table_y, w4, "..._archive  日志归档", C, archive)

    # 外部表（上方）
    ext_w = 200
    ext_y = 95
    content += render_ext_box(x1 + (w1 - ext_w)//2, ext_y, ext_w, "users / posts")
    content += render_ext_box(x2 + (w2 - ext_w)//2, ext_y, ext_w, "users")
    content += render_ext_box(x3 + (w3 - ext_w)//2, ext_y, ext_w, "users (admin)")
    # 引用线
    content += render_rel(x1 + w1//2, table_y, x1 + w1//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")
    content += render_rel(x2 + w2//2, table_y, x2 + w2//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")
    content += render_rel(x3 + w3//2, table_y, x3 + w3//2, ext_y + 30, "#9CA3AF", "FK", dashed=True, m1="crow", m2="odot")

    # admin_log -> archive 归档关系
    content += render_rel(x3 + w3, table_y + 100, x4, table_y + 100, C, "归档(90天前)", m1="crow", m2="crow")

    title = "E. 历史与日志子系统 ER 图"
    subtitle = "4 张表  ·  全部按月分区（archive 除外）  ·  90天前日志归档"
    return build_svg(title, subtitle, C, BG, W, H, content), W


if __name__ == "__main__":
    print("开始重新生成 5 个子系统 ER 图（画布自适应版）...\n")

    tasks = [
        ("ER图_1_用户子系统.png", render_user_subsystem),
        ("ER图_2_信息核心子系统.png", render_post_subsystem),
        ("ER图_3_互动子系统.png", render_inter_subsystem),
        ("ER图_4_治理子系统.png", render_gov_subsystem),
        ("ER图_5_历史与日志子系统.png", render_log_subsystem),
    ]
    for i, (filename, fn) in enumerate(tasks, 1):
        print(f"[{i}/5] {filename}")
        html, w = fn()
        render_html_to_png(html, IMG_DIR / filename, viewport_width=w, scale=2.0)

    print("\n全部完成。输出目录：", IMG_DIR)
    print("\n所有图片清单：")
    for f in sorted(IMG_DIR.iterdir()):
        if f.is_file():
            print(f"  {f.name:50s}  {f.stat().st_size//1024} KB")
