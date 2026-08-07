// skills/moment-campus/apis/listPosts.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取此刻列表
 * @param {Object} args - { category_id?, page?, page_size? }
 */
async function listPosts(args) {
  args = args || {};
  console.log('[ai-mode] listPosts args=' + JSON.stringify(args));

  var params = {};
  if (args.category_id !== undefined) params.category_id = args.category_id;
  if (args.page !== undefined) params.page = args.page;
  if (args.page_size !== undefined) params.page_size = args.page_size;

  var query = util.buildQueryString(params);

  var url = (args.category_id === 0 || !args.category_id)
    ? '/recommendations' + query
    : '/posts' + query;

  try {
    var res = await http.get(url);
    var items = res.items || res.posts || [];
    var processed = items.map(function(p) {
      return {
        id: p.id,
        title: p.title,
        content: p.content,
        images: (p.images || []).map(function(img) { return { image_url: util.resolveImageUrl(img.image_url || img), thumbnail_url: img.thumbnail_url ? util.resolveImageUrl(img.thumbnail_url) : undefined }; }),
        category_id: p.category_id,
        category_name: p.category && p.category.name,
        status: p.status,
        author_nickname: p.author_nickname,
        author_avatar: util.resolveImageUrl(p.author_avatar),
        school_name: p.school_name,
        view_count: p.view_count,
        like_count: p.like_count,
        comment_count: p.comment_count,
        valid_count: p.valid_count,
        invalid_count: p.invalid_count,
        created_at: p.created_at,
        created_at_text: util.formatDate(p.created_at),
        has_location: !!(p.location_id || p.location)
      };
    });

    var total = res.total !== undefined ? res.total : processed.length;
    var hasMore = res.has_more !== undefined ? res.has_more : false;

    var content = '为你找到 ' + total + ' 条此刻' + (params.category_id ? '（分类ID:' + params.category_id + '）' : '（推荐）');

    console.log('[ai-mode] listPosts success count=' + processed.length);

    return {
      content: [{ type: 'text', text: content }],
      structuredContent: {
        items: processed,
        total: total,
        has_more: hasMore,
        page: params.page || 1
      },
      handoff: { query: 'category_id=' + (args.category_id || 0) + '&page=' + (args.page || 1) }
    };
  } catch(e) {
    console.error('[ai-mode] listPosts error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取此刻列表失败：' + e.message }]
    };
  }
}

module.exports = listPosts;
