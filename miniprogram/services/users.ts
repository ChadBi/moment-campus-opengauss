import { http } from './request'
import type { User } from '../types'
import { normalizeUser } from './normalize'

export async function getMe(): Promise<User> {
  return normalizeUser(await http.get<User>('/users/me'))
}
