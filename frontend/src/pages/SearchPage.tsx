import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchApi } from '../services/search';
import type { Post } from '../types';
import { Card } from '../components/ui/Card';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Heart, MessageCircle, Eye, MapPin, Clock, Search, Sparkles } from 'lucide-react';

const HOT_TAGS = ['食堂', '图书馆', '自习室', '快递点', '校园活动', '二手', '失物招领', '拍照打卡'];

const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e?: React.FormEvent, kw?: string) => {
    if (e) e.preventDefault();
    const target = (kw ?? keyword).trim();
    if (!target) {
      return;
    }
    if (kw) setKeyword(kw);

    setLoading(true);
    setSearched(true);
    try {
      const response = await searchApi.search(target);
      setPosts(response.data?.items || []);
    } catch (error) {
      console.error('搜索失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTagClick = (tag: string) => {
    setKeyword(tag);
    handleSearch(undefined, tag);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000) return '刚刚';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 30) return `${minutes}分钟前`;
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(diff / 86400000);
    return `${days}天前`;
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* 标题区 */}
      <div className="mb-6">
        <span className="eyebrow">SEARCH</span>
        <h1 className="text-2xl font-display font-bold text-lake mt-2">搜索</h1>
        <p className="text-ink-sub text-sm mt-1">发现校园生活的每一刻</p>
      </div>

      {/* 大搜索框 */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative">
          <Input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索标题、内容、地点..."
            icon={<Search size={20} />}
            className="!h-[52px] !rounded-[18px] !text-[15px] pr-24"
          />
          <Button
            type="submit"
            variant="primary"
            size="md"
            className="absolute right-2 top-1/2 -translate-y-1/2"
          >
            搜索
          </Button>
        </div>
      </form>

      {/* 热门标签推荐 */}
      {!searched && (
        <Card variant="elevated" padding="lg" className="mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-lamp" />
            <span className="text-sm font-semibold text-ink">热门搜索</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {HOT_TAGS.map(tag => (
              <button
                key={tag}
                type="button"
                onClick={() => handleTagClick(tag)}
                className="hand-tag hover:bg-lamp/15 hover:text-lamp transition-colors"
              >
                {tag}
              </button>
            ))}
          </div>
        </Card>
      )}

      {loading && (
        <div className="py-12">
          <Loading text="搜索中..." />
        </div>
      )}

      {/* 空状态：未搜索 */}
      {!loading && !searched && (
        <Card variant="outlined" padding="lg" className="text-center py-16">
          <div className="text-[56px] leading-none mb-4">🔎</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">搜索校园信息</h3>
          <p className="text-ink-sub text-sm">输入关键词，或点击上方热门标签开始探索</p>
        </Card>
      )}

      {/* 搜索无结果 */}
      {!loading && searched && posts.length === 0 && (
        <Card variant="outlined" padding="lg" className="text-center py-16">
          <div className="text-[56px] leading-none mb-4">🗂️</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">未找到相关内容</h3>
          <p className="text-ink-sub text-sm">换个关键词试试，或浏览热门标签</p>
        </Card>
      )}

      {/* 搜索结果 */}
      {!loading && posts.length > 0 && (
        <>
          <div className="mb-4 text-sm text-ink-sub flex items-center gap-2">
            <span className="hand-tag !bg-lake/10 !text-lake">找到 {posts.length} 条结果</span>
          </div>
          <div className="space-y-4">
            {posts.map(post => (
              <Card
                key={post.id}
                variant="elevated"
                padding="md"
                className="cursor-pointer"
                onClick={() => navigate(`/posts/${post.id}`)}
              >
                <div className="flex items-start gap-3">
                  <Avatar
                    src={post.author?.avatar_url}
                    fallback={post.author?.nickname?.[0] || '?'}
                    size="md"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="font-medium text-ink text-sm">
                        {post.author?.nickname || '匿名用户'}
                      </span>
                      <Badge variant="default">
                        {post.category?.name || '未分类'}
                      </Badge>
                    </div>
                    <h3 className="font-display font-semibold text-ink text-base mb-2 line-clamp-2">
                      {post.title}
                    </h3>
                    <p className="text-ink-sub text-sm mb-3 line-clamp-3">
                      {post.content}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-ink-muted">
                      <span className="flex items-center gap-1">
                        <MapPin size={14} />
                        {post.location?.name || '未知地点'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock size={14} />
                        {formatDate(post.created_at)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-3 text-xs text-ink-muted">
                      <span className="flex items-center gap-1">
                        <Eye size={14} />
                        {post.view_count || 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <Heart size={14} />
                        {post.like_count || 0}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageCircle size={14} />
                        {post.comment_count || 0}
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default SearchPage;
