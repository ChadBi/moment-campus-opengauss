// skills/moment-campus/apis/getMapMarkers.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取地图标记点
 * @param {Object} args - { school_id?, category_id? }
 */
async function getMapMarkers(args) {
  args = args || {};
  var err = util.ensureLogin();
  if (err.needLogin) {
    return {
      isError: true,
      content: [{ type: 'text', text: err.message }]
    };
  }

  console.log('[ai-mode] getMapMarkers');

  var params = {};
  if (args.school_id) params.school_id = args.school_id;
  if (args.category_id) params.category_id = args.category_id;

  var query = util.buildQueryString(params);

  try {
    var res = await http.get('/map/markers' + query);
    var markers = res.markers || [];
    var processed = markers.map(function(m) {
      return {
        id: m.id,
        post_id: m.post_id,
        latitude: m.latitude,
        longitude: m.longitude,
        title: m.title,
        content_snippet: m.content_snippet,
        category_name: m.category_name,
        status: m.status,
        created_at: m.created_at
      };
    });

    console.log('[ai-mode] getMapMarkers success count=' + processed.length);

    return {
      content: [{ type: 'text', text: '地图上有 ' + processed.length + ' 个此刻标记点' }],
      structuredContent: {
        markers: processed
      },
      handoff: { query: '' }
    };
  } catch(e) {
    console.error('[ai-mode] getMapMarkers error=' + e.message);
    return {
      isError: true,
      content: [{ type: 'text', text: '获取地图标记失败：' + e.message }]
    };
  }
}

module.exports = getMapMarkers;