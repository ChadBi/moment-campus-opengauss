// 统一环境配置：优先使用构建标记 __ENV__，否则按微信运行版本自动选择：
// 开发者工具=本地，体验版=线上体验，正式版=线上生产。
declare const __ENV__: string | undefined

export type MiniProgramEnv = 'dev' | 'experience' | 'prod'

// 真机调试时手机无法访问电脑的 localhost，开发环境统一走当前电脑的局域网地址。
// ⚠️ 如果你换了 Wi-Fi / 网段，必须同时改 3 处（否则小程序 AI Skills 里的图片/请求仍然连 localhost 真机失败）：
//   1. miniprogram/config/env.ts              → DEV_LAN_HOST
//   2. miniprogram/skills/moment-campus/utils/util.js    → DEV_LAN_HOST 常量（resolveImageUrl 拼接 /uploads/）
//   3. miniprogram/skills/moment-campus/utils/request.js → DEV_LAN_HOST 常量（BASE_URL 拼接）
// 一键查本机局域网 IP：Get-NetIPAddress -AddressFamily IPv4 | ? IPAddress -notlike '127.*' | ? IPAddress -notlike '169.254.*' | select InterfaceAlias,IPAddress
const DEV_LAN_HOST = '192.168.3.10'

const HOSTS: Record<MiniProgramEnv, { api: string; image: string }> = {
  dev: { api: `http://${DEV_LAN_HOST}:8000`, image: `http://${DEV_LAN_HOST}:8000` },
  experience: { api: 'https://campus.chaina1.com', image: 'https://campus.chaina1.com' },
  prod: { api: 'https://campus.chaina1.com', image: 'https://campus.chaina1.com' },
}

function resolveEnv(): MiniProgramEnv {
  const override = typeof __ENV__ !== 'undefined' ? __ENV__ : ''
  if (override === 'dev' || override === 'experience' || override === 'prod') return override

  // 微信开发者工具为 develop；上传体验版/正式版分别为 trial/release。
  try {
    const envVersion = wx.getAccountInfoSync().miniProgram.envVersion
    if (envVersion === 'release') return 'prod'
    if (envVersion === 'trial') return 'experience'
  } catch {
    // 旧基础库或测试环境取不到账号信息时，默认使用本地后端，避免误连线上旧服务。
  }
  return 'dev'
}

export const ENV = resolveEnv()
const cfg = HOSTS[ENV]
export const API_HOST = cfg.api
export const IMAGE_HOST = cfg.image
export const BASE_URL = `${API_HOST}/api/v1`
