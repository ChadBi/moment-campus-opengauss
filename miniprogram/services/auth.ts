import { http } from './request'
import type { LoginResponse, User } from '../types'

export interface WechatQuickLoginResult {
  status: 'authenticated' | 'binding_required'
  access_token?: string
  refresh_token?: string
  token_type?: string
  user?: LoginResponse['user']
  message?: string
}

export async function wechatLogin(code: string): Promise<WechatQuickLoginResult> {
  return http.post<WechatQuickLoginResult>('/auth/wechat/login', { code })
}

export async function wechatPhoneLogin(code: string, phoneCode: string, schoolCode?: string): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/wechat/phone-login', {
    code,
    phone_code: phoneCode,
    school_code: schoolCode,
  })
}

export async function wechatSmsLogin(
  code: string,
  phone: string,
  smsCode: string,
  schoolCode?: string,
): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/wechat/sms-login', {
    code,
    phone,
    sms_code: smsCode,
    school_code: schoolCode,
  })
}

export async function phoneLogin(phone: string, password?: string, smsCode?: string): Promise<LoginResponse> {
  return http.post<LoginResponse>('/auth/login', {
    phone,
    ...(password ? { password } : { sms_code: smsCode }),
  })
}

export async function sendSms(phone: string, purpose: 'register' | 'login' | 'set_password' | 'education_unbind'): Promise<{ message: string; code?: string }> {
  return http.post('/auth/sms/send', { phone, purpose })
}

export async function setPassword(password: string, passwordConfirm: string): Promise<void> {
  return http.post('/auth/password/set', { password, password_confirm: passwordConfirm })
}

export async function refreshToken(refreshToken: string): Promise<{ access_token: string; refresh_token: string }> {
  return http.post('/auth/refresh', { refresh_token: refreshToken })
}

export async function logout(): Promise<void> {
  return http.post('/auth/logout')
}

export async function sendEducationEmail(educationEmail: string): Promise<{ message: string; code?: string }> {
  return http.post('/users/me/education-email/send', { education_email: educationEmail })
}

export async function confirmEducationEmail(code: string): Promise<{ message: string; campus_verified: boolean }> {
  return http.post('/users/me/education-email/confirm', { code })
}

export async function sendEducationEmailUnbindCode(): Promise<{ message: string; code?: string }> {
  return http.post('/users/me/education-email/unbind/send', {})
}

export async function unbindEducationEmail(smsCode: string): Promise<User> {
  return http.delete('/users/me/education-email', { sms_code: smsCode })
}
