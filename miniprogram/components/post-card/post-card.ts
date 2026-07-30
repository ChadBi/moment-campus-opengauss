import { formatDate, formatCount } from '../../utils/format'
import { resolveImageUrl } from '../../services/request'

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
      value: null,
    }
  },

  data: {
    displayImages: [] as string[],
    authorAvatar: '',
    formattedTime: '',
    formattedViews: '0',
    formattedLikes: '0',
    formattedComments: '0',
    formattedValidations: '0',
    formattedRefutations: '0',
    categoryClass: 'default',
  },

  observers: {
    'post': function (post: any) {
      if (!post) return
      const rawImages = post.images || []
      const categoryName = post.category_name || (post.category && post.category.name) || ''
      this.setData({
        displayImages: rawImages
          .map((img: string) => resolveImageUrl(img))
          .slice(0, 3),
        authorAvatar: resolveImageUrl(post.author_avatar),
        formattedTime: formatDate(post.created_at),
        formattedViews: formatCount(post.views_count || 0),
        formattedLikes: formatCount(post.likes_count || 0),
        formattedComments: formatCount(post.comments_count || 0),
        formattedValidations: formatCount(post.validations_count || 0),
        formattedRefutations: formatCount(post.refutations_count || 0),
        categoryClass: mapCategoryToClass(categoryName),
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
