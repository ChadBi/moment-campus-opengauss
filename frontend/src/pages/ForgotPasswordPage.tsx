import React from 'react';
import { Link } from 'react-router-dom';

/** 兼容旧书签：邮箱找回密码已下线，统一引导到手机号登录。 */
const ForgotPasswordPage: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-mist px-4">
    <div className="max-w-md rounded-[16px] bg-paper p-8 text-center shadow-sm">
      <h1 className="font-display font-bold text-xl text-lake">邮箱找回密码已下线</h1>
      <p className="mt-3 text-sm text-ink-muted">请使用手机号短信验证码登录；小程序账号登录后可在个人中心设置密码。</p>
      <Link to="/login" className="mt-6 inline-block text-sm font-medium text-lake hover:underline">返回手机号登录</Link>
    </div>
  </div>
);

export default ForgotPasswordPage;
