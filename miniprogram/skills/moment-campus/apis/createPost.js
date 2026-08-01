// skills/moment-campus/apis/createPost.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 发布新此刻
 * @param {Object} args - { title, content, category_id, location_name?, images?, expires_at? }
 */
async function createPost(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  if (!args.title || !args.title.trim()) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供此刻标题' }]
    };
  }
  if (!args.category_id) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请选择分类' }]
    };
  }

  console.log('[ai-mode] createPost title=' + args.title);

  var payload = {
    title: args.title.trim(),
    content: (args.content || '').trim(),
    category_id: args.category_id
  };
  if (args.location_name) payload.location_name = args.location_name;
  if (args.latitude) payload.latitude = args.latitude;
  if (args.longitude) payload.longitude = args.longitude;
  if (args.images && args.images.length > 0) payload.images = args.images;
  if (args.expires_at) payload.expires_at = args.expires_at;

  try {
    var res = await http.post('/posts', payload);
    console.log('[ai-mode] createPost success id=' + res.id);

    return {
      content: [{ type: 'text', text: '此刻发布成功！标题：' + res.title }],
      structuredContent: {
        id: res.id,
        title: res.title,
        status: res.status
      },
      handoff: {
        query: 'id=' + res.id
      }
    };
  } catch(e) {
    console.error('[ai-mode] createPost error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '发布此刻失败：' + e.message }]
    };
  }
}

module.exports = createPost;