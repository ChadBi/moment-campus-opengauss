// skills/moment-campus/apis/aiSearch.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * AI 语义搜索此刻
 * @param {Object} args - { query, page?, page_size? }
 */
async function aiSearch(args) {
  args = args || {};
  if (!args.query || !args.query.trim()) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供搜索内容' }]
    };
  }

  console.log('[ai-mode] aiSearch query=' + args.query);

  var payload = { query: args.query.trim() };
  if (args.page) payload.page = args.page;
  if (args.page_size) payload.page_size = args.page_size;

  try {
    var res = await http.post('/search/ai', payload);
    var items = res.items || res.posts || [];
    var matchReasons = res.match_reasons || {};

    var processed = items.map(function(p) {
      var images = Array.isArray(p.images) ? p.images.map(function(img) { return { image_url: util.resolveImageUrl(img.image_url || img), thumbnail_url: img.thumbnail_url ? util.resolveImageUrl(img.thumbnail_url) : undefined }; }) : [];
      var reasons = (p.id !== undefined && (matchReasons[String(p.id)] || matchReasons[p.id])) || [];
      return {
        id: p.id,
        title: p.title,
        content: p.content,
        content_brief: util.truncateText(p.content || '', 80),
        cover: images[0] || '',
        images: images,
        category_name: p.category && p.category.name,
        author_nickname: p.author && p.author.nickname,
        like_count: p.like_count,
        comment_count: p.comment_count,
        created_at_text: util.formatDate(p.created_at),
        match_reasons: reasons
      };
    });

    var total = res.total !== undefined ? res.total : processed.length;
    var intent = res.intent || {};
    var intentText = intent.intent || '';
    var intentReasons = intent.reasons || [];

    var content = 'AI 搜索"' + args.query + '"找到 ' + total + ' 条结果';
    if (intentText) content += '。识别意图：' + intentText;

    console.log('[ai-mode] aiSearch success count=' + processed.length);

    return {
      content: [{ type: 'text', text: content }],
      structuredContent: {
        items: processed,
        total: total,
        intent: intentText,
        intent_reasons: intentReasons,
        match_reasons: matchReasons,
        has_more: res.has_more || false
      },
      handoff: { query: 'query=' + encodeURIComponent(args.query || '') }
    };
  } catch(e) {
    console.error('[ai-mode] aiSearch error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: 'AI搜索失败：' + e.message }]
    };
  }
}

module.exports = aiSearch;
