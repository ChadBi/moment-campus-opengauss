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
      http.get('/posts/' + id + '/validation-stats').catch(function() { return null; }),
      http.get('/posts/' + id + '/comments').catch(function() { return null; })
    ]);

    var post = results[0] || {};
    var validationStats = results[1] || {};
    var commentsData = results[2] || {};

    var images = (post.images || []).map(function(img) { return { image_url: util.resolveImageUrl(img.image_url || img), thumbnail_url: img.thumbnail_url ? util.resolveImageUrl(img.thumbnail_url) : undefined }; });
    var comments = (commentsData.items || []).map(function(c) {
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
      location_name: post.location_name || (post.location && post.location.name),
      location_lat: post.location_lat,
      location_lng: post.location_lng,
      category_id: post.category_id,
      category_name: post.category && post.category.name,
      status: post.status,
      author_id: post.author_id,
      author_nickname: post.author && post.author.nickname,
      author_avatar: util.resolveImageUrl(post.author && post.author.avatar_url),
      school_name: post.school_name,
      view_count: post.view_count,
      like_count: post.like_count,
      comment_count: post.comment_count,
      valid_count: post.valid_count,
      invalid_count: post.invalid_count,
      created_at: post.created_at,
      created_at_text: util.formatDate(post.created_at),
      expire_at: post.expire_at,
      remaining_time: post.expire_at ? util.getRemainingTime(post.expire_at) : ''
    };

    var textSummary = '【' + (post.category_name || '此刻') + '】' + post.title + '\n' +
      (post.content || '') + '\n' +
      '👍 ' + (post.like_count || 0) + ' 💬 ' + (post.comment_count || 0);

    console.log('[ai-mode] getPostDetail success id=' + id);

    return {
      content: [{ type: 'text', text: textSummary }],
      structuredContent: {
        post: postData,
        interactions: {
          is_liked: post.is_liked || false,
          like_count: post.like_count || 0,
          comment_count: post.comment_count || 0
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
