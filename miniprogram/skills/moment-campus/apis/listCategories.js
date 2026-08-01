// skills/moment-campus/apis/listCategories.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取分类列表
 */
async function listCategories(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  console.log('[ai-mode] listCategories');

  try {
    var res = await http.get('/categories');
    var categories = res.categories || res.items || [];
    var processed = categories.map(function(c) {
      return {
        id: c.id,
        name: c.name,
        icon: c.icon,
        description: c.description,
        sort_order: c.sort_order
      };
    });

    console.log('[ai-mode] listCategories success count=' + processed.length);

    var names = processed.map(function(c) { return c.name; }).join('、');

    return {
      content: [{ type: 'text', text: '当前分类：' + (names || '暂无分类') }],
      structuredContent: {
        categories: processed
      }
    };
  } catch(e) {
    console.error('[ai-mode] listCategories error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取分类失败：' + e.message }]
    };
  }
}

module.exports = listCategories;