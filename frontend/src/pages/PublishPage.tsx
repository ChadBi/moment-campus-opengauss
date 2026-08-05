import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useCampusStore } from '../store/useCampusStore';
import { Card } from '../components/ui/Card';
import PostForm from '../components/PostForm';
import { VerifyGate } from '../components/VerifyGate';

/**
 * PUB-01.1: 发布页（页面壳）
 *
 * 表单核心逻辑（字段 / 校验 / 图片 / 标签 / 地点 / 草稿恢复）已抽取到
 * `components/PostForm.tsx`，本页只保留页面级布局（标题 / 说明 / 当前学校）
 * 与发布成功后的跳转策略（PUB-01.3：跳"我的发布" /profile）。
 *
 * MapPage 的侧滑发帖面板复用同一个 PostForm（variant='panel'），保证字段、
 * 校验、草稿恢复一致。
 *
 * PUB-02: 支持 `?edit={postId}` 进入草稿编辑模式（继续编辑 / 修改后重新提交），
 * 提交成功后回到"我的发布"。
 */

const PublishPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const currentSchoolName = useCampusStore((s) => s.currentSchoolName);

  // PUB-02: 编辑模式（从"我的发布-草稿"进入）
  const editIdRaw = searchParams.get('edit');
  const editPostId = editIdRaw && /^\d+$/.test(editIdRaw) ? Number(editIdRaw) : undefined;

  const handleSuccess = (status: 'draft' | 'pending') => {
    // PUB-01.3：发布成功后跳"我的发布"（/profile），而非无条件跳首页
    // 草稿也跳 /profile，便于用户继续编辑
    void status;
    setTimeout(() => navigate('/profile'), 800);
  };

  return (
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-5 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
          {editPostId ? '编辑草稿' : '发布此刻'}
        </h1>
        <p className="text-ink-muted text-sm mt-1">
          {editPostId ? '修改后可保存草稿或直接重新提交审核' : '把会消失的校园经验留下来'}
          {currentSchoolName ? (
            <span className="ml-1 text-ink-sub">· 当前学校：{currentSchoolName}</span>
          ) : null}
        </p>
      </header>

      <Card variant="elevated" padding="lg">
        {/* D4: 未认证用户仅只读——发帖需先完成校园身份认证 */}
        <VerifyGate message="完成校园身份认证后即可发布内容（未认证用户仅拥有浏览权限）">
          <PostForm
            variant="page"
            onSuccess={handleSuccess}
            onCancel={() => navigate(-1)}
            editPostId={editPostId}
          />
        </VerifyGate>
      </Card>
    </div>
  );
};

export default PublishPage;
