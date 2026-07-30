export function formatDate(dateStr: string | Date, format: string = 'relative'): string {
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

  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function formatCount(count: number): string {
  if (count < 1000) return String(count)
  if (count < 10000) return `${(count / 1000).toFixed(1)}k`
  return `${(count / 10000).toFixed(1)}w`
}

export function truncateText(text: string, maxLength: number = 100): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

export function getRemainingTime(expiresAt: string): string {
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
