// skills/moment-campus/utils/util.js
// Utility functions for moment-campus skill

function ensureStorageInit() {
  // Ensure school_code has a default
  var schoolCode = wx.getStorageSync('school_code');
  if (!schoolCode) {
    wx.setStorageSync('school_code', 'jiangnan');
  }
}

function ensureLogin() {
  var token = wx.getStorageSync('access_token');
  if (!token) {
    return { needLogin: true, message: '请先登录此刻校园' };
  }
  return { needLogin: false };
}

function resolveImageUrl(url) {
  if (!url) return '';
  if (url.indexOf('http') === 0) return url;
  if (url.indexOf('/uploads/') === 0) {
    return url.replace('/uploads/', 'http://localhost:8000/uploads/');
  }
  return url;
}

function formatDate(dateStr) {
  var date = new Date(dateStr);
  var now = new Date();
  var diffMs = now.getTime() - date.getTime();
  var diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return '刚刚';
  var diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return diffMin + '分钟前';
  var diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return diffHour + '小时前';
  var diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return diffDay + '天前';
  var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes());
}

function formatCount(count) {
  if (count < 1000) return '' + count;
  if (count < 10000) return (count / 1000).toFixed(1) + 'k';
  return (count / 10000).toFixed(1) + 'w';
}

function truncateText(text, maxLength) {
  maxLength = maxLength || 100;
  if (!text || text.length <= maxLength) return text || '';
  return text.slice(0, maxLength) + '...';
}

function getRemainingTime(expiresAt) {
  var expireDate = new Date(expiresAt);
  var now = new Date();
  var diffMs = expireDate.getTime() - now.getTime();
  if (diffMs <= 0) return '已过期';
  var diffHour = Math.floor(diffMs / (1000 * 60 * 60));
  var diffDay = Math.floor(diffHour / 24);
  if (diffDay > 0) return diffDay + '天后过期';
  if (diffHour > 0) return diffHour + '小时后过期';
  var diffMin = Math.floor(diffMs / (1000 * 60));
  return diffMin + '分钟后过期';
}

function buildQueryString(params) {
  var parts = [];
  for (var k in params) {
    if (params.hasOwnProperty(k) && params[k] !== undefined && params[k] !== null) {
      parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(String(params[k])));
    }
  }
  return parts.length > 0 ? '?' + parts.join('&') : '';
}

module.exports = {
  ensureStorageInit: ensureStorageInit,
  ensureLogin: ensureLogin,
  resolveImageUrl: resolveImageUrl,
  formatDate: formatDate,
  formatCount: formatCount,
  truncateText: truncateText,
  getRemainingTime: getRemainingTime,
  buildQueryString: buildQueryString
};