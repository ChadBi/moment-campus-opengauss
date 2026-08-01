// skills/moment-campus/apis/getMyPosts.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取我的此刻列表
 * @param {Object} args - { status?, page? }
 */
async function getMyPosts(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  console.log('[ai-mode] getMyPosts');

  var params = {};
  if (args.status) params.status = args.status;
  if (args.page) params.page = args.page;

  var query = util.buildQueryString(params);

  try {
    var res = await http.get('/users/me/posts' + query);
    var items = res.items || res.posts || [];
    var processed = items.map(function(p) {
      var images = Array.isArray(p.images) ? p.images.map(function(u) { return util.resolveImageUrl(u); }) : [];
      return {
        id: p.id,
        title: p.title,
        content: p.content,
        cover: images[0] || '',
        status: p.status,
        views_count: p.views_count,
        likes_count: p.likes_count,
        comments_count: p.comments_count,
        validations_count: p.validations_count,
        created_at: p.created_at,
        created_at_text: util.formatDate(p.created_at)
      };
    });

    var total = res.total !== undefined ? res.total : processed.length;

    console.log('[ai-mode] getMyPosts success count=' + processed.length);

    return {
      content: [{ type: 'text', text: '我发布了 ' + total + ' 条此刻' }],
      structuredContent: {
        items: processed,
        total: total
      },
      handoff: { query: 'status=' + (args.status || '') }
    };
  } catch(e) {
    console.error('[ai-mode] getMyPosts error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取我的此刻失败：' + e.message }]
    };
  }
}

module.exports = getMyPosts;