export interface IssueLike {
  code: string;
  message: string;
  severity: "info" | "warning" | "risk";
}

export function dedupeIssues(...groups: IssueLike[][]): IssueLike[] {
  const seen = new Set<string>();
  const result: IssueLike[] = [];
  for (const group of groups) {
    for (const issue of group) {
      const key = `${issue.code}\u0000${issue.message}`;
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(issue);
    }
  }
  return result;
}

export function sortIssues(issues: IssueLike[]): IssueLike[] {
  const order: Record<IssueLike["severity"], number> = {
    risk: 0,
    warning: 1,
    info: 2,
  };
  return [...issues].sort((a, b) => order[a.severity] - order[b.severity]);
}
