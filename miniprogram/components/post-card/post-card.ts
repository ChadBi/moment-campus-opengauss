import { formatDate, formatCount } from '../../utils/format'
import { resolveImageUrl } from '../../services/request'

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
  },

  observers: {
    'post': function (post: any) {
      if (!post) return
      const rawImages = post.images || []
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
