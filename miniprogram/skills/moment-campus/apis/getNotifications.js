// skills/moment-campus/apis/getNotifications.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取通知列表
 * @param {Object} args - { type?, page? }
 */
async function getNotifications(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  console.log('[ai-mode] getNotifications');

  var params = {};
  if (args.type) params.type = args.type;
  if (args.page) params.page = args.page;

  var query = util.buildQueryString(params);

  try {
    var res = await http.get('/notifications' + query);
    var items = res.items || res.notifications || [];
    var processed = items.map(function(n) {
      return {
        id: n.id,
        type: n.type,
        title: n.title,
        content: n.content,
        is_read: n.is_read,
        related_post_id: n.related_post_id,
        created_at: n.created_at,
        created_at_text: util.formatDate(n.created_at)
      };
    });

    var unreadCount = res.unread_count || 0;

    console.log('[ai-mode] getNotifications success count=' + processed.length + ' unread=' + unreadCount);

    return {
      content: [{ type: 'text', text: '您有 ' + unreadCount + ' 条未读通知，共 ' + processed.length + ' 条' }],
      structuredContent: {
        items: processed,
        unread_count: unreadCount
      },
      handoff: { query: 'type=' + (args.type || '') }
    };
  } catch(e) {
    console.error('[ai-mode] getNotifications error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取通知失败：' + e.message }]
    };
  }
}

module.exports = getNotifications;