# coding=utf-8
"""
此刻校园 - 视频旁白 AI 语音生成脚本
模型：qwen-audio-3.0-tts-plus（阿里云百炼 DashScope）
使用前请设置环境变量：$env:DASHSCOPE_API_KEY = "sk-xxx"
文档：https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide
模型页：https://www.qianwenai.com/models/qwen-audio-3.0-tts-plus

两种调用方式：
  方式 A（默认）：DashScope SDK — WebSocket 连接，返回音频字节，输出 MP3
  方式 B（备选）：HTTP REST API — 返回音频 URL，支持 WAV 格式
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# ============================================================
# 配置
# ============================================================

API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not API_KEY:
    print("错误：请先设置环境变量 DASHSCOPE_API_KEY")
    print('  PowerShell: $env:DASHSCOPE_API_KEY = "sk-xxx"')
    print("  获取地址：https://help.aliyun.com/zh/model-studio/get-api-key")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 模型与音色
MODEL = "qwen-audio-3.0-tts-plus"
VOICE_DEMO = "longanhuan_v3.6"       # 作品演示视频：沉稳男声
VOICE_PERSONAL = "longanhuan_v3.6"   # 个人介绍视频：同款男声（可改 longanyang 女声）

# REST API 端点
REST_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"

# ============================================================
# 旁白文本（从脚本中提取，每段独立生成）
# ============================================================

# 作品演示视频旁白（9段）
DEMO_NARRATIONS = [
    {
        "id": "demo_01_pain_point",
        "text": "每天，校园里产生大量信息：二手交易、失物招领、活动组队、生活吐槽。但它们散落在几十个微信群、表白墙和公告栏里。你找不到需要的信息，发布的信息也很快沉底、过期、无人知晓。校园信息，缺一个统一的入口。"
    },
    {
        "id": "demo_02_product",
        "text": "此刻校园——一张活的校园信息地图。我们把校园里每一条信息，绑定到地图上的一个位置、一个时间、一个分类，让信息不再流浪。"
    },
    {
        "id": "demo_03_map",
        "text": "打开地图页，校园信息以点位形式呈现在地图上。每条信息都有精确的地理位置，点击标记即可查看详情。无论是图书馆的空座分享，还是食堂的失物招领，一目了然。"
    },
    {
        "id": "demo_04_ai_search",
        "text": "传统搜索只能匹配关键词。我们接入了AI语义搜索：输入\u201c哪里有流浪猫\u201d，AI首先解析你的意图——识别关键词\u201c流浪猫\u201d，匹配到分享和失物招领分类，再通过openGauss DataVec 512维语义向量进行召回，最后按语义相关性、新鲜度、验证数和关键词匹配度混合排序。每条结果都标注了匹配理由，让你知道\u201c为什么推荐这条\u201d。"
    },
    {
        "id": "demo_05_ai_publish",
        "text": "发布信息时，不知道选什么分类？不确定有效期设多久？点击\u201cAI辅助建议\u201d，系统自动分析你的内容，推荐最合适的分类、建议合理的有效期，并检测是否包含敏感信息。你可以逐条确认采纳，也可以手动修改。每一条建议都透明可控。"
    },
    {
        "id": "demo_06_verification",
        "text": "信息发布后，谁来保证它的真实性？我们设计了协同验证机制。每条帖子都可以被其他用户\u201c证实\u201d或\u201c证伪\u201d，两类互斥，可以切换，再次点击同类即可取消。验证结果以百分比直观展示。多人证实的信息可信度高，多人证伪的信息会触发平台关注。这是一种去中心化的信息自治理方式。"
    },
    {
        "id": "demo_07_social_value",
        "text": "校园信息不对称是一个真实的社会问题。找不到失物、错过活动、重复消费——此刻校园通过地图定位让信息可发现，通过有效期让信息不过期，通过协同验证让信息可信任。这不是一个论坛，而是一套校园信息基础设施。目前平台已入驻三所高校，累计沉淀超过1500条真实校园信息。"
    },
    {
        "id": "demo_08_trae",
        "text": "从第一行代码到最后一次部署，全程使用TRAE IDE完成。"
    },
    {
        "id": "demo_09_outro",
        "text": "此刻校园支持多学校入驻，切换学校，信息独立。让校园里每一刻都值得被看见。此刻校园，给信息一个坐标，给此刻一个归属。"
    },
]

# 个人介绍视频旁白（4段）
PERSONAL_NARRATIONS = [
    {
        "id": "personal_01_intro",
        "text": "你好，我是一名校园摄影爱好者。在大学校园里，我最喜欢做的事，就是带着相机满校园找猫拍。"
    },
    {
        "id": "personal_02_story",
        "text": "有一次，我听说图书馆后面有一只橘猫，找了整整一下午也没等到。后来才知道，它常出没的时间是清晨，而这条信息，藏在某个微信群的聊天记录里，已经是一周前的消息了。那一刻我突然意识到：校园里的信息一直都在，但它们散落、过期、找不到。猫就在校园里，我却不知道它在哪。"
    },
    {
        "id": "personal_03_motivation",
        "text": "于是我做了\u201c此刻校园\u201d。我用TRAE IDE从零开始开发了整个产品——从数据库设计到前端界面，从AI搜索到协同验证，每一行代码都有TRAE的参与。把校园信息和地点、时间绑定，让每一条信息都有坐标、有时效、有人验证。从一个人追着猫跑，到想让整个校园的人都能分享此刻——这就是我做这个项目的初衷。"
    },
    {
        "id": "personal_04_declaration",
        "text": "校园信息每天都在产生，也在每天消失。我不想等到毕业才做这件事。让校园里的每一刻，都有坐标。"
    },
]


# ============================================================
# 方式 A：DashScope SDK（WebSocket，输出 MP3）
# ============================================================

def generate_with_sdk(text: str, voice: str, output_path: Path) -> bool:
    """使用 DashScope SDK 生成语音（返回音频字节，输出 MP3）"""
    try:
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
    except ImportError:
        print("    [SDK] dashscope 未安装，跳过此方式")
        return False

    dashscope.api_key = API_KEY
    dashscope.base_websocket_api_url = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

    try:
        synthesizer = SpeechSynthesizer(model=MODEL, voice=voice)
        audio_data = synthesizer.call(text)

        if not audio_data:
            print("    [SDK] 返回空数据")
            return False

        # SDK 默认输出 MP3
        output_file = output_path.with_suffix(".mp3")
        with open(output_file, "wb") as f:
            f.write(audio_data)

        file_size = len(audio_data)
        print(f"    [SDK] 成功: {output_file.name} ({file_size / 1024:.1f} KB)")
        return True

    except Exception as e:
        print(f"    [SDK] 失败: {e}")
        return False


# ============================================================
# 方式 B：HTTP REST API（返回 URL，输出 WAV）
# ============================================================

def generate_with_rest(text: str, voice: str, output_path: Path) -> bool:
    """使用 HTTP REST API 生成语音（返回音频 URL，输出 WAV）"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "input": {
            "text": text,
            "voice": voice,
            "format": "wav",
            "sample_rate": 24000,
        }
    }

    try:
        response = requests.post(REST_API_URL, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            print(f"    [REST] HTTP {response.status_code}: {response.text[:200]}")
            return False

        result = response.json()

        # 解析返回的音频 URL（可能有多种格式）
        audio_url = None
        try:
            audio_url = result["output"]["audio"]["url"]
        except (KeyError, TypeError):
            audio_url = result.get("output", {}).get("audio", {}).get("url")

        if not audio_url:
            print(f"    [REST] 未获取到音频URL: {json.dumps(result, ensure_ascii=False)[:300]}")
            return False

        # 下载音频文件
        audio_response = requests.get(audio_url, timeout=60)
        if audio_response.status_code != 200:
            print(f"    [REST] 下载失败: {audio_response.status_code}")
            return False

        output_file = output_path.with_suffix(".wav")
        with open(output_file, "wb") as f:
            f.write(audio_response.content)

        file_size = len(audio_response.content)
        print(f"    [REST] 成功: {output_file.name} ({file_size / 1024:.1f} KB)")
        return True

    except Exception as e:
        print(f"    [REST] 失败: {e}")
        return False


# ============================================================
# 统一生成函数（先试 SDK，失败再试 REST）
# ============================================================

def generate_tts(text: str, voice: str, item_id: str) -> bool:
    """生成单段语音：优先 SDK，失败后回退 REST API"""
    output_path = OUTPUT_DIR / item_id

    print(f"  正在生成: {item_id}")
    print(f"  文本前30字: {text[:30]}...")

    # 方式 A：SDK
    ok = generate_with_sdk(text, voice, output_path)
    if ok:
        return True

    # 方式 B：REST API
    print("    切换到 REST API 方式...")
    ok = generate_with_rest(text, voice, output_path)
    return ok


def batch_generate(narrations: list, voice: str, prefix: str) -> int:
    """批量生成旁白，返回成功数"""
    print(f"\n{'=' * 60}")
    print(f"开始生成 {prefix} 旁白（共 {len(narrations)} 段）")
    print(f"模型: {MODEL}")
    print(f"音色: {voice}")
    print(f"{'=' * 60}")

    success_count = 0
    for i, item in enumerate(narrations, 1):
        print(f"\n[{i}/{len(narrations)}] {item['id']}")
        ok = generate_tts(item["text"], voice, item["id"])
        if ok:
            success_count += 1
        else:
            print(f"  !! 该段生成失败，可稍后单独重试")

        # 避免 RPM 超限（180/分钟），每段间隔 0.5 秒
        time.sleep(0.5)

    print(f"\n{prefix} 完成: {success_count}/{len(narrations)} 段成功")
    return success_count


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("此刻校园 - 视频旁白 AI 语音生成")
    print(f"模型: {MODEL}")
    print(f"输出目录: {OUTPUT_DIR.absolute()}")
    print("=" * 60)

    # 检查 dashscope SDK 是否安装
    try:
        import dashscope
        from importlib.metadata import version as get_version
        sdk_ver = get_version("dashscope")
        print(f"dashscope SDK 版本: {sdk_ver}")
        print("主调用方式: SDK (WebSocket, MP3)")
    except ImportError:
        print("dashscope SDK 未安装，将使用 REST API 方式")
        print("安装 SDK: pip install dashscope")

    # 统计字数和费用
    demo_chars = sum(len(item["text"]) for item in DEMO_NARRATIONS)
    personal_chars = sum(len(item["text"]) for item in PERSONAL_NARRATIONS)
    total_chars = demo_chars + personal_chars
    estimated_cost = total_chars * 1.4 / 10000

    print(f"\n作品演示视频旁白: {len(DEMO_NARRATIONS)} 段, {demo_chars} 字")
    print(f"个人介绍视频旁白: {len(PERSONAL_NARRATIONS)} 段, {personal_chars} 字")
    print(f"总计: {total_chars} 字, 预估费用 ¥{estimated_cost:.2f}")
    print(f"定价: ¥1.4/万字符")

    print("\n按回车开始生成（Ctrl+C 取消）...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(0)

    # 生成作品演示视频旁白
    demo_ok = batch_generate(DEMO_NARRATIONS, VOICE_DEMO, "作品演示视频")

    # 生成个人介绍视频旁白
    personal_ok = batch_generate(PERSONAL_NARRATIONS, VOICE_PERSONAL, "个人介绍视频")

    # 汇总
    total_ok = demo_ok + personal_ok
    total_segments = len(DEMO_NARRATIONS) + len(PERSONAL_NARRATIONS)

    print(f"\n{'=' * 60}")
    print(f"全部完成！")
    print(f"作品演示视频: {demo_ok}/{len(DEMO_NARRATIONS)} 段成功")
    print(f"个人介绍视频: {personal_ok}/{len(PERSONAL_NARRATIONS)} 段成功")
    print(f"总计: {total_ok}/{total_segments} 段成功")
    print(f"音频文件保存在: {OUTPUT_DIR.absolute()}")
    print(f"{'=' * 60}")

    if total_ok < total_segments:
        print(f"\n提示：有 {total_segments - total_ok} 段未成功，可重新运行脚本")
        print("已生成的段会跳过（检查文件是否存在）")

    print(f"\n下一步：在剪映中导入音频文件，与视频画面对齐")
    print(f"如需调整语速，可在剪映中使用\u201c变速\u201d功能（0.8x-1.2x）")
