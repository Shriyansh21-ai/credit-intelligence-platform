/**
 * Compact fuzzy matcher used by the command palette and universal search.
 *
 * A dependency-free stand-in for Fuse.js: subsequence matching with scoring that
 * rewards consecutive matches, word-boundary hits and prefix matches — enough to
 * make "rag" surface "RAG Platform" and "portfolio" surface every portfolio page.
 * Kept tiny so search stays instant across the ~100-page registry.
 */

export interface FuzzyMatch<T> {
  item: T;
  score: number;
}

/**
 * Score how well `query` fuzzy-matches `text`. Returns a number in roughly
 * [0, 1+]; higher is better. Returns `null` when `query` is not a subsequence of
 * `text` at all (no match).
 */
export function fuzzyScore(query: string, text: string): number | null {
  if (!query) return 0;
  const q = query.toLowerCase();
  const t = text.toLowerCase();

  // Fast paths — exact / prefix / substring get strong, ranked bonuses.
  if (t === q) return 2;
  if (t.startsWith(q)) return 1.5;
  const idx = t.indexOf(q);
  if (idx >= 0) {
    // Substring: bonus if it lands on a word boundary.
    const boundary = idx === 0 || /[\s\-_/]/.test(t[idx - 1]);
    return 1.2 + (boundary ? 0.1 : 0) - idx * 0.002;
  }

  // Subsequence scan with consecutive / boundary bonuses.
  let qi = 0;
  let score = 0;
  let consecutive = 0;
  let prevMatchIdx = -2;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      let s = 0.1;
      if (ti === prevMatchIdx + 1) {
        consecutive++;
        s += 0.15 * consecutive;
      } else {
        consecutive = 0;
      }
      // Word-boundary bonus (start of a word inside the text).
      if (ti === 0 || /[\s\-_/]/.test(t[ti - 1])) s += 0.2;
      score += s;
      prevMatchIdx = ti;
      qi++;
    }
  }
  if (qi < q.length) return null; // not all query chars matched → no match
  // Normalise slightly by text length so short, tight matches rank above long ones.
  return score / (1 + t.length * 0.01);
}

/**
 * Rank `items` against `query` across the provided string fields (later fields
 * weighted lower). Items with no match on any field are dropped. Stable order is
 * preserved for equal scores (input order acts as tie-break).
 */
export function fuzzySearch<T>(
  query: string,
  items: readonly T[],
  fields: (item: T) => string[],
): FuzzyMatch<T>[] {
  const q = query.trim();
  if (!q) return items.map((item) => ({ item, score: 0 }));

  const results: (FuzzyMatch<T> & { order: number })[] = [];
  items.forEach((item, order) => {
    const parts = fields(item);
    let best: number | null = null;
    parts.forEach((part, i) => {
      const s = fuzzyScore(q, part);
      if (s !== null) {
        // Later fields (keywords, descriptions) contribute less than the title.
        const weighted = s * (i === 0 ? 1 : 0.7 - Math.min(i, 4) * 0.1);
        if (best === null || weighted > best) best = weighted;
      }
    });
    if (best !== null) results.push({ item, score: best, order });
  });

  results.sort((a, b) => (b.score === a.score ? a.order - b.order : b.score - a.score));
  return results.map(({ item, score }) => ({ item, score }));
}
