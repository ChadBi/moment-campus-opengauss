// skills/moment-campus/apis/listTopics.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取话题/专题列表
 * @param {Object} args - { page?, page_size? }
 */
async function listTopics(args) {
  args = args || {};
  console.log('[ai-mode] listTopics');

  var params = {};
  if (args.page) params.page = args.page;
  if (args.page_size) params.page_size = args.page_size;

  var query = util.buildQueryString(params);

  try {
    var res = await http.get('/topics' + query);
    var topics = res.items || res.topics || [];
    var processed = topics.map(function(t) {
      return {
        id: t.id,
        title: t.title,
        description: t.description,
        cover_url: util.resolveImageUrl(t.cover_url || t.cover_image),
        post_count: t.post_count,
        is_featured: t.is_featured,
        created_at: t.created_at
      };
    });

    var total = res.total !== undefined ? res.total : processed.length;

    console.log('[ai-mode] listTopics success count=' + processed.length);

    return {
      content: [{ type: 'text', text: '共找到 ' + total + ' 个话题' }],
      structuredContent: {
        topics: processed,
        total: total
      },
      handoff: { query: 'page=' + (args.page || 1) }
    };
  } catch(e) {
    console.error('[ai-mode] listTopics error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取话题列表失败：' + e.message }]
    };
  }
}

module.exports = listTopics;
