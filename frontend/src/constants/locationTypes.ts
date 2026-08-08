export const LOCATION_TYPE_OPTIONS = ['教学楼', '食堂', '宿舍', '运动场', '服务点', '公共空间', '其他'] as const;

export type LocationType = (typeof LOCATION_TYPE_OPTIONS)[number];
