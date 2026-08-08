// skills/moment-campus/utils/util.js
// Utility functions for moment-campus skill

// ⚠️ 真机调试时手机无法访问电脑的 localhost，开发环境必须用电脑的局域网地址。
// 与 miniprogram/config/env.ts 的 DEV_LAN_HOST 保持一致，换 Wi-Fi/网段时同步修改。
const DEV_LAN_HOST = '192.168.3.10'
const DEV_API_HOST = `http://${DEV_LAN_HOST}:8000`

function ensureStorageInit() {
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
    return DEV_API_HOST + url;
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