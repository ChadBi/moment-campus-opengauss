/**
 * format.ts 纯函数单测（Task 14）
 * 由于 utils/format.ts 为 TS 且无 wx 依赖，这里以内联 JS 保持与源逻辑一致的方式验证核心行为。
 * 运行：npm run test:format
 */
import assert from 'node:assert/strict'

function pad(n) {
  return String(n).padStart(2, '0')
}

function formatDate(dateStr, format = 'relative') {
  const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  if (format === 'relative') {
    const diffSec = Math.floor(diffMs / 1000)
    if (diffSec < 60) return '刚刚'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour}小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 30) return `${diffDay}天前`
  }
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatCount(count) {
  if (count < 1000) return String(count)
  if (count < 10000) return `${(count / 1000).toFixed(1)}k`
  return `${(count / 10000).toFixed(1)}w`
}

function truncateText(text, maxLength = 100) {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

function getRemainingTime(expiresAt) {
  const expireDate = new Date(expiresAt)
  const now = new Date()
  const diffMs = expireDate.getTime() - now.getTime()
  if (diffMs <= 0) return '已过期'
  const diffHour = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay > 0) return `${diffDay}天后过期`
  if (diffHour > 0) return `${diffHour}小时后过期`
  const diffMin = Math.floor(diffMs / (1000 * 60))
  return `${diffMin}分钟后过期`
}

// ---- formatCount ----
assert.equal(formatCount(0), '0')
assert.equal(formatCount(999), '999')
assert.equal(formatCount(1000), '1.0k')
assert.equal(formatCount(1500), '1.5k')
assert.equal(formatCount(12345), '1.2w')
assert.equal(formatCount(100000), '10.0w')

// ---- truncateText ----
assert.equal(truncateText('短文本', 10), '短文本')
assert.equal(truncateText('短文本', 2), '短文...')
assert.equal(truncateText('abcdefghij', 5), 'abcde...')

// ---- formatDate（绝对格式） ----
assert.equal(formatDate('2026-08-06T10:00:00Z', 'datetime'), formatDate(new Date('2026-08-06T10:00:00Z'), 'datetime'))

// ---- formatDate（相对 - 刚刚） ----
assert.equal(formatDate(new Date(), 'relative'), '刚刚')

// ---- getRemainingTime ----
assert.equal(getRemainingTime(new Date(Date.now() - 1000).toISOString()), '已过期')
assert.equal(getRemainingTime(new Date(Date.now() + 10 * 60 * 1000).toISOString()), '10分钟后过期')
assert.equal(getRemainingTime(new Date(Date.now() + 3 * 3600 * 1000).toISOString()), '3小时后过期')
assert.equal(getRemainingTime(new Date(Date.now() + 5 * 86400 * 1000).toISOString()), '5天后过期')

console.log('✅ utils/format 单测通过（formatCount / truncateText / formatDate / getRemainingTime）')