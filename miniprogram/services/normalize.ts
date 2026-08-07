import type {
  Comment,
  LocationItem,
  LocationSummary,
  Notification,
  Post,
  PostImage,
  SearchResult,
  School,
  SchoolMembership,
  Subscription,
  Topic,
} from '../types'
import { resolveAvatar, resolveImageUrl } from './request'

const SCHOOL_DEFAULTS: Record<string, { lat: number; lng: number; zoom: number }> = {
  jiangnan: { lat: 31.483652, lng: 120.27116, zoom: 16 },
  fudan: { lat: 31.298886, lng: 121.501843, zoom: 15 },
  zju: { lat: 30.30895, lng: 120.086, zoom: 15 },
}

function numberOr(value: unknown, fallback: number): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function normalizeSchool(raw: any, fallbackCode = 'jiangnan'): School {
  const code = String(raw?.code || fallbackCode)
  const defaults = SCHOOL_DEFAULTS[code] || SCHOOL_DEFAULTS.jiangnan
  return {
    id: numberOr(raw?.id, 0),
    code,
    name: String(raw?.name || code),
    logo_url: raw?.logo_url ? resolveImageUrl(raw.logo_url) : undefined,
    description: raw?.description,
    province: raw?.province,
    city: raw?.city,
    center_lat: numberOr(raw?.center_lat, defaults.lat),
    center_lng: numberOr(raw?.center_lng, defaults.lng),
    map_zoom: numberOr(raw?.map_zoom, defaults.zoom),
    is_active: raw?.is_active !== false,
    domains: Array.isArray(raw?.domains) ? raw.domains.map(String) : [],
  }
}

export function normalizeMembership(raw: any): SchoolMembership {
  const schoolRaw = raw?.school || raw?.school_info
  return {
    id: numberOr(raw?.id, 0),
    user_id: numberOr(raw?.user_id, 0),
    school_id: numberOr(raw?.school_id || schoolRaw?.id, 0),
    school: schoolRaw ? normalizeSchool(schoolRaw) : undefined,
    role: raw?.role || 'member',
    status: raw?.status || 'active',
    is_default: raw?.is_default,
    joined_at: raw?.joined_at || raw?.created_at || '',
  }
}

function normalizeImage(raw: any): PostImage {
  if (typeof raw === 'string') return { image_url: resolveImageUrl(raw) }
  return {
    image_url: resolveImageUrl(raw?.image_url || raw?.url || ''),
    thumbnail_url: raw?.thumbnail_url ? resolveImageUrl(raw.thumbnail_url) : undefined,
  }
}

