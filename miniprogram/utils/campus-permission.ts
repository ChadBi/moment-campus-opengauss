import type { User } from '../types'

/** 注册时选择的学校；兼容历史用户尚未返回新字段的情况。 */
export function getRegistrationSchoolId(user?: Partial<User> | null): number | null {
  if (!user) return null
  const id = user.registration_school_id ?? user.school_id
  const normalized = Number(id)
  return Number.isFinite(normalized) ? normalized : null
}

/** 当前学校是否为用户注册时选择的学校。 */
export function isRegistrationSchool(user?: Partial<User> | null, schoolId?: number | null): boolean {
  if (schoolId == null) return true
  return getRegistrationSchoolId(user) === Number(schoolId)
}

/** 普通用户在当前学校是否具备内容写权限。 */
export function canWriteInCurrentSchool(user?: Partial<User> | null, schoolId?: number | null): boolean {
  if (!user) return false
  if (!user.campus_verified) return false
  return user.role === 'super_admin' || isRegistrationSchool(user, schoolId)
}
