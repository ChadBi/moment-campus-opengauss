// skills/moment-campus/apis/likePost.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 点赞/取消点赞此刻
 * @param {Object} args - { post_id: number }
 */
async function likePost(args) {
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

  console.log('[ai-mode] likePost post_id=' + args.post_id);

  try {
    var res = await http.post('/posts/' + args.post_id + '/like');
    var liked = res.liked;
    var count = res.likes_count;
    var action = liked ? '点赞成功' : '已取消点赞';

    console.log('[ai-mode] likePost success liked=' + liked);

    return {
      content: [{ type: 'text', text: action + '（当前' + count + '赞）' }],
      structuredContent: {
        liked: liked,
        likes_count: count
      }
    };
  } catch(e) {
    console.error('[ai-mode] likePost error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '操作失败：' + e.message }]
    };
  }
}

module.exports = likePost;