export function normalizePost(raw: any): Post {
  const authorRaw = raw?.author || {}
  const categoryRaw = raw?.category || (raw?.category_id ? { id: raw.category_id, name: raw.category_name } : null)
  const locationRaw = raw?.location || (raw?.location_id ? {
    id: raw.location_id,
    name: raw.location_name,
    latitude: raw.location_lat,
    longitude: raw.location_lng,
  } : null)
  const images = Array.isArray(raw?.images)
    ? raw.images.map(normalizeImage).filter((item: PostImage) => item.image_url)
    : []
  const cover = raw?.cover_image || images[0]?.thumbnail_url || images[0]?.image_url || ''
  const governance = raw?.governance
    ? {
      ...raw.governance,
      valid_count: numberOr(raw.governance.valid_count, numberOr(raw?.valid_count, 0)),
      invalid_count: numberOr(raw.governance.invalid_count, numberOr(raw?.invalid_count, 0)),
    }
    : null
  return {
    id: numberOr(raw?.id, 0),
    title: String(raw?.title || ''),
    content: String(raw?.content || ''),
    cover_image: resolveImageUrl(cover),
    images,
    location_id: raw?.location_id ?? locationRaw?.id ?? null,
    location_name: raw?.location_name || locationRaw?.name,
    location_lat: raw?.location_lat ?? locationRaw?.latitude,
    location_lng: raw?.location_lng ?? locationRaw?.longitude,
    category_id: numberOr(raw?.category_id || categoryRaw?.id, 0),
    status: raw?.status || 'published',
    is_anonymous: raw?.is_anonymous === true,
    contact_info: raw?.contact_info ?? null,
    lost_type: raw?.lost_type ?? null,
    school_id: numberOr(raw?.school_id, 0),
    school_name: raw?.school_name,
    author: {
      id: numberOr(authorRaw?.id || raw?.author_id, 0),
      nickname: String(authorRaw?.nickname || raw?.author_nickname || '校园用户'),
      avatar_url: resolveAvatar(authorRaw?.avatar_url || raw?.author_avatar),
      is_verified: authorRaw?.is_verified ?? raw?.is_verified,
    },
    category: categoryRaw ? {
      id: numberOr(categoryRaw.id, 0),
      name: String(categoryRaw.name || ''),
      icon: categoryRaw.icon,
    } : null,
    location: locationRaw ? {
      id: numberOr(locationRaw.id, 0),
      name: String(locationRaw.name || ''),
      latitude: numberOr(locationRaw.latitude, 0),
      longitude: numberOr(locationRaw.longitude, 0),
      building: locationRaw.building,
      floor: locationRaw.floor,
      is_verified: locationRaw.is_verified,
    } : null,
    like_count: numberOr(raw?.like_count, 0),
    comment_count: numberOr(raw?.comment_count, 0),
    view_count: numberOr(raw?.view_count, 0),
    valid_count: numberOr(raw?.valid_count, numberOr(governance?.valid_count, 0)),
    invalid_count: numberOr(raw?.invalid_count, numberOr(governance?.invalid_count, 0)),
    expire_at: raw?.expire_at ?? null,
    created_at: raw?.created_at || '',
    updated_at: raw?.updated_at || raw?.created_at || '',
    is_liked: raw?.is_liked === true,
    governance,
    is_verified: raw?.is_verified ?? authorRaw?.is_verified,
    recommend_reason: raw?.reason || raw?.recommend_reason,
    recommend_score: raw?.score,
  }
}

export function normalizePostList(raw: any): { items: Post[]; total: number; page: number; page_size: number; has_more: boolean; total_pages?: number; mode?: { personalized?: boolean; reason_code?: string } | null } {
  const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : [])
  return {
    items: items.map(normalizePost),
    total: numberOr(raw?.total, items.length),
    page: numberOr(raw?.page, 1),
    page_size: numberOr(raw?.page_size, items.length || 20),
    has_more: raw?.has_more === true,
    total_pages: raw?.total_pages,
    mode: raw?.mode || null,
  }
}

export function normalizeLocation(raw: any): LocationItem {
  return {
    id: numberOr(raw?.id, 0),
    school_id: numberOr(raw?.school_id, 0),
    name: String(raw?.name || ''),
    description: raw?.description,
    latitude: numberOr(raw?.latitude, 0),
    longitude: numberOr(raw?.longitude, 0),
    floor: raw?.floor,
    building: raw?.building,
    post_count: numberOr(raw?.post_count, 0),
    is_verified: raw?.is_verified === true,
    avg_score: numberOr(raw?.avg_score, 0),
    rating_count: numberOr(raw?.rating_count, 0),
    review_count: numberOr(raw?.review_count, 0),
  }
}

