import { http, resolveImageUrl, getAccessToken } from './request'
import { BASE_URL } from '../config/env'

export async function uploadImage(filePath: string): Promise<{ url: string }> {
  return new Promise((resolve, reject) => {
    const token = getAccessToken()
    const schoolCode = wx.getStorageSync('school_code') || 'jiangnan'

    wx.uploadFile({
      url: `${BASE_URL}/upload/image`,
      filePath,
      name: 'file',
      header: {
        'Authorization': `Bearer ${token}`,
        'X-School-Code': schoolCode,
      },
      success: res => {
        try {
          const data = JSON.parse(res.data)
          const url = data.url || data.path
          resolve({ url: resolveImageUrl(url) })
        } catch {
          reject(new Error('上传响应解析失败'))
        }
      },
      fail: err => reject(err),
    })
  })
}

export async function chooseAndUploadImage(count: number = 1): Promise<string[]> {
  // 与后端校验一致：单张 ≤5MB、仅 jpg/png/gif、总张数上限 5
  const MAX_IMAGE_SIZE = 5 * 1024 * 1024
  const ALLOWED_IMAGE_TYPES = /\.(jpe?g|png|gif)$/i
  const safeCount = Math.max(1, Math.min(Math.floor(count), 5))

  const res = await new Promise<any>((resolve, reject) => {
    wx.chooseMedia({
      count: safeCount,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      maxDuration: 30,
      camera: 'back',
      success: resolve,
      fail: reject,
    })
  })

  const urls: string[] = []
  for (const file of res.tempFiles) {
    if (file.size > MAX_IMAGE_SIZE) {
      wx.showToast({ title: '图片不能超过5MB', icon: 'none' })
      continue
    }
    if (!ALLOWED_IMAGE_TYPES.test(file.tempFilePath || '')) {
      wx.showToast({ title: '仅支持 jpg/png/gif 图片', icon: 'none' })
      continue
    }
    try {
      const { url } = await uploadImage(file.tempFilePath)
      urls.push(url)
    } catch (e) {
      console.error('图片上传失败', e)
    }
  }
  return urls
}
