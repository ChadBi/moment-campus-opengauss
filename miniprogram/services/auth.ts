import { http } from './request'
import type {
  WechatExchangeResponse,
  LoginResponse,
  IdentityInfo,
  AuthSessionInfo,
} from '../types'

export async function wechatExchange(code: string): Promise<WechatExchangeResponse> {
  return http.post<WechatExchangeResponse>('/auth/wechat/exchange', { code })
}

export async function wechatBindExisting(
  bindingTicket: string,
  email: string,
  password: string
): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/wechat/bind-existing', {
    binding_ticket: bindingTicket,
    email,
    password,
  })
}

export async function wechatRegister(params: {
  binding_ticket: string
  nickname: string
  school_id: number
  password: string
  email?: string
}): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/wechat/register', params)
}

export async function emailLogin(email: string, password: string): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/login', { email, password })
}

export async function emailRegister(params: {
  email: string
  nickname: string
  password: string
  school_id: number
}): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/register', params)
}

export async function forgotPassword(email: string): Promise<{
  message: string
  reset_token?: string
}> {
  return http.post<{ message: string; reset_token?: string }>('/auth/forgot-password', {
    email,
  })
}

export async function resetPassword(params: {
  token: string
  new_password: string
}): Promise<{ message: string }> {
  return http.post<{ message: string }>('/auth/reset-password', params)
}

export async function refreshToken(refreshToken: string): Promise<{
  access_token: string
  refresh_token: string
}> {
  return http.post('/auth/refresh', { refresh_token: refreshToken })
}

export async function logout(): Promise<void> {
  return http.post('/auth/logout')
}

export async function listIdentities(): Promise<{ identities: IdentityInfo[] }> {
  return http.get('/auth/wechat/identities')
}

export async function addEmailIdentity(email: string, password: string): Promise<{
  message: string
  identity_id: number
}> {
  return http.post('/auth/wechat/identities/email', { email, password })
}

export async function deleteIdentity(identityId: number): Promise<{ message: string }> {
  return http.delete(`/auth/wechat/identities/${identityId}`)
}

export async function listSessions(): Promise<{ sessions: AuthSessionInfo[] }> {
  return http.get('/auth/wechat/sessions')
}

export async function revokeSession(sessionId: number): Promise<{ message: string }> {
  return http.delete(`/auth/wechat/sessions/${sessionId}`)
}

// ============== 校园身份认证（B-01/B-06，统一教育邮箱） ==============

export async function sendCampusVerify(): Promise<{ message: string; code?: string }> {
  return http.post<{ message: string; code?: string }>('/users/me/verify-campus/send')
}

export async function confirmCampusVerify(params: {
  code: string
}): Promise<{ message: string; campus_verified: boolean }> {
  return http.post<{ message: string; campus_verified: boolean }>(
    '/users/me/verify-campus/confirm',
    params
  )
}
