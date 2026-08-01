// skills/moment-campus/index.js
// Main entry point for moment-campus skill

var requestUtil = require('./utils/request.js');
var util = require('./utils/util.js');

// Ensure storage initialization
util.ensureStorageInit();

// Import API implementations
var listPosts = require('./apis/listPosts.js');
var getPostDetail = require('./apis/getPostDetail.js');
var createPost = require('./apis/createPost.js');
var searchPosts = require('./apis/searchPosts.js');
var aiSearch = require('./apis/aiSearch.js');
var likePost = require('./apis/likePost.js');
var createComment = require('./apis/createComment.js');
var validatePost = require('./apis/validatePost.js');
var listTopics = require('./apis/listTopics.js');
var getTopicDetail = require('./apis/getTopicDetail.js');
var getMapMarkers = require('./apis/getMapMarkers.js');
var listCategories = require('./apis/listCategories.js');
var getHotTags = require('./apis/getHotTags.js');
var getNotifications = require('./apis/getNotifications.js');
var getMyPosts = require('./apis/getMyPosts.js');

// Register all APIs
wx.modelContext.registerAPI('listPosts', listPosts);
wx.modelContext.registerAPI('getPostDetail', getPostDetail);
wx.modelContext.registerAPI('createPost', createPost);
wx.modelContext.registerAPI('searchPosts', searchPosts);
wx.modelContext.registerAPI('aiSearch', aiSearch);
wx.modelContext.registerAPI('likePost', likePost);
wx.modelContext.registerAPI('createComment', createComment);
wx.modelContext.registerAPI('validatePost', validatePost);
wx.modelContext.registerAPI('listTopics', listTopics);
wx.modelContext.registerAPI('getTopicDetail', getTopicDetail);
wx.modelContext.registerAPI('getMapMarkers', getMapMarkers);
wx.modelContext.registerAPI('listCategories', listCategories);
wx.modelContext.registerAPI('getHotTags', getHotTags);
wx.modelContext.registerAPI('getNotifications', getNotifications);
wx.modelContext.registerAPI('getMyPosts', getMyPosts);

console.log('[ai-mode] moment-campus skill initialized with 15 APIs');

module.exports = {
  listPosts: listPosts,
  getPostDetail: getPostDetail,
  createPost: createPost,
  searchPosts: searchPosts,
  aiSearch: aiSearch,
  likePost: likePost,
  createComment: createComment,
  validatePost: validatePost,
  listTopics: listTopics,
  getTopicDetail: getTopicDetail,
  getMapMarkers: getMapMarkers,
  listCategories: listCategories,
  getHotTags: getHotTags,
  getNotifications: getNotifications,
  getMyPosts: getMyPosts
};