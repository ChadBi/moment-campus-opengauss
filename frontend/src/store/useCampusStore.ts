import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface CampusState {
  currentSchoolId: number | null;
  currentSchoolName: string | null;
  setSchool: (id: number, name: string) => void;
  clearSchool: () => void;
}

export const useCampusStore = create<CampusState>()(
  persist(
    (set) => ({
      currentSchoolId: null,
      currentSchoolName: null,
      setSchool: (id, name) =>
        set({ currentSchoolId: id, currentSchoolName: name }),
      clearSchool: () =>
        set({ currentSchoolId: null, currentSchoolName: null }),
    }),
    {
      name: 'campus-storage',
    }
  )
);