export function normalizeLocationSummary(raw: any): LocationSummary {
  const claims = Array.isArray(raw?.claims) ? raw.claims : []
  const conflicts = Array.isArray(raw?.conflicts) ? raw.conflicts : []
  const sources = Array.isArray(raw?.sources) ? raw.sources : []
  return {
    id: raw?.id ?? null,
    version: raw?.version ?? null,
    status: raw?.status || 'insufficient',
    summary_text: raw?.summary_text ?? null,
    confidence_level: raw?.confidence_level || 'insufficient',
    claims: claims.map((claim: any, index: number) => ({
      claim_id: String(claim?.claim_id || `claim-${index + 1}`),
      text: String(claim?.text || ''),
      confidence_level: String(claim?.confidence_level || raw?.confidence_level || 'insufficient'),
      source_refs: Array.isArray(claim?.source_refs) ? claim.source_refs.map((ref: any) => ({
        source_type: String(ref?.source_type || ''),
        source_id: numberOr(ref?.source_id, 0),
      })) : [],
    })),
    conflicts: conflicts.map((conflict: any) => ({
      text: String(conflict?.text || ''),
      source_refs: Array.isArray(conflict?.source_refs) ? conflict.source_refs.map((ref: any) => ({
        source_type: String(ref?.source_type || ''),
        source_id: numberOr(ref?.source_id, 0),
      })) : [],
    })),
    source_count: numberOr(raw?.source_count, sources.length),
    generated_at: raw?.generated_at ?? null,
    stale_at: raw?.stale_at ?? null,
    sources: sources.map((source: any) => ({
      source_type: String(source?.source_type || ''),
      source_id: numberOr(source?.source_id, 0),
      title: source?.title,
      snippet: source?.snippet,
      created_at: source?.created_at,
      author_name: source?.author_name,
      score: source?.score,
      confirmation_count: numberOr(source?.confirmation_count, 0),
      refutation_count: numberOr(source?.refutation_count, 0),
    })),
  }
}

export function normalizeNotification(raw: any): Notification {
  return {
    id: numberOr(raw?.id, 0),
    type: raw?.type || 'system',
    title: String(raw?.title || ''),
    content: String(raw?.content || ''),
    target_type: raw?.target_type,
    target_id: raw?.target_id ?? null,
    actor_name: raw?.actor_name,
    actor_avatar: raw?.actor_avatar ? resolveAvatar(raw.actor_avatar) : undefined,
    is_read: raw?.is_read === true,
    created_at: raw?.created_at || '',
  }
}

export function normalizeSubscription(raw: any): Subscription {
  return {
    id: numberOr(raw?.id, 0),
    target_type: raw?.target_type || 'category',
    target_id: numberOr(raw?.target_id, 0),
    target_name: raw?.target_name || raw?.name,
    created_at: raw?.created_at || '',
  }
}

export function normalizeComment(raw: any): Comment {
  const authorRaw = raw?.author || {}
  return {
    id: numberOr(raw?.id, 0),
    post_id: numberOr(raw?.post_id, 0),
    parent_id: raw?.parent_id ?? null,
    reply_to_user_id: raw?.reply_to_user_id ?? null,
    reply_to_user: raw?.reply_to_user ? {
      id: numberOr(raw.reply_to_user.id, 0),
      nickname: String(raw.reply_to_user.nickname || ''),
      avatar_url: resolveAvatar(raw.reply_to_user.avatar_url),
      is_verified: raw.reply_to_user.is_verified,
    } : null,
    user_id: numberOr(raw?.user_id || authorRaw?.id, 0),
    content: String(raw?.content || ''),
    author: {
      id: numberOr(authorRaw?.id || raw?.user_id, 0),
      nickname: String(authorRaw?.nickname || raw?.author_nickname || '校园用户'),
      avatar_url: resolveAvatar(authorRaw?.avatar_url || raw?.author_avatar),
      is_verified: authorRaw?.is_verified ?? raw?.is_verified,
    },
    replies: Array.isArray(raw?.replies) ? raw.replies.map(normalizeComment) : [],
    reply_count: numberOr(raw?.reply_count, Array.isArray(raw?.replies) ? raw.replies.length : 0),
    created_at: raw?.created_at || '',
    updated_at: raw?.updated_at,
  }
}

export function normalizeSearchResult(raw: any): SearchResult {
  const list = normalizePostList(raw)
  return {
    ...list,
    match_reasons: raw?.match_reasons,
    scores: raw?.scores,
    fallback: raw?.fallback === true,
    fallback_reason: raw?.fallback_reason,
    intent: raw?.intent,
  }
}

export function normalizeTopic(raw: any): Topic {
  return {
    id: numberOr(raw?.id, 0),
    title: String(raw?.title || raw?.name || ''),
    description: raw?.description,
    cover_url: raw?.cover_url ? resolveImageUrl(raw.cover_url) : undefined,
    post_count: numberOr(raw?.post_count, 0),
    view_count: numberOr(raw?.view_count, 0),
    is_featured: raw?.is_featured,
    sort_order: raw?.sort_order,
  }
}
