/**
 * Universal navigation search — fuzzy-ranks the whole registry for the command
 * palette and the top-bar search. Searches title, module and keywords so "rag",
 * "portfolio", "policy" or "basel" all land on the right pages instantly.
 */

import { fuzzySearch } from "./fuzzy";
import { NAV_ITEMS, type NavItem } from "./registry";

export function searchNavigation(query: string, limit = 50): NavItem[] {
  const results = fuzzySearch(query, NAV_ITEMS, (item) => [
    item.title,
    item.moduleTitle,
    ...(item.keywords ?? []),
    item.description ?? "",
  ]);
  return results.slice(0, limit).map((r) => r.item);
}
