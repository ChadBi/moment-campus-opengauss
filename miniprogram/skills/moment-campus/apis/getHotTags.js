// skills/moment-campus/apis/getHotTags.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取热门搜索标签
 */
async function getHotTags(args) {
  args = args || {};
  console.log('[ai-mode] getHotTags');

  try {
    var res = await http.get('/search/hot-tags');
    var tags = res.tags || [];

    console.log('[ai-mode] getHotTags success count=' + tags.length);

    return {
      content: [{ type: 'text', text: '热门搜索：' + (tags.length > 0 ? tags.join('、') : '暂无') }],
      structuredContent: {
        tags: tags
      }
    };
  } catch(e) {
    console.error('[ai-mode] getHotTags error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取热门标签失败：' + e.message }]
    };
  }
}

module.exports = getHotTags;
