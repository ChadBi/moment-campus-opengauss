import { http } from './request'
import type { User } from '../types'

export async function getMe(): Promise<User> {
  return http.get<User>('/users/me')
}
