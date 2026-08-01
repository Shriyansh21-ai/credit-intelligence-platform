/**
 * Shared Recharts theme (Stage 2 · M10).
 *
 * A single, token-driven palette + tooltip/axis/grid styles so every chart in
 * the app looks consistent and is readable in both light and dark themes.
 * Colours reference the CSS theme tokens (see styles.css / DESIGN_SYSTEM.md),
 * so charts recolour automatically with the theme.
 */

/** Categorical series palette — theme tokens, safe as Recharts `fill`/`stroke`. */
export const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-accent)",
  "var(--color-info)",
  "var(--color-success)",
];

/** Themed tooltip container (readable in dark mode). */
export const chartTooltipStyle = {
  backgroundColor: "var(--color-popover)",
  border: "1px solid var(--color-border)",
  borderRadius: 10,
  fontSize: 12,
  color: "var(--color-popover-foreground)",
} as const;

/** Axis tick label style. */
export const chartAxisTick = { fill: "var(--color-muted-foreground)", fontSize: 11 } as const;

/** Axis line / grid stroke. */
export const chartGridStroke = "var(--color-border)";

/** Hover cursor fill for bar/area tooltips. */
export const chartCursor = { fill: "var(--color-secondary)", opacity: 0.4 } as const;
