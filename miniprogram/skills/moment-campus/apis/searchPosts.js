// skills/moment-campus/apis/searchPosts.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 关键词搜索此刻
 * @param {Object} args - { keyword, page?, page_size? }
 */
async function searchPosts(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  if (!args.keyword || !args.keyword.trim()) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供搜索关键词' }]
    };
  }

  console.log('[ai-mode] searchPosts keyword=' + args.keyword);

  var params = { keyword: args.keyword.trim() };
  if (args.page) params.page = args.page;
  if (args.page_size) params.page_size = args.page_size;

  var query = util.buildQueryString(params);

  try {
    var res = await http.get('/search' + query);
    var items = res.items || res.posts || [];
    var processed = items.map(function(p) {
      var images = Array.isArray(p.images) ? p.images.map(function(u) { return util.resolveImageUrl(u); }) : [];
      return {
        id: p.id,
        title: p.title,
        content: p.content,
        content_brief: util.truncateText(p.content || '', 80),
        cover: images[0] || '',
        images: images,
        category_id: p.category_id,
        category_name: p.category_name,
        author_nickname: p.author_nickname,
        author_avatar: util.resolveImageUrl(p.author_avatar),
        likes_count: p.likes_count,
        comments_count: p.comments_count,
        views_count: p.views_count,
        created_at: p.created_at,
        created_at_text: util.formatDate(p.created_at)
      };
    });

    var total = res.total !== undefined ? res.total : processed.length;
    var hasMore = res.has_more !== undefined ? res.has_more : false;

    var content = '搜索"' + args.keyword + '"找到 ' + total + ' 条结果';

    console.log('[ai-mode] searchPosts success count=' + processed.length);

    return {
      content: [{ type: 'text', text: content }],
      structuredContent: {
        items: processed,
        total: total,
        has_more: hasMore
      },
      handoff: { query: 'keyword=' + encodeURIComponent(args.keyword || '') }
    };
  } catch(e) {
    console.error('[ai-mode] searchPosts error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '搜索失败：' + e.message }]
    };
  }
}

module.exports = searchPosts;