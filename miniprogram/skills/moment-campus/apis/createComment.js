// skills/moment-campus/apis/createComment.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 发表评论
 * @param {Object} args - { post_id, content, parent_id?, reply_to_user_id? }
 */
async function createComment(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  if (!args.post_id) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供帖子ID' }]
    };
  }
  if (!args.content || !args.content.trim()) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供评论内容' }]
    };
  }

  console.log('[ai-mode] createComment post_id=' + args.post_id);

  var payload = { content: args.content.trim() };
  if (args.parent_id) payload.parent_id = args.parent_id;
  if (args.reply_to_user_id) payload.reply_to_user_id = args.reply_to_user_id;

  try {
    var res = await http.post('/posts/' + args.post_id + '/comments', payload);
    console.log('[ai-mode] createComment success id=' + (res && res.id));

    return {
      content: [{ type: 'text', text: '评论发表成功' }],
      structuredContent: {
        id: res && res.id,
        content: args.content.trim(),
        created_at: res && res.created_at
      }
    };
  } catch(e) {
    console.error('[ai-mode] createComment error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '评论失败：' + e.message }]
    };
  }
}

module.exports = createComment;
