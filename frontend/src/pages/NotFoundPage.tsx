import React from 'react';
import { Link } from 'react-router-dom';

const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-body px-4 relative overflow-hidden">
      {/* 装饰圆 */}
      <div className="pointer-events-none absolute -top-32 -left-24 w-80 h-80 rounded-full border-[28px] border-mist/70" />
      <div className="pointer-events-none absolute -bottom-28 -right-20 w-72 h-72 rounded-full border-[22px] border-mist/60" />

      <div className="relative text-center max-w-md">
        <span className="eyebrow">PAGE NOT FOUND</span>
        <h1 className="font-display font-bold text-lake text-[140px] leading-none mt-3 mb-4 select-none">
          404
        </h1>
        <h2 className="text-xl font-display font-bold text-ink mb-3">页面走丢了</h2>
        <p className="text-ink-sub text-sm mb-8 leading-relaxed">
          您访问的页面可能已被移除、重命名，<br />
          或暂时隐入了水墨之中。
        </p>
        <Link
          to="/"
          className="inline-flex items-center justify-center h-12 px-7 bg-lamp text-white rounded-md font-medium font-sans shadow-lamp hover:-translate-y-0.5 hover:bg-lamp-dark active:translate-y-0 transition-[transform,background-color,box-shadow] duration-[180ms] ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-lamp/40"
        >
          返回首页
        </Link>
      </div>
    </div>
  );
};

export default NotFoundPage;
