// skills/moment-campus/apis/validatePost.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 协同验证（证实/证伪）
 * @param {Object} args - { post_id, validation_type: 'confirmation' | 'refutation' }
 */
async function validatePost(args) {
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
  if (!args.validation_type || (args.validation_type !== 'confirmation' && args.validation_type !== 'refutation')) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供验证类型（confirmation 或 refutation）' }]
    };
  }

  console.log('[ai-mode] validatePost post_id=' + args.post_id + ' type=' + args.validation_type);

  try {
    var res = await http.post('/posts/' + args.post_id + '/validations', {
      validation_type: args.validation_type
    });
    var typeLabel = args.validation_type === 'confirmation' ? '证实' : '证伪';
    console.log('[ai-mode] validatePost success');

    return {
      content: [{ type: 'text', text: '已完成' + typeLabel + '操作' }],
      structuredContent: {
        id: res && res.id,
        validation_type: args.validation_type
      }
    };
  } catch(e) {
    console.error('[ai-mode] validatePost error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '操作失败：' + e.message }]
    };
  }
}

module.exports = validatePost;