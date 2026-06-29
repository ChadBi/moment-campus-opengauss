import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { postsApi } from '../services/posts';
import type { Post } from '../types';
import { Card } from '../components/ui/Card';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Loading } from '../components/ui/Loading';
import { Button } from '../components/ui/Button';
import { Heart, MessageCircle, Eye, MapPin, Clock } from 'lucide-react';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    loadPosts();
  }, [page]);

  const loadPosts = async () => {
    try {
      setLoading(true);
      const response = await postsApi.getPosts({ page, page_size: 20 });
      if (page === 1) {
        setPosts(response.items as Post[]);
      } else {
        setPosts(prev => [...prev, ...(response.items as Post[])]);
      }
      setHasMore(page * 20 < response.total);
    } catch (error) {
      console.error('加载帖子失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadMore = () => {
    if (hasMore && !loading) {
      setPage(prev => prev + 1);
    }
  };

  const handlePostClick = (postId: number) => {
    navigate(`/posts/${postId}`);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  return (
    <div className="max-w-2xl mx-auto px-1 py-2">
      {/* 页面标题：楷体品牌字 + 副标题 */}
      <header className="mb-7">
        <span className="eyebrow">Campus Feed</span>
        <h1 className="font-display font-extrabold text-[30px] leading-tight tracking-[0.06em] text-lake mt-2">
          此刻校园
        </h1>
        <p className="text-ink-sub text-sm mt-1.5">把会消失的校园经验留下来</p>
      </header>

      {/* 信息流卡片：左侧 Avatar + 右侧内容 */}
      <div className="space-y-4">
        {posts.map(post => (
          <Card
            key={post.id}
            variant="elevated"
            padding="md"
            className="hover:shadow-xl"
            onClick={() => handlePostClick(post.id)}
          >
            <div className="flex items-start gap-3.5">
              <Avatar
                src={post.author?.avatar_url}
                fallback={post.author?.nickname?.[0] || '?'}
                size="md"
                className="flex-shrink-0"
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
                <h3 className="font-semibold text-ink mb-2 line-clamp-2 leading-snug">
                  {post.title}
                </h3>
                <p className="text-ink-sub text-sm mb-3 line-clamp-3 leading-relaxed">
                  {post.content}
                </p>
                <div className="flex items-center gap-4 text-xs text-ink-muted">
                  <span className="flex items-center gap-1">
                    <MapPin size={13} />
                    {post.location?.name || '未知地点'}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={13} />
                    {formatDate(post.created_at)}
                  </span>
                </div>
                {/* 底部统计：小图标 + font-data 数字 */}
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-line/70 text-xs text-ink-muted">
                  <span className="flex items-center gap-1.5">
                    <Eye size={13} />
                    <span className="font-data font-bold">{post.view_count || 0}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Heart size={13} />
                    <span className="font-data font-bold">{post.like_count || 0}</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <MessageCircle size={13} />
                    <span className="font-data font-bold">{post.comment_count || 0}</span>
                  </span>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {loading && posts.length === 0 && (
        <div className="py-16">
          <Loading text="加载中..." />
        </div>
      )}

      {/* 空状态：大 emoji + 文字引导 */}
      {!loading && posts.length === 0 && (
        <div className="text-center py-16">
          <div className="text-5xl mb-4">⌖</div>
          <p className="font-medium text-ink mb-1.5">这里还没有校园经验</p>
          <p className="text-sm text-ink-muted">发布第一条，把会消失的校园经验留下来。</p>
        </div>
      )}

      {/* 加载更多：Button variant=secondary */}
      {hasMore && posts.length > 0 && (
        <div className="mt-7 text-center">
          <Button
            variant="secondary"
            onClick={handleLoadMore}
            loading={loading}
          >
            加载更多
          </Button>
        </div>
      )}
    </div>
  );
};

export default HomePage;
