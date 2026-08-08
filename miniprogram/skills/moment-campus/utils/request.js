// skills/moment-campus/utils/request.js
// Network request wrapper for moment-campus skill

// ⚠️ 真机调试时手机无法访问电脑的 localhost，开发环境必须用电脑的局域网地址。
// 与 miniprogram/config/env.ts 的 DEV_LAN_HOST 保持一致，换 Wi-Fi/网段时同步修改。
const DEV_LAN_HOST = '192.168.3.10'
var BASE_URL = `http://${DEV_LAN_HOST}:8000/api/v1`;
var REQUEST_TIMEOUT = 15000;

function getAccessToken() {
  return wx.getStorageSync('access_token') || '';
}

function getRefreshToken() {
  return wx.getStorageSync('refresh_token') || '';
}

function setTokens(accessToken, refreshToken) {
  wx.setStorageSync('access_token', accessToken);
  wx.setStorageSync('refresh_token', refreshToken);
}

function clearTokens() {
  wx.removeStorageSync('access_token');
  wx.removeStorageSync('refresh_token');
}

function getSchoolCode() {
  return wx.getStorageSync('school_code') || 'jiangnan';
}

function isAuthUrl(url) {
  var authPaths = ['/auth/', '/auth/wechat/'];
  return authPaths.some(function(p) { return url.indexOf(p) !== -1; });
}

function buildFullUrl(path) {
  if (path.indexOf('http') === 0) return path;
  return BASE_URL + (path.indexOf('/') === 0 ? path : '/' + path);
}

var isRefreshing = false;
var pendingRequests = [];

function refreshToken() {
  if (isRefreshing) {
    return new Promise(function(resolve) {
      pendingRequests.push(resolve);
    });
  }
  isRefreshing = true;
  var rt = getRefreshToken();
  if (!rt) {
    clearTokens();
    isRefreshing = false;
    return Promise.resolve(null);
  }
  return new Promise(function(resolve, reject) {
    wx.request({
      url: buildFullUrl('/auth/refresh'),
      method: 'POST',
      data: { refresh_token: rt },
      timeout: REQUEST_TIMEOUT,
      success: function(r) {
        if (r.statusCode === 200) {
          var tokens = r.data;
          setTokens(tokens.access_token, tokens.refresh_token);
          pendingRequests.forEach(function(cb) { cb(tokens.access_token); });
          pendingRequests = [];
          resolve(tokens.access_token);
        } else {
          clearTokens();
          pendingRequests.forEach(function(cb) { cb(null); });
          pendingRequests = [];
          resolve(null);
        }
        isRefreshing = false;
      },
      fail: function(err) {
        clearTokens();
        pendingRequests.forEach(function(cb) { cb(null); });
        pendingRequests = [];
        isRefreshing = false;
        resolve(null);
      }
    });
  });
}

function handleResponse(statusCode, data) {
  if (statusCode >= 200 && statusCode < 300) {
    return data;
  }
  if (statusCode === 401) {
    clearTokens();
    throw new Error(((data && data.detail) || '未登录或登录已过期'));
  }
  if (statusCode === 403) {
    throw new Error(((data && data.detail) || '权限不足'));
  }
  if (statusCode === 404) {
    throw new Error(((data && data.detail) || '资源不存在'));
  }
  if (statusCode >= 400 && statusCode < 500) {
    throw new Error(((data && data.detail) || (data && data.message) || '请求参数错误'));
  }
  throw new Error(((data && data.detail) || '服务器错误'));
}

function request(options) {
  var url = options.url;
  var method = options.method || 'GET';
  var data = options.data;
  var header = options.header || {};
  var fullUrl = buildFullUrl(url);
  var authUrl = isAuthUrl(url);

  var headers = {};
  for (var k in header) {
    if (header.hasOwnProperty(k)) headers[k] = header[k];
  }

  if (!authUrl) {
    var token = getAccessToken();
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    headers['X-School-Code'] = getSchoolCode();
  }

  return new Promise(function(resolve, reject) {
    wx.request({
      url: fullUrl,
      method: method,
      data: data,
      header: headers,
      timeout: REQUEST_TIMEOUT,
      success: function(r) {
        if (r.statusCode === 401 && !authUrl) {
          refreshToken().then(function(newToken) {
            if (newToken) {
              headers['Authorization'] = 'Bearer ' + newToken;
              wx.request({
                url: fullUrl,
                method: method,
                data: data,
                header: headers,
                timeout: REQUEST_TIMEOUT,
                success: function(r2) {
                  try {
                    resolve(handleResponse(r2.statusCode, r2.data));
                  } catch (e) { reject(e); }
                },
                fail: reject
              });
            } else {
              reject(new Error('登录已过期'));
            }
          });
        } else {
          try {
            resolve(handleResponse(r.statusCode, r.data));
          } catch (e) { reject(e); }
        }
      },
      fail: function(err) {
        if (err.errMsg && err.errMsg.indexOf('timeout') !== -1) {
          reject(new Error('请求超时，请检查网络'));
        } else {
          reject(err);
        }
      }
    });
  });
}

module.exports = {
  BASE_URL: BASE_URL,
  buildFullUrl: buildFullUrl,
  getAccessToken: getAccessToken,
  getSchoolCode: getSchoolCode,
  request: request,
  http: {
    get: function(url, data) { return request({ url: url, method: 'GET', data: data }); },
    post: function(url, data) { return request({ url: url, method: 'POST', data: data }); },
    put: function(url, data) { return request({ url: url, method: 'PUT', data: data }); },
    del: function(url, data) { return request({ url: url, method: 'DELETE', data: data }); }
  }
};