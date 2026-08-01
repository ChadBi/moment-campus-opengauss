// skills/moment-campus/apis/getTopicDetail.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取话题详情及关联此刻
 * @param {Object} args - { id: number }
 */
async function getTopicDetail(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  if (!args.id) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供话题ID' }]
    };
  }

  console.log('[ai-mode] getTopicDetail id=' + args.id);

  try {
    var res = await http.get('/topics/' + args.id);
    var topic = res || {};
    var posts = Array.isArray(topic.posts) ? topic.posts.map(function(p) {
      var cover = util.resolveImageUrl(p.cover_image_url || p.cover_image);
      return {
        id: p.id,
        title: p.title,
        cover: cover,
        author_name: p.author_name,
        like_count: p.like_count || p.likes_count || 0,
        comment_count: p.comment_count || p.comments_count || 0,
        view_count: p.view_count || p.views_count || 0,
        created_at: p.created_at,
        created_at_text: util.formatDate(p.created_at)
      };
    }) : [];

    console.log('[ai-mode] getTopicDetail success id=' + args.id);

    return {
      content: [{ type: 'text', text: '【' + (topic.title || '话题') + '】共 ' + (topic.post_count || 0) + ' 条此刻' }],
      structuredContent: {
        topic: {
          id: topic.id,
          title: topic.title,
          description: topic.description,
          cover_image: util.resolveImageUrl(topic.cover_url || topic.cover_image),
          post_count: topic.post_count
        },
        posts: posts
      },
      handoff: { query: 'id=' + args.id }
    };
  } catch(e) {
    console.error('[ai-mode] getTopicDetail error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取话题详情失败：' + e.message }]
    };
  }
}

module.exports = getTopicDetail;