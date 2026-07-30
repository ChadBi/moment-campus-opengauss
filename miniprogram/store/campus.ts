import type { School } from '../types'

interface CampusState {
  currentSchool: School | null
  schoolCode: string
  location: {
    latitude: number
    longitude: number
    accuracy?: number
  } | null
  locationAuthorized: boolean
}

type CampusListener = (state: CampusState) => void

const DEFAULT_SCHOOL = 'jiangnan'

const state: CampusState = {
  currentSchool: null,
  schoolCode: DEFAULT_SCHOOL,
  location: null,
  locationAuthorized: false,
}

const listeners: Set<CampusListener> = new Set()

function notify() {
  listeners.forEach(fn => fn({ ...state }))
}

export const campusStore = {
  subscribe(fn: CampusListener): () => void {
    listeners.add(fn)
    fn({ ...state })
    return () => listeners.delete(fn)
  },

  getState(): CampusState {
    return { ...state }
  },

  setSchool(school: School) {
    state.currentSchool = school
    state.schoolCode = school.code
    wx.setStorageSync('school_code', school.code)
    notify()
  },

  setSchoolCode(code: string) {
    state.schoolCode = code
    wx.setStorageSync('school_code', code)
    notify()
  },

  setLocation(lat: number, lng: number, accuracy?: number) {
    state.location = { latitude: lat, longitude: lng, accuracy }
    state.locationAuthorized = true
    notify()
  },

  setLocationAuthorized(authorized: boolean) {
    state.locationAuthorized = authorized
    if (!authorized) {
      state.location = null
    }
    notify()
  },

  initFromStorage() {
    const code = wx.getStorageSync('school_code')
    if (code) {
      state.schoolCode = code
    }
    notify()
  },
}
