// 统一环境配置：通过构建标记 __ENV__ 区分 dev / experience / prod；未定义时默认 prod
declare const __ENV__: string | undefined
const ENV = (typeof __ENV__ !== 'undefined' && __ENV__) || 'prod'

const HOSTS: Record<string, { api: string; image: string }> = {
  dev: { api: 'http://localhost:8000', image: 'http://localhost:8000' },
  experience: { api: 'https://campus.chaina1.com', image: 'https://campus.chaina1.com' },
  prod: { api: 'https://campus.chaina1.com', image: 'https://campus.chaina1.com' },
}

const cfg = HOSTS[ENV] || HOSTS.prod
export const API_HOST = cfg.api
export const IMAGE_HOST = cfg.image
export const BASE_URL = `${API_HOST}/api/v1`