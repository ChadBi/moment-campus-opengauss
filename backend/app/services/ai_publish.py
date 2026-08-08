"""AI-03.1: AI 辅助发布建议服务。

职责：
1. 输入校验：标题/内容长度（schema 已强制）+ 敏感信息确定性检测（手机/邮箱/身份证/银行卡）
2. 三校隔离：school_id 强制取自 TenantContext；分类白名单只来自当前学校
3. 模型调用：调用 invoke_ai（PUBLISH_SUGGESTION_SCHEMA 约束）→ 白名单校验分类，并返回标题/正文优化建议
4. 确定性敏感检测：正则匹配手机/邮箱/身份证/银行卡 → 落 sensitive_warnings + sensitive_findings
5. 缺失字段检测：根据草稿字段空缺情况生成 missing_info（不调模型）
6. 日志记录：通过 invoke_ai 自动记录 ai_invocation_logs（成功/失败均记录）
7. 降级：AI 失败 / 输入过短 → fallback=true，仍返回敏感检测结果（确定性，不依赖模型）

安全约束：
- 不修改原文：本服务只生成"建议"，标题/正文优化结果也必须由用户主动采纳
- 不改坐标/状态：不修改 location_id / status / 任何 Post 字段
- 不自动过审：本服务不调用状态机，不参与审核流程
- 失败不阻塞：fallback=true 时仍返回可用的敏感检测结果，前端可继续手动发布
- 三校隔离：school_id 强制取自 TenantContext；分类白名单只来自当前学校
- 提示词只含当前学校的分类白名单，不引用其他学校地点或词表

Task 1.3 调整：Tag 模型已删除，AI 发布建议不再加载标签白名单；
AIPublishSuggestions.tags 字段保留为空列表（向后兼容 API 响应结构）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import OUTPUT_STATUS_SUCCESS
from app.ai.provider import AIInvokeOptions, AIProvider
from app.ai.schemas import PUBLISH_SUGGESTION_SCHEMA
from app.ai.service import invoke_ai, update_invocation_result
from app.core.tenant import TenantContext
from app.models.category import Category
from app.models.user import User
from app.schemas.ai import (
    AIPublishSuggestRequest,
    AIPublishSuggestionResponse,
    AIPublishSuggestions,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================
# 输入过短的阈值（标题或内容过短时 AI 难以给出有用建议，降级为仅敏感检测）
_MIN_TITLE_LEN_FOR_AI = 3
_MIN_CONTENT_LEN_FOR_AI = 5

# AI 建议的默认信息截止天数上限（防止模型给出过大值）
_MAX_VALIDITY_DAYS = 365

# 敏感信息检测正则（确定性，不依赖模型）
# 注：以下正则仅做基础检测，生产环境应接入专门的内容安全服务
_SENSITIVE_PATTERNS: dict[str, list[re.Pattern]] = {
    "phone": [
        # 中国大陆 11 位手机号（1 开头）
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        # 座机：区号-号码（如 0510-8888888 / 010-12345678）
        re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)"),
        # 400/800 客服电话
        re.compile(r"(?<!\d)[48]00-?\d{3}-?\d{4}(?!\d)"),
    ],
    "email": [
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    ],
    "id_card": [
        # 18 位身份证号（最后一位可能是 X）
        re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
        # 15 位老式身份证号
        re.compile(r"(?<!\d)\d{15}(?!\d)"),
    ],
    "bank_card": [
        # 16-19 位银行卡号
        re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
    ],
    "qq": [
        # QQ 号（5-12 位数字，以 1-9 开头）
        re.compile(r"(?<!\d)[1-9]\d{4,11}(?!\d)"),
    ],
}

# 敏感类型中文描述
_SENSITIVE_TYPE_LABELS: dict[str, str] = {
    "phone": "手机/电话号码",
    "email": "邮箱地址",
    "id_card": "身份证号",
    "bank_card": "银行卡号",
    "qq": "QQ 号",
}


# ============================================================
# 数据结构
# ============================================================
@dataclass
class _SensitiveResult:
    """敏感信息检测结果。"""

    warnings: list[str]
    findings: dict[str, list[str]]


# ============================================================
# 1. 确定性敏感信息检测（不依赖模型）
# ============================================================
def detect_sensitive_info(text: str) -> _SensitiveResult:
    """确定性敏感信息检测：手机/邮箱/身份证/银行卡/QQ。

    Args:
        text: 待检测的文本（标题 + 内容 + 联系方式）

    Returns:
        _SensitiveResult：warnings（人类可读提示列表）+ findings（type→[matched...] 明细）
    """
    if not text:
        return _SensitiveResult(warnings=[], findings={})

    warnings: list[str] = []
    findings: dict[str, list[str]] = {}

    for stype, patterns in _SENSITIVE_PATTERNS.items():
        matched_set: set[str] = set()
        for pattern in patterns:
            for m in pattern.finditer(text):
                matched_set.add(m.group(0))
        if matched_set:
            matched_list = sorted(matched_set)
            label = _SENSITIVE_TYPE_LABELS.get(stype, stype)
            # warnings 文案：避免在提示中重复完整敏感值，仅展示前 4 位 + ***
            preview = "、".join(_mask_value(v) for v in matched_list[:3])
            warnings.append(f"检测到{label}：{preview}（共 {len(matched_list)} 处）")
            findings[stype] = matched_list

    return _SensitiveResult(warnings=warnings, findings=findings)


def _mask_value(value: str) -> str:
    """对敏感值做部分掩码（保留前 3 位 + ***）。"""
    if len(value) <= 4:
        return value[:2] + "***"
    return value[:3] + "***" + value[-2:]


# ============================================================
# 2. 缺失字段检测（不依赖模型）
# ============================================================
def _detect_missing_info(request: AIPublishSuggestRequest) -> list[str]:
    """根据草稿字段空缺情况生成遗漏信息提示（不调用模型）。

    检查项：
    - 标题是否为空 / 过短
    - 内容是否为空 / 过短
    - 分类是否已选
    - 地点是否已选
    - 信息截止时间是否已设置
    - 失物招领类是否设置了 lost_type 与联系方式
    """
    missing: list[str] = []

    title = (request.title or "").strip()
    content = (request.content or "").strip()

    if not title:
        missing.append("标题为空，建议补充简洁明确的标题（5-100 字符）")
    elif len(title) < 5:
        missing.append("标题过短，建议补充更多关键词便于搜索")

    if not content:
        missing.append("正文内容为空，建议补充详细信息（时间/地点/对象/经过）")
    elif len(content) < 10:
        missing.append("正文内容过短，建议补充时间、地点、对象、经过等关键信息")

    if request.category_id is None:
        missing.append("未选择分类，分类影响默认信息截止天数与展示位置")

    if request.location_id is None and not request.contact_info:
        # 没有地点且没有联系方式时提示
        missing.append("未选择地点，建议补充具体地点便于定位")

    if request.expire_at is None:
        missing.append("未设置信息截止时间，将使用分类默认信息截止天数")

    # 失物招领类检查
    if request.lost_type is not None and not request.contact_info:
        missing.append("失物招领类信息建议补充联系方式（可设置匿名）")

    return missing


# ============================================================
# 3. 三校隔离：加载当前学校的分类白名单
# ============================================================
async def _load_whitelists(
    db: AsyncSession,
    school_id: int,
) -> list[Category]:
    """加载当前学校的分类白名单（用于提示词与解析后校验）。

    Task 1.3 调整：Tag 模型已删除，不再加载标签白名单，仅返回分类列表。

    Returns:
        categories：当前学校启用的分类列表
    """
    cat_result = await db.execute(
        select(Category)
        .where(Category.school_id == school_id, Category.is_active == True)
        .order_by(Category.sort_order, Category.id)
    )
    return list(cat_result.scalars().all())


# ============================================================
# 4. 提示词构造
# ============================================================
def _build_prompt(
    request: AIPublishSuggestRequest,
    categories: list[Category],
) -> str:
    """构造模型提示词。

    提示词包含：
    - 任务说明（返回严格 JSON）
    - 当前学校可用的分类白名单（防止模型编造不存在的分类）
    - 草稿原文（标题/正文/当前已选字段）
    - 重要约束（不修改原文 / 只返回建议 / 分类必须来自白名单 / 优化不得新增事实）

    Task 1.3 调整：Tag 模型已删除，提示词不再展示标签白名单；
    模型仍可在 suggestions.tags 中返回数组（保持 schema 兼容），
    但 service 层会忽略该字段并恒定返回空数组。
    """
    cat_list = (
        "、".join(f"{c.name}（code={c.code}，默认信息截止天数={c.default_validity_days}天）" for c in categories[:30])
        or "（暂无分类）"
    )

    # 当前已选字段（仅展示，不要求模型沿用）
    current_fields: list[str] = []
    if request.category_id is not None:
        cat = next((c for c in categories if c.id == request.category_id), None)
        if cat is not None:
            current_fields.append(f"当前已选分类：{cat.name}")
    if request.lost_type:
        current_fields.append(f"失物类型：{request.lost_type}")
    current_block = "\n".join(f"- {f}" for f in current_fields) or "- （用户未选择任何字段）"

    return f"""你是校园信息发布助手。请基于用户草稿给出"结构化建议"，但不直接修改用户草稿。

