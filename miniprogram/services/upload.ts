import { http, resolveImageUrl } from './request'

export async function uploadImage(filePath: string): Promise<{ url: string }> {
  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('access_token')
    const schoolCode = wx.getStorageSync('school_code') || 'jiangnan'

    wx.uploadFile({
      url: 'http://localhost:8000/api/v1/uploads',
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
  const res = await new Promise<any>((resolve, reject) => {
    wx.chooseMedia({
      count,
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
    if (file.size > 5 * 1024 * 1024) {
      wx.showToast({ title: '图片不能超过5MB', icon: 'none' })
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
