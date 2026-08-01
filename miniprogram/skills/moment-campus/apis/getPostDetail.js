// skills/moment-campus/apis/getPostDetail.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取此刻详情
 * @param {Object} args - { id: number }
 */
async function getPostDetail(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  var id = args.id;
  if (!id) {
    return {
      isError: true,
      content: [{ type: 'text', text: '请提供帖子ID' }]
    };
  }

  console.log('[ai-mode] getPostDetail id=' + id);

  try {
    var results = await Promise.all([
      http.get('/posts/' + id),
      http.get('/posts/' + id + '/interactions').catch(function() { return null; }),
      http.get('/posts/' + id + '/validation-stats').catch(function() { return null; }),
      http.get('/posts/' + id + '/comments').catch(function() { return null; })
    ]);

    var post = results[0] || {};
    var interactions = results[1] || {};
    var validationStats = results[2] || {};
    var commentsData = results[3] || {};

    var images = (post.images || []).map(function(u) { return util.resolveImageUrl(u); });
    var comments = (commentsData.items || commentsData.comments || []).map(function(c) {
      return {
        id: c.id,
        content: c.content,
        author_nickname: c.author_nickname,
        author_avatar: util.resolveImageUrl(c.author_avatar),
        created_at: c.created_at,
        created_at_text: util.formatDate(c.created_at)
      };
    });

    var postData = {
      id: post.id,
      title: post.title,
      content: post.content,
      images: images,
      location_name: post.location_name,
      latitude: post.latitude,
      longitude: post.longitude,
      category_id: post.category_id,
      category_name: post.category_name,
      status: post.status,
      author_id: post.author_id,
      author_nickname: post.author_nickname,
      author_avatar: util.resolveImageUrl(post.author_avatar),
      school_name: post.school_name,
      views_count: post.views_count,
      likes_count: post.likes_count,
      comments_count: post.comments_count,
      validations_count: post.validations_count,
      refutations_count: post.refutations_count,
      created_at: post.created_at,
      created_at_text: util.formatDate(post.created_at),
      expires_at: post.expires_at,
      remaining_time: post.expires_at ? util.getRemainingTime(post.expires_at) : ''
    };

    var textSummary = '【' + (post.category_name || '此刻') + '】' + post.title + '\n' +
      (post.content || '') + '\n' +
      '👍 ' + (post.likes_count || 0) + ' 💬 ' + (post.comments_count || 0);

    console.log('[ai-mode] getPostDetail success id=' + id);

    return {
      content: [{ type: 'text', text: textSummary }],
      structuredContent: {
        post: postData,
        interactions: {
          is_liked: interactions.is_liked || false,
          likes_count: interactions.likes_count || 0,
          comments_count: interactions.comments_count || 0
        },
        validation_stats: {
          confirmation_count: validationStats.confirmation_count || 0,
          refutation_count: validationStats.refutation_count || 0,
          total_count: validationStats.total_count || 0,
          validity_status: validationStats.validity_status || 'valid'
        },
        comments: comments
      },
      handoff: {
        query: 'id=' + id
      }
    };
  } catch(e) {
    console.error('[ai-mode] getPostDetail error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取此刻详情失败：' + e.message }]
    };
  }
}

module.exports = getPostDetail;