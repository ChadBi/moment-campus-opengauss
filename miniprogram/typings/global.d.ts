/**
 * 全局类型补充声明
 * 小程序运行环境基于 JSCore，提供 URLSearchParams，但 tsconfig 未引入 DOM lib。
 * 这里补充最小声明，避免 URLSearchParams 报 TS2304。
 */
declare class URLSearchParams {
  constructor(init?: string | Record<string, string> | URLSearchParams)
  append(name: string, value: string): void
  delete(name: string): void
  get(name: string): string | null
  getAll(name: string): string[]
  has(name: string): boolean
  set(name: string, value: string): void
  toString(): string
}