# 任务
分析用户草稿，给出 JSON 建议，字段如下：
{{
  "suggestions": {{
    "title": "建议标题（仅在原文标题较弱或不规范时给出；原文标题已合适则填 null）",
    "optimized_title": "优化后的标题（只改善清晰度、准确性和可读性，不改变事实；无需优化则填 null）",
    "optimized_content": "优化后的正文（只改善结构、语句和可读性，不添加草稿中不存在的事实；无需优化则填 null）",
    "category": "建议分类名（必须从下方分类白名单中选取；用户当前已选合适则填 null）",
    "tags": ["建议标签（最多 5 个；无建议则空数组）"],
    "default_validity_days": 建议默认信息截止天数（整数 1-365；来自分类配置或常见场景）
  }},
  "missing_info": ["遗漏的关键信息（1-5 条简短说明，如缺少时间/地点/联系方式/物品特征等）"],
  "sensitive_warnings": ["敏感信息提醒（如检测到手机号/身份证/银行卡等；无则空数组）"]
}}

# 重要约束
1. category 必须从下方分类白名单中选取，不得编造不存在的分类
2. title 字段保留兼容旧版；optimized_title 和 optimized_content 只能基于草稿润色，不得新增、删除或推断事实
3. 原文已经清晰完整时，optimized_title 和 optimized_content 填 null
4. 不引用其他学校的地点、词表、分类
5. missing_info 与 sensitive_warnings 可空数组
6. 只返回 JSON，不要任何额外文字

