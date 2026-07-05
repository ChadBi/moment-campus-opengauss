import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchApi } from '../services/search';
import type { Post } from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Loading } from '../components/ui/Loading';
import { MapPin, Clock, Search, Sparkles } from 'lucide-react';

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
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-5 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">搜索</h1>
        <p className="text-ink-muted text-sm mt-1">发现校园生活的每一刻</p>
      </header>

      <form onSubmit={handleSearch} className="mb-5">
        <div className="relative">
          <Input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索标题、内容、地点..."
            icon={<Search size={16} />}
            className="pr-20"
          />
          <Button
            type="submit"
            variant="primary"
            size="sm"
            className="absolute right-1 top-1/2 -translate-y-1/2"
          >
            搜索
          </Button>
        </div>
      </form>

      {!searched && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-lamp" />
            <span className="text-sm font-semibold text-ink">热门搜索</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {HOT_TAGS.map(tag => (
              <button
                key={tag}
                type="button"
                onClick={() => handleTagClick(tag)}
                className="inline-flex items-center px-2.5 py-1 rounded-[6px] text-xs font-medium bg-mist text-ink-sub hover:bg-lake/10 hover:text-lake transition-colors"
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className="py-12">
          <Loading text="搜索中..." />
        </div>
      )}

      {!loading && !searched && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-10 text-center">
          <div className="text-[48px] leading-none mb-4">🔎</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">搜索校园信息</h3>
          <p className="text-ink-sub text-sm">输入关键词，或点击上方热门标签开始探索</p>
        </div>
      )}

      {!loading && searched && posts.length === 0 && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-10 text-center">
          <div className="text-[48px] leading-none mb-4">🗂️</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">未找到相关内容</h3>
          <p className="text-ink-sub text-sm">换个关键词试试，或浏览热门标签</p>
        </div>
      )}

      {!loading && posts.length > 0 && (
        <>
          <div className="mb-4 text-sm text-ink-sub flex items-center gap-2">
            <span className="text-xs bg-lake/10 text-lake px-2 py-0.5 rounded-[6px]">找到 {posts.length} 条结果</span>
          </div>
          <div className="space-y-0">
            {posts.map((post, idx) => (
              <article
                key={post.id}
                className={`bg-paper border border-line/60 rounded-[16px] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer mb-3 overflow-hidden ${idx > 0 ? '' : ''}`}
                onClick={() => navigate(`/posts/${post.id}`)}
              >
                <div className="px-5 pt-4 pb-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar
                      src={post.author?.avatar_url}
                      fallback={post.author?.nickname?.[0] || '?'}
                      size="sm"
                    />
                    <span className="font-medium text-ink text-sm">
                      {post.author?.nickname || '匿名用户'}
                    </span>
                    <Badge>
                      {post.category?.name || '未分类'}
                    </Badge>
                    <span className="text-xs text-ink-muted ml-auto flex items-center gap-1">
                      <Clock size={11} />
                      {formatDate(post.created_at)}
                    </span>
                  </div>
                  <h3 className="font-semibold text-[15px] text-ink mb-1.5 line-clamp-2 leading-[1.5]">
                    {post.title}
                  </h3>
                  <p className="text-ink-sub text-[14px] line-clamp-2 leading-[1.7]">
                    {post.content}
                  </p>
                </div>
                <div className="px-5 py-2.5 border-t border-ink-divider/60 flex items-center justify-between text-xs text-ink-muted">
                  <span className="flex items-center gap-1">
                    <MapPin size={11} />
                    {post.location?.name || '未知地点'}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default SearchPage;
