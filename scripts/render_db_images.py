"""将 ER 图 SVG 与 SQL 表结构 HTML 通过 playwright 渲染为 PNG 图片。

输入：
  - ER 图 SVG（手写 SVG，等同于 dot 文件渲染结果）
  - SQL 表结构 HTML（两张分图）

输出：
  docs/image/ER图.png
  docs/image/SQL表结构_1_用户与信息核心子系统.png
  docs/image/SQL表结构_2_互动治理日志子系统.png
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "docs" / "image"
IMG_DIR.mkdir(parents=True, exist_ok=True)


def render_html_to_png(html_content: str, output_path: Path, viewport_width: int = 1700, full_page: bool = True, scale: float = 2.0):
    """用 Chromium 把 HTML 内容渲染为 PNG。"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": viewport_width, "height": 1200},
            device_scale_factor=scale,
        )
        page = context.new_page()
        page.set_content(html_content, wait_until="networkidle")
        # 给字体一点时间加载
        page.wait_for_timeout(500)
        page.screenshot(path=str(output_path), full_page=full_page)
        browser.close()
    print(f"  -> {output_path.name}  ({output_path.stat().st_size // 1024} KB)")


# ===================== ER 图 SVG =====================
# 这里采用与聊天中渲染一致的 SVG，作为 dot 文件的视觉等价物
ER_SVG = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:#FAFAFA;}
svg{display:block;}
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1640 1180" font-family="Microsoft YaHei, sans-serif" font-size="12" width="1640" height="1180">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#4B5563"/>
    </marker>
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
  <rect width="1640" height="1180" fill="#FAFAFA"/>
  <text x="820" y="38" text-anchor="middle" font-size="22" font-weight="700" fill="#1F2937">此刻校园 数据库 ER 图（江南大学蠡湖校区）</text>
  <text x="820" y="62" text-anchor="middle" font-size="13" fill="#6B7280">基于源码反向提取 · 共 22 张表 · Crow's Foot 表示法</text>
  <rect x="20" y="90" width="240" height="540" rx="8" fill="#EFF6FF" stroke="#1E40AF" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="140" y="110" text-anchor="middle" font-size="14" font-weight="700" fill="#1E40AF">用户子系统</text>
  <rect x="280" y="90" width="540" height="740" rx="8" fill="#FFF7ED" stroke="#C2410C" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="550" y="110" text-anchor="middle" font-size="14" font-weight="700" fill="#C2410C">信息核心子系统</text>
  <rect x="840" y="90" width="260" height="540" rx="8" fill="#F0FDF4" stroke="#15803D" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="970" y="110" text-anchor="middle" font-size="14" font-weight="700" fill="#15803D">互动子系统</text>
  <rect x="1120" y="90" width="500" height="400" rx="8" fill="#FEF2F2" stroke="#B91C1C" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="1370" y="110" text-anchor="middle" font-size="14" font-weight="700" fill="#B91C1C">治理子系统</text>
  <rect x="1120" y="510" width="500" height="620" rx="8" fill="#F5F3FF" stroke="#6D28D9" stroke-width="1" stroke-dasharray="5,3"/>
  <text x="1370" y="530" text-anchor="middle" font-size="14" font-weight="700" fill="#6D28D9">历史与日志子系统</text>

  <g>
    <rect x="40" y="130" width="200" height="64" rx="6" fill="white" stroke="#1E40AF" stroke-width="2"/>
    <rect x="40" y="130" width="200" height="22" fill="#1E40AF"/>
    <text x="140" y="146" text-anchor="middle" font-size="13" font-weight="700" fill="white">schools 学校</text>
    <text x="50" y="170" font-size="11" fill="#1F2937">PK id</text>
    <text x="50" y="184" font-size="10" fill="#6B7280">UQ code · name · 地图坐标</text>
  </g>
  <g>
    <rect x="40" y="290" width="200" height="80" rx="6" fill="white" stroke="#1E40AF" stroke-width="2"/>
    <rect x="40" y="290" width="200" height="22" fill="#1E40AF"/>
    <text x="140" y="306" text-anchor="middle" font-size="13" font-weight="700" fill="white">users 用户</text>
    <text x="50" y="330" font-size="11" fill="#1F2937">PK id</text>
    <text x="50" y="344" font-size="10" fill="#6B7280">FK school_id · UQ email</text>
    <text x="50" y="358" font-size="10" fill="#6B7280">role · reputation_score</text>
  </g>
  <g>
    <rect x="40" y="490" width="200" height="74" rx="6" fill="white" stroke="#1E40AF" stroke-width="2"/>
    <rect x="40" y="490" width="200" height="22" fill="#1E40AF"/>
    <text x="140" y="506" text-anchor="middle" font-size="13" font-weight="700" fill="white">locations 地点</text>
    <text x="50" y="530" font-size="11" fill="#1F2937">PK id</text>
    <text x="50" y="544" font-size="10" fill="#6B7280">FK school_id · lat/lng</text>
    <text x="50" y="558" font-size="10" fill="#6B7280">building · floor</text>
  </g>
  <g>
    <rect x="300" y="140" width="180" height="58" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="300" y="140" width="180" height="22" fill="#C2410C"/>
    <text x="390" y="156" text-anchor="middle" font-size="13" font-weight="700" fill="white">categories 分类</text>
    <text x="310" y="180" font-size="11" fill="#1F2937">PK id · UQ code · name</text>
    <text x="310" y="194" font-size="10" fill="#6B7280">default_validity_days</text>
  </g>
  <g>
    <rect x="300" y="220" width="180" height="50" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="300" y="220" width="180" height="22" fill="#C2410C"/>
    <text x="390" y="236" text-anchor="middle" font-size="13" font-weight="700" fill="white">post_types 类型</text>
    <text x="310" y="260" font-size="11" fill="#1F2937">PK id · UQ code · name</text>
  </g>
  <g>
    <rect x="300" y="370" width="260" height="170" rx="6" fill="white" stroke="#C2410C" stroke-width="2.5"/>
    <rect x="300" y="370" width="260" height="24" fill="#C2410C"/>
    <text x="430" y="388" text-anchor="middle" font-size="14" font-weight="700" fill="white">posts 信息（分区表）</text>
    <text x="310" y="414" font-size="11" fill="#1F2937">PK (id, created_at)</text>
    <text x="310" y="430" font-size="10" fill="#6B7280">FK user_id · school_id · category_id</text>
    <text x="310" y="444" font-size="10" fill="#6B7280">FK post_type_id · location_id</text>
    <text x="310" y="460" font-size="10" fill="#1F2937">title · content · is_anonymous</text>
    <text x="310" y="474" font-size="10" fill="#1F2937">status 6态机 · credibility_score</text>
    <text x="310" y="488" font-size="10" fill="#1F2937">view/like/comment/valid/invalid</text>
    <text x="310" y="502" font-size="10" fill="#1F2937">expire_at · activity_start/end_at</text>
    <text x="310" y="516" font-size="10" fill="#6B7280">lost_type · is_recommend</text>
    <text x="310" y="530" font-size="10" fill="#9CA3AF">is_deleted/deleted_at · created_at</text>
  </g>
  <g>
    <rect x="620" y="140" width="180" height="58" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="620" y="140" width="180" height="22" fill="#C2410C"/>
    <text x="710" y="156" text-anchor="middle" font-size="13" font-weight="700" fill="white">tags 标签</text>
    <text x="630" y="180" font-size="11" fill="#1F2937">PK id · UQ name · UQ slug</text>
    <text x="630" y="194" font-size="10" fill="#6B7280">usage_count · is_official</text>
  </g>
  <g>
    <rect x="620" y="230" width="180" height="58" rx="6" fill="white" stroke="#C2410C" stroke-width="1.5" stroke-dasharray="3,2"/>
    <rect x="620" y="230" width="180" height="22" fill="#C2410C"/>
    <text x="710" y="246" text-anchor="middle" font-size="13" font-weight="700" fill="white">post_tags 关联</text>
    <text x="630" y="270" font-size="11" fill="#1F2937">PK id · FK post_id · FK tag_id</text>
    <text x="630" y="284" font-size="10" fill="#6B7280">UQ (post_id, tag_id) — M:N</text>
  </g>
  <g>
    <rect x="620" y="370" width="180" height="60" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="620" y="370" width="180" height="22" fill="#C2410C"/>
    <text x="710" y="386" text-anchor="middle" font-size="13" font-weight="700" fill="white">post_images 图片</text>
    <text x="630" y="410" font-size="11" fill="#1F2937">PK id · FK post_id</text>
    <text x="630" y="424" font-size="10" fill="#6B7280">image_url · width/height</text>
  </g>
  <g>
    <rect x="300" y="600" width="240" height="80" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="300" y="600" width="240" height="22" fill="#C2410C"/>
    <text x="420" y="616" text-anchor="middle" font-size="13" font-weight="700" fill="white">drafts 草稿</text>
    <text x="310" y="640" font-size="11" fill="#1F2937">PK id · FK user_id</text>
    <text x="310" y="654" font-size="10" fill="#6B7280">FK category/type/location_id (可选)</text>
    <text x="310" y="668" font-size="10" fill="#6B7280">title · content · extra_data</text>
  </g>
  <g>
    <rect x="620" y="510" width="180" height="68" rx="6" fill="white" stroke="#C2410C" stroke-width="2"/>
    <rect x="620" y="510" width="180" height="22" fill="#C2410C"/>
    <text x="710" y="526" text-anchor="middle" font-size="13" font-weight="700" fill="white">topic_collections</text>
    <text x="630" y="550" font-size="11" fill="#1F2937">PK id · FK school_id</text>
    <text x="630" y="564" font-size="10" fill="#6B7280">FK creator_id · title · status</text>
  </g>
  <g>
    <rect x="620" y="600" width="180" height="68" rx="6" fill="white" stroke="#C2410C" stroke-width="1.5" stroke-dasharray="3,2"/>
    <rect x="620" y="600" width="180" height="22" fill="#C2410C"/>
    <text x="710" y="616" text-anchor="middle" font-size="12" font-weight="700" fill="white">topic_collection_posts</text>
    <text x="630" y="640" font-size="11" fill="#1F2937">PK id · FK topic_collection_id</text>
    <text x="630" y="654" font-size="10" fill="#6B7280">FK post_id · UQ(组合) — M:N</text>
  </g>
  <g>
    <rect x="860" y="140" width="220" height="100" rx="6" fill="white" stroke="#15803D" stroke-width="2"/>
    <rect x="860" y="140" width="220" height="22" fill="#15803D"/>
    <text x="970" y="156" text-anchor="middle" font-size="13" font-weight="700" fill="white">comments 评论（分区表）</text>
    <text x="870" y="180" font-size="11" fill="#1F2937">PK (id, created_at)</text>
    <text x="870" y="194" font-size="10" fill="#6B7280">FK post_id · user_id</text>
    <text x="870" y="208" font-size="10" fill="#6B7280">FK parent_id (自引用) </text>
    <text x="870" y="222" font-size="10" fill="#6B7280">FK reply_to_user_id · like_count</text>
  </g>
  <g>
    <rect x="860" y="270" width="220" height="60" rx="6" fill="white" stroke="#15803D" stroke-width="2"/>
    <rect x="860" y="270" width="220" height="22" fill="#15803D"/>
    <text x="970" y="286" text-anchor="middle" font-size="13" font-weight="700" fill="white">likes 点赞</text>
    <text x="870" y="310" font-size="11" fill="#1F2937">PK id · FK post_id · FK user_id</text>
    <text x="870" y="324" font-size="10" fill="#6B7280">UQ (post_id, user_id) — M:N</text>
  </g>
  <g>
    <rect x="860" y="360" width="220" height="80" rx="6" fill="white" stroke="#15803D" stroke-width="2"/>
    <rect x="860" y="360" width="220" height="22" fill="#15803D"/>
    <text x="970" y="376" text-anchor="middle" font-size="13" font-weight="700" fill="white">validation_records 协同验证</text>
    <text x="870" y="400" font-size="11" fill="#1F2937">PK (id, created_at)</text>
    <text x="870" y="414" font-size="10" fill="#6B7280">FK post_id · FK user_id</text>
    <text x="870" y="428" font-size="10" fill="#6B7280">UQ (post_id, user_id) · 2 类</text>
  </g>
  <g>
    <rect x="1140" y="140" width="220" height="100" rx="6" fill="white" stroke="#B91C1C" stroke-width="2"/>
    <rect x="1140" y="140" width="220" height="22" fill="#B91C1C"/>
    <text x="1250" y="156" text-anchor="middle" font-size="13" font-weight="700" fill="white">reports 举报</text>
    <text x="1150" y="180" font-size="11" fill="#1F2937">PK id</text>
    <text x="1150" y="194" font-size="10" fill="#6B7280">FK post_id · FK comment_id</text>
    <text x="1150" y="208" font-size="10" fill="#6B7280">FK reporter_id · FK handler_id</text>
    <text x="1150" y="222" font-size="10" fill="#6B7280">UQ (post_id, reporter_id)</text>
  </g>
  <g>
    <rect x="1380" y="140" width="220" height="90" rx="6" fill="white" stroke="#B91C1C" stroke-width="2"/>
    <rect x="1380" y="140" width="220" height="22" fill="#B91C1C"/>
    <text x="1490" y="156" text-anchor="middle" font-size="13" font-weight="700" fill="white">notifications 通知（分区）</text>
    <text x="1390" y="180" font-size="11" fill="#1F2937">PK (id, created_at)</text>
    <text x="1390" y="194" font-size="10" fill="#6B7280">FK user_id · FK actor_id</text>
    <text x="1390" y="208" font-size="10" fill="#6B7280">type · target_type/id</text>
  </g>
  <g>
    <rect x="1140" y="560" width="220" height="68" rx="6" fill="white" stroke="#6D28D9" stroke-width="2"/>
    <rect x="1140" y="560" width="220" height="22" fill="#6D28D9"/>
    <text x="1250" y="576" text-anchor="middle" font-size="13" font-weight="700" fill="white">browse_histories 浏览</text>
    <text x="1150" y="600" font-size="11" fill="#1F2937">PK (id, created_at) 分区</text>
    <text x="1150" y="614" font-size="10" fill="#6B7280">FK user_id · FK post_id</text>
  </g>
  <g>
    <rect x="1380" y="560" width="220" height="68" rx="6" fill="white" stroke="#6D28D9" stroke-width="2"/>
    <rect x="1380" y="560" width="220" height="22" fill="#6D28D9"/>
    <text x="1490" y="576" text-anchor="middle" font-size="13" font-weight="700" fill="white">search_histories 搜索</text>
    <text x="1390" y="600" font-size="11" fill="#1F2937">PK (id, created_at) 分区</text>
    <text x="1390" y="614" font-size="10" fill="#6B7280">FK user_id · keyword</text>
  </g>
  <g>
    <rect x="1140" y="700" width="220" height="80" rx="6" fill="white" stroke="#6D28D9" stroke-width="2"/>
    <rect x="1140" y="700" width="220" height="22" fill="#6D28D9"/>
    <text x="1250" y="716" text-anchor="middle" font-size="13" font-weight="700" fill="white">admin_operation_logs</text>
    <text x="1150" y="740" font-size="11" fill="#1F2937">PK (id, created_at) 分区</text>
    <text x="1150" y="754" font-size="10" fill="#6B7280">FK admin_id · action</text>
    <text x="1150" y="768" font-size="10" fill="#6B7280">target_type/id · ip · UA</text>
  </g>
  <g>
    <rect x="1380" y="700" width="220" height="80" rx="6" fill="white" stroke="#6D28D9" stroke-width="1.5" stroke-dasharray="3,2"/>
    <rect x="1380" y="700" width="220" height="22" fill="#6D28D9"/>
    <text x="1490" y="716" text-anchor="middle" font-size="12" font-weight="700" fill="white">..._archive 日志归档</text>
    <text x="1390" y="740" font-size="11" fill="#1F2937">PK id</text>
    <text x="1390" y="754" font-size="10" fill="#6B7280">结构同 admin_operation_logs</text>
    <text x="1390" y="768" font-size="10" fill="#9CA3AF">+ archived_at</text>
  </g>

  <path d="M140,194 L140,290" stroke="#1E40AF" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="148" y="245" font-size="10" fill="#1E40AF">1:N 注册</text>
  <path d="M140,370 L140,490" stroke="#1E40AF" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="148" y="435" font-size="10" fill="#1E40AF">1:N 包含</text>
  <path d="M240,160 C 270,200 270,400 300,400" stroke="#1E40AF" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="248" y="280" font-size="10" fill="#1E40AF">1:N 归属</text>
  <path d="M240,330 C 270,330 270,420 300,420" stroke="#1E40AF" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="250" y="350" font-size="10" fill="#1E40AF">1:N 发布</text>
  <path d="M390,198 L390,370" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="398" y="290" font-size="10" fill="#C2410C">1:N 归类</text>
  <path d="M390,270 L390,370" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M240,527 C 270,527 270,470 300,470" stroke="#1E40AF" stroke-width="1.5" fill="none" marker-start="url(#odot)" marker-end="url(#crow)"/>
  <text x="248" y="510" font-size="10" fill="#1E40AF">0/1:N 定位</text>
  <path d="M560,440 L620,400" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="568" y="418" font-size="10" fill="#C2410C">1:N 附图</text>
  <path d="M560,400 L620,260" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="568" y="335" font-size="10" fill="#C2410C">1:N</text>
  <path d="M710,198 L710,230" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M560,400 C 700,400 720,200 860,200" stroke="#15803D" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="660" y="270" font-size="10" fill="#15803D">1:N 评论</text>
  <path d="M240,330 C 600,330 700,210 860,210" stroke="#15803D" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M1010,170 C 1060,170 1060,220 1010,220" stroke="#15803D" stroke-width="1.2" fill="none" stroke-dasharray="3,2" marker-start="url(#odot)" marker-end="url(#crow)"/>
  <text x="1018" y="200" font-size="9" fill="#15803D">0/1:N 回复</text>
  <path d="M560,440 C 700,440 720,300 860,300" stroke="#15803D" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="660" y="345" font-size="10" fill="#15803D">1:N 点赞</text>
  <path d="M240,340 C 600,340 700,320 860,320" stroke="#15803D" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M560,470 C 700,470 720,400 860,400" stroke="#15803D" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="660" y="425" font-size="10" fill="#15803D">1:N 验证</text>
  <path d="M240,350 C 600,350 700,420 860,420" stroke="#15803D" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M560,490 C 800,490 900,200 1140,200" stroke="#B91C1C" stroke-width="1.5" fill="none" marker-start="url(#odot)" marker-end="url(#crow)"/>
  <text x="900" y="250" font-size="10" fill="#B91C1C">0/1:N 被举报</text>
  <path d="M240,365 C 600,365 900,210 1140,210" stroke="#B91C1C" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="900" y="378" font-size="9" fill="#B91C1C">1:N 举报人</text>
  <path d="M240,375 C 600,375 1100,375 1380,180" stroke="#B91C1C" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="700" y="385" font-size="9" fill="#B91C1C">1:N 接收</text>
  <path d="M240,385 C 700,500 900,590 1140,590" stroke="#6D28D9" stroke-width="1.2" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="700" y="510" font-size="9" fill="#6D28D9">1:N 浏览</text>
  <path d="M240,400 C 700,520 1100,520 1380,590" stroke="#6D28D9" stroke-width="1.2" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="700" y="540" font-size="9" fill="#6D28D9">1:N 搜索</text>
  <path d="M240,415 C 700,560 900,740 1140,740" stroke="#6D28D9" stroke-width="1.2" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="700" y="600" font-size="9" fill="#6D28D9">1:N 操作</text>
  <path d="M1360,740 L1380,740" stroke="#6D28D9" stroke-width="1.5" fill="none" stroke-dasharray="5,3" marker-start="url(#crow)" marker-end="url(#crow)"/>
  <text x="1362" y="730" font-size="9" fill="#6D28D9">归档</text>
  <path d="M380,540 L380,600" stroke="#C2410C" stroke-width="1.2" fill="none" stroke-dasharray="3,2"/>
  <path d="M560,460 C 590,460 590,640 620,640" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <text x="568" y="555" font-size="10" fill="#C2410C">1:N</text>
  <path d="M710,578 L710,600" stroke="#C2410C" stroke-width="1.5" fill="none" marker-start="url(#tee)" marker-end="url(#crow)"/>
  <path d="M240,170 C 470,170 470,540 620,540" stroke="#1E40AF" stroke-width="1.2" fill="none" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>

  <g transform="translate(40, 1000)">
    <rect x="0" y="0" width="1560" height="160" rx="6" fill="white" stroke="#D1D5DB" stroke-width="1"/>
    <text x="20" y="22" font-size="14" font-weight="700" fill="#1F2937">图例</text>
    <text x="20" y="48" font-size="11" fill="#1F2937">实体颜色：</text>
    <rect x="100" y="38" width="14" height="14" fill="#1E40AF"/><text x="120" y="50" font-size="11">用户子系统</text>
    <rect x="200" y="38" width="14" height="14" fill="#C2410C"/><text x="220" y="50" font-size="11">信息核心子系统</text>
    <rect x="320" y="38" width="14" height="14" fill="#15803D"/><text x="340" y="50" font-size="11">互动子系统</text>
    <rect x="420" y="38" width="14" height="14" fill="#B91C1C"/><text x="440" y="50" font-size="11">治理子系统</text>
    <rect x="520" y="38" width="14" height="14" fill="#6D28D9"/><text x="540" y="50" font-size="11">历史与日志子系统</text>
    <rect x="660" y="38" width="14" height="14" fill="white" stroke="#6B7280" stroke-dasharray="3,2"/><text x="680" y="50" font-size="11">M:N 关联表/归档表</text>
    <text x="20" y="78" font-size="11" fill="#1F2937">关系记号（Crow's Foot）：</text>
    <line x1="160" y1="74" x2="220" y2="74" stroke="#4B5563" stroke-width="1.5" marker-start="url(#tee)" marker-end="url(#crow)"/>
    <text x="230" y="78" font-size="11">1:N（一对多，强制）</text>
    <line x1="380" y1="74" x2="440" y2="74" stroke="#4B5563" stroke-width="1.5" marker-start="url(#odot)" marker-end="url(#crow)"/>
    <text x="450" y="78" font-size="11">0/1:N（可选一对多）</text>
    <line x1="600" y1="74" x2="660" y2="74" stroke="#4B5563" stroke-width="1.5" stroke-dasharray="4,3" marker-start="url(#tee)" marker-end="url(#crow)"/>
    <text x="670" y="78" font-size="11">虚线 = 用户作为操作者</text>
    <text x="20" y="108" font-size="11" fill="#1F2937">主键标记：</text>
    <text x="100" y="108" font-size="11" fill="#1F2937"><tspan font-weight="700">PK</tspan> 主键</text>
    <text x="180" y="108" font-size="11" fill="#1F2937"><tspan font-weight="700">FK</tspan> 外键</text>
    <text x="260" y="108" font-size="11" fill="#1F2937"><tspan font-weight="700">UQ</tspan> 唯一约束</text>
    <text x="20" y="134" font-size="11" fill="#6B7280">说明：7 张大表（posts / comments / notifications / admin_operation_logs / browse_histories / search_histories / validation_records）</text>
    <text x="20" y="150" font-size="11" fill="#6B7280">采用 RANGE 分区（按 created_at 月度分区），故主键为 (id, created_at) 复合主键。其他表为单字段主键。</text>
  </g>
</svg>
</body></html>
"""

# ===================== SQL 表结构 HTML（1/2） =====================
# 此处省略，从外部 HTML 文件读取（保持脚本简洁）

if __name__ == "__main__":
    print("开始生成图片到 docs/image/ ...")

    # 1. ER 图
    print("[1/3] 渲染 ER 图...")
    render_html_to_png(ER_SVG, IMG_DIR / "ER图.png", viewport_width=1700, scale=1.5)

    # 2. SQL 表结构图 1
    html_1 = (ROOT / "scripts" / "_tmp_tables_1.html").read_text(encoding="utf-8")
    print("[2/3] 渲染 SQL 表结构图 1...")
    render_html_to_png(html_1, IMG_DIR / "SQL表结构_1_用户与信息核心子系统.png", viewport_width=1700, scale=2.0)

    # 3. SQL 表结构图 2
    html_2 = (ROOT / "scripts" / "_tmp_tables_2.html").read_text(encoding="utf-8")
    print("[3/3] 渲染 SQL 表结构图 2...")
    render_html_to_png(html_2, IMG_DIR / "SQL表结构_2_互动治理日志子系统.png", viewport_width=1700, scale=2.0)

    print("\n全部完成。输出目录：", IMG_DIR)
