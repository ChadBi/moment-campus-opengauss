export function buildLocationDescription(
  locationType: string | null | undefined,
  description: string | null | undefined,
): string | undefined {
  const type = String(locationType || '').trim();
  const desc = String(description || '').trim();
  const parts: string[] = [];
  if (type) parts.push(`场所类型：${type}`);
  if (desc) parts.push(desc);
  const joined = parts.join('\n');
  return joined.length > 0 ? joined : undefined;
}
