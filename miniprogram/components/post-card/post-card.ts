import { formatDate, formatCount } from '../../utils/format'
import { resolveAvatar, defaultAvatar } from '../../services/request'

/**
 * 分类名映射到分类色板 CSS 类名
 * 美食/食物/餐饮→food, 活动/事件→event, 服务→service,
 * 学习/学术→study, 失物招领/失物→lostFound, 社团→club, 其他→default
 */
function mapCategoryToClass(name: string): string {
  if (!name) return 'default'
  const n = String(name).trim()
  if (/(美食|食物|餐饮|食品|吃饭)/.test(n)) return 'food'
  if (/(活动|事件)/.test(n)) return 'event'
  if (/(服务)/.test(n)) return 'service'
  if (/(学习|学术|学习交流|课程|考研)/.test(n)) return 'study'
  if (/(失物招领|失物)/.test(n)) return 'lostFound'
  if (/(社团)/.test(n)) return 'club'
  return 'default'
}

Component({
  properties: {
    post: {
      type: Object,
      value: {},
    }
  },

  data: {
    displayImages: [] as string[],
    authorAvatar: defaultAvatar(),
    authorName: '匿名用户',
    formattedTime: '',
    formattedViews: '0',
    formattedLikes: '0',
    formattedComments: '0',
    formattedValidations: '0',
    formattedRefutations: '0',
    categoryClass: 'default',
    verified: false,
    recommendReason: '',
  },

  observers: {
    'post': function (post: any) {
      if (!post) return
      const rawImages = post.images || []
      const categoryName = (post.category && post.category.name) || ''
      // B-06: 归一化作者认证状态（页面已把 author.is_verified 归一化到 post.is_verified，兜底再查嵌套）
      const verified = !!post.is_verified || !!(post.author && post.author.is_verified)
      const authorName = (post.author && post.author.nickname) || '匿名用户'
      const authorAvatar = (post.author && post.author.avatar_url) || ''
      this.setData({
        displayImages: rawImages
          .map((img: any) => img.thumbnail_url || img.image_url)
          .slice(0, 3),
        authorAvatar: resolveAvatar(authorAvatar),
        authorName,
        verified,
        formattedTime: formatDate(post.created_at),
        formattedViews: formatCount(post.view_count || 0),
        formattedLikes: formatCount(post.like_count || 0),
        formattedComments: formatCount(post.comment_count || 0),
        formattedValidations: formatCount(post.valid_count || 0),
        formattedRefutations: formatCount(post.invalid_count || 0),
        categoryClass: mapCategoryToClass(categoryName),
        recommendReason: post.recommend_reason || '',
      })
    }
  },

  methods: {
    onTap() {
      const post = this.properties.post as any
      if (post && post.id !== undefined) {
        this.triggerEvent('tap', { id: post.id, post })
      }
    },

    onImageTap(e: any) {
      const current = e.currentTarget.dataset.src
      const urls = this.data.displayImages
      if (urls.length > 0) {
        wx.previewImage({ current, urls })
      }
    },
  }
})
