import type { User } from '../types';

/** 注册时选择的学校；兼容尚未返回新字段的历史用户。 */
export function getRegistrationSchoolId(user?: Pick<User, 'school_id' | 'registration_school_id'> | null): number | null {
  if (!user) return null;
  const id = user.registration_school_id ?? user.school_id;
  return Number.isFinite(Number(id)) ? Number(id) : null;
}

/** 当前页面是否处于用户注册时选择的学校。 */
export function isRegistrationSchool(
  user?: Pick<User, 'school_id' | 'registration_school_id'> | null,
  currentSchoolId?: number | null,
): boolean {
  if (currentSchoolId == null) return true;
  return getRegistrationSchoolId(user) === Number(currentSchoolId);
}

/** 普通用户在当前学校是否拥有内容写权限。 */
export function canWriteInCurrentSchool(
  user?: Pick<User, 'school_id' | 'registration_school_id' | 'campus_verified' | 'role'> | null,
  currentSchoolId?: number | null,
): boolean {
  if (!user) return false;
  if (!user.campus_verified) return false;
  return user.role === 'super_admin' || isRegistrationSchool(user, currentSchoolId);
}
