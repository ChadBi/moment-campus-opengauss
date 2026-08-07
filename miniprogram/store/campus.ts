import type { School } from '../types'
import { normalizeSchool } from '../services/normalize'

interface CampusState {
  currentSchool: School | null
  schoolCode: string
}

type CampusListener = (state: CampusState) => void

const DEFAULT_SCHOOL = 'jiangnan'

const state: CampusState = {
  currentSchool: null,
  schoolCode: DEFAULT_SCHOOL,
}

const listeners: Set<CampusListener> = new Set()

function snapshot(): CampusState {
  return {
    currentSchool: state.currentSchool ? { ...state.currentSchool, domains: [...(state.currentSchool.domains || [])] } : null,
    schoolCode: state.schoolCode,
  }
}

function notify() {
  const value = snapshot()
  listeners.forEach(fn => fn(value))
}

export const campusStore = {
  subscribe(fn: CampusListener): () => void {
    listeners.add(fn)
    fn(snapshot())
    return () => listeners.delete(fn)
  },

  getState(): CampusState {
    return snapshot()
  },

  /** 原子写入当前学校对象及租户代码，避免页面读到半更新状态。 */
  setSchool(rawSchool: School | any) {
    const school = normalizeSchool(rawSchool, state.schoolCode)
    state.currentSchool = school
    state.schoolCode = school.code
    wx.setStorageSync('school_code', school.code)
    notify()
  },

  setSchoolCode(code: string) {
    const next = String(code || DEFAULT_SCHOOL)
    state.schoolCode = next
    wx.setStorageSync('school_code', next)
    notify()
  },

  initFromStorage() {
    const code = wx.getStorageSync('school_code')
    if (code) state.schoolCode = String(code)
    notify()
  },
}

export type { CampusState }