# 上下文
- 当前学校可用分类：{cat_list}
- 当前草稿已选字段：
{current_block}

# 用户草稿
标题：{request.title or "（空）"}
正文：
{request.content or "（空）"}
"""


# ============================================================
# 5. 白名单校验
# ============================================================
def _validate_suggestions(
    parsed: dict[str, Any],
    categories: list[Category],
    request: AIPublishSuggestRequest,
) -> tuple[AIPublishSuggestions, list[str], list[str]]:
    """对模型解析结果做白名单校验，并构造最终建议对象。

    校验规则：
    - title：截断 200 字符；兼容旧版建议字段
    - optimized_title：截断 200 字符；只保留模型返回的非空优化结果
    - optimized_content：截断 5000 字符；只保留模型返回的非空优化结果
    - summary：截断 200 字符
    - category：必须在白名单中（按 name 或 code 匹配）；非法值置空
    - tags：Task 1.3 后恒定返回空列表（Tag 模型已删除，schema 字段保留向后兼容）
    - default_validity_days：限定 1-365；超出范围回退到当前分类默认值

    Returns:
        (suggestions, missing_info, sensitive_warnings)
    """
    sug_data = parsed.get("suggestions") or {}
    if not isinstance(sug_data, dict):
        sug_data = {}

    # ---- title ----
    title_sug = sug_data.get("title")
    if isinstance(title_sug, str):
        title_sug = title_sug.strip()[:200] or None
    else:
        title_sug = None

    # ---- optimized_title ----
    optimized_title = sug_data.get("optimized_title")
    if isinstance(optimized_title, str):
        optimized_title = optimized_title.strip()[:200] or None
    else:
        optimized_title = None

    # ---- optimized_content ----
    optimized_content = sug_data.get("optimized_content")
    if isinstance(optimized_content, str):
        optimized_content = optimized_content.strip()[:5000] or None
    else:
        optimized_content = None

    # ---- summary ----
    summary_sug = sug_data.get("summary")
    if isinstance(summary_sug, str):
        summary_sug = summary_sug.strip()[:200] or None
    else:
        summary_sug = None

    # ---- category 白名单校验 ----
    category_name: Optional[str] = None
    category_id: Optional[int] = None
    raw_category = sug_data.get("category")
    if isinstance(raw_category, str) and raw_category.strip():
        cleaned = raw_category.strip()
        matched = next(
            (c for c in categories if c.name == cleaned or c.code == cleaned),
            None,
        )
        if matched is not None:
            category_name = matched.name
            category_id = matched.id
        # 非法值直接丢弃（不向用户报错）

    # ---- tags 字段：Task 1.3 后恒定返回空列表（不再校验白名单） ----

    # ---- default_validity_days 校验 ----
    raw_days = sug_data.get("default_validity_days")
    default_validity_days: Optional[int] = None
    if isinstance(raw_days, int) and 1 <= raw_days <= _MAX_VALIDITY_DAYS:
        default_validity_days = raw_days
    elif isinstance(raw_days, str) and raw_days.isdigit():
        days_int = int(raw_days)
        if 1 <= days_int <= _MAX_VALIDITY_DAYS:
            default_validity_days = days_int
    # 回退：当前已选分类的默认信息截止天数
    if default_validity_days is None and request.category_id is not None:
        cat = next((c for c in categories if c.id == request.category_id), None)
        if cat is not None:
            default_validity_days = cat.default_validity_days

    suggestions = AIPublishSuggestions(
        title=title_sug,
        optimized_title=optimized_title,
        optimized_content=optimized_content,
        summary=summary_sug,
        category=category_name,
        category_id=category_id,
        tags=[],
        default_validity_days=default_validity_days,
    )

    # ---- missing_info ----
    missing_raw = parsed.get("missing_info") or []
    if not isinstance(missing_raw, list):
        missing_raw = []
    missing_info = [str(m).strip()[:200] for m in missing_raw if str(m).strip()][:5]

    # ---- sensitive_warnings ----
    sensitive_raw = parsed.get("sensitive_warnings") or []
    if not isinstance(sensitive_raw, list):
        sensitive_raw = []
    sensitive_warnings = [str(s).strip()[:200] for s in sensitive_raw if str(s).strip()][:10]

    return suggestions, missing_info, sensitive_warnings


# ============================================================
# 6. 主入口
# ============================================================
async def execute_publish_suggestion(
    request: AIPublishSuggestRequest,
    tenant: TenantContext,
    db: AsyncSession,
    user: Optional[User] = None,
    trace_id: Optional[str] = None,
    provider: Optional[AIProvider] = None,
) -> AIPublishSuggestionResponse:
    """AI 发布建议主入口。

    流程：
    1. 确定性敏感信息检测（始终执行，不依赖模型）
    2. 缺失字段检测（确定性，不依赖模型）
    3. 加载白名单（当前学校分类）
    4. 输入过短 / 无可建议字段 → fallback（仍返回敏感检测 + 缺失提示）
    5. 否则调用 invoke_ai（PUBLISH_SUGGESTION_SCHEMA 约束）解析建议
    6. 白名单校验分类（非法值丢弃）；tags 字段恒定返回空列表
    7. 任一步失败 → fallback=true，仍返回敏感检测结果（确定性）
    8. 记录 ai_invocation_logs（成功/失败均记录）

    安全约束：
    - 不修改原文：返回的是"建议"，由前端逐项采纳
    - 不改坐标/状态：本服务不修改 Post 任何字段
    - 不自动过审：不调用状态机
    - 失败不阻塞：fallback=true 时仍返回敏感检测 + 缺失提示

    Task 1.3 调整：Tag 模型已删除，不再加载标签白名单；AIPublishSuggestions.tags 恒定为空列表。
    """
    title = (request.title or "").strip()
    content = (request.content or "").strip()
    contact_info = (request.contact_info or "").strip()

    # ---- 1. 确定性敏感信息检测 ----
    sensitive_text = "\n".join([title, content, contact_info])
    sensitive_result = detect_sensitive_info(sensitive_text)

    # ---- 2. 缺失字段检测 ----
    missing_info = _detect_missing_info(request)

    # ---- 3. 加载白名单 ----
    try:
        categories = await _load_whitelists(db, tenant.school_id)
    except Exception as exc:  # noqa: BLE001  DB 异常降级
        logger.warning(
            "ai_publish_load_whitelist_failed school_id=%s err=%s",
            tenant.school_id, exc,
        )
        # DB 失败 → 仅返回确定性结果，不调用模型
        return AIPublishSuggestionResponse(
            suggestions=None,
            missing_info=missing_info,
            sensitive_warnings=sensitive_result.warnings,
            sensitive_findings=sensitive_result.findings,
            fallback=True,
            fallback_reason="AI 服务暂时不可用，已仅返回敏感信息检测结果",
            ai_log_id=None,
        )

    # ---- 4. 输入过短检查 ----
    if len(title) < _MIN_TITLE_LEN_FOR_AI and len(content) < _MIN_CONTENT_LEN_FOR_AI:
        # 输入过短 → 不调用模型，仅返回确定性结果
        return AIPublishSuggestionResponse(
            suggestions=None,
            missing_info=missing_info,
            sensitive_warnings=sensitive_result.warnings,
            sensitive_findings=sensitive_result.findings,
            fallback=True,
            fallback_reason="草稿内容过短，请补充更多内容后再请求 AI 建议",
            ai_log_id=None,
        )

    # ---- 5. 调用模型解析建议 ----
    prompt = _build_prompt(request, categories)
    outcome = await invoke_ai(
        prompt=prompt,
        schema=PUBLISH_SUGGESTION_SCHEMA,
        scene="publish_suggestion",
        tenant=tenant,
        db=db,
        user=user,
        options=AIInvokeOptions(temperature=0.3, max_tokens=1200),
        trace_id=trace_id,
        provider=provider,
    )
    ai_log_id = outcome.log_id

    # ---- 6. 失败降级：仍返回敏感检测 + 缺失提示 ----
    if outcome.fallback or outcome.response is None:
        fallback_reason = outcome.fallback_reason or "AI 服务暂时不可用，已仅返回敏感信息检测结果"
        # 合并模型可能返回的敏感提示（如有）与确定性检测结果
        merged_warnings = list(sensitive_result.warnings)
        if ai_log_id is not None:
            try:
                await update_invocation_result(
                    db, ai_log_id,
                    result_count=0,
                    fallback_reason=fallback_reason,
                )
            except Exception:  # noqa: BLE001  日志更新失败不影响主流程
                logger.warning("update_invocation_result failed ai_log_id=%s", ai_log_id)

        return AIPublishSuggestionResponse(
            suggestions=None,
            missing_info=missing_info,
            sensitive_warnings=merged_warnings,
            sensitive_findings=sensitive_result.findings,
            fallback=True,
            fallback_reason=fallback_reason,
            ai_log_id=ai_log_id,
        )

    # ---- 7. 白名单校验 ----
    try:
        parsed = outcome.response.parsed
        if not isinstance(parsed, dict):
            raise ValueError("parsed suggestion is not a dict")
        suggestions, ai_missing, ai_sensitive = _validate_suggestions(
            parsed, categories, request,
        )
    except Exception as exc:  # noqa: BLE001  校验失败降级
        logger.warning(
            "ai_publish_validate_failed school_id=%s err=%s",
            tenant.school_id, exc,
        )
        fallback_reason = "AI 输出解析失败，已仅返回敏感信息检测结果"
        if ai_log_id is not None:
            try:
                await update_invocation_result(
                    db, ai_log_id,
                    result_count=0,
                    fallback_reason=fallback_reason,
                )
            except Exception:  # noqa: BLE001  日志更新失败不影响主流程
                logger.warning("update_invocation_result failed ai_log_id=%s", ai_log_id)

        return AIPublishSuggestionResponse(
            suggestions=None,
            missing_info=missing_info,
            sensitive_warnings=sensitive_result.warnings,
            sensitive_findings=sensitive_result.findings,
            fallback=True,
            fallback_reason=fallback_reason,
            ai_log_id=ai_log_id,
        )

    # ---- 8. 合并模型输出与确定性结果 ----
    # missing_info：合并确定性检测结果与模型输出，去重保序
    merged_missing = list(missing_info)
    for m in ai_missing:
        if m and m not in merged_missing:
            merged_missing.append(m)
    merged_missing = merged_missing[:8]

    # sensitive_warnings：合并确定性检测结果与模型输出，去重保序
    merged_sensitive = list(sensitive_result.warnings)
    for s in ai_sensitive:
        if s and s not in merged_sensitive:
            merged_sensitive.append(s)
    merged_sensitive = merged_sensitive[:10]

    # ---- 9. 更新日志 result_count ----
    if ai_log_id is not None:
        try:
            # result_count：建议项数（兼容旧建议，并统计标题/正文优化结果）
            suggestion_count = sum(
                1 for v in (
                    suggestions.title,
                    suggestions.optimized_title,
                    suggestions.optimized_content,
                    suggestions.summary,
                    suggestions.category_id,
                    suggestions.tags,
                    suggestions.default_validity_days,
                ) if v
            )
            await update_invocation_result(
                db, ai_log_id,
                result_count=suggestion_count,
            )
        except Exception:  # noqa: BLE001  日志更新失败不影响主流程
            logger.warning("update_invocation_result failed ai_log_id=%s", ai_log_id)

    return AIPublishSuggestionResponse(
        suggestions=suggestions,
        missing_info=merged_missing,
        sensitive_warnings=merged_sensitive,
        sensitive_findings=sensitive_result.findings,
        fallback=False,
        fallback_reason=None,
        ai_log_id=ai_log_id,
    )
