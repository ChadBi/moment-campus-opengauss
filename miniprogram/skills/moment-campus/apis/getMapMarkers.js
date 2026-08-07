// skills/moment-campus/apis/getMapMarkers.js
// [ai-mode:static]

var http = require('../utils/request.js').http;
var util = require('../utils/util.js');

/**
 * 获取学校静态地点标记点；地图不读取用户位置。
 * @param {Object} args - {}
 */
async function getMapMarkers(args) {
  args = args || {};
  console.log('[ai-mode] getMapMarkers');

  try {
    var res = await http.get('/locations');
    var locations = Array.isArray(res) ? res : (res.items || []);
    var processed = locations.map(function(m) {
      return {
        id: m.id,
        latitude: m.latitude,
        longitude: m.longitude,
        title: m.name,
        is_verified: m.is_verified,
        avg_score: m.avg_score,
        post_count: m.post_count
      };
    });

    console.log('[ai-mode] getMapMarkers success count=' + processed.length);

    return {
      content: [{ type: 'text', text: '地图上有 ' + processed.length + ' 个学校地点' }],
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
