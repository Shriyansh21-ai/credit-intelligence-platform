import { cn } from "@/lib/utils";
import { TONE_CLASS, TONE_COLOR, statusTone, titleCase } from "../format";
import type { HealthScore } from "../types";

/**
 * Circular 0-100 gauge for a single health dimension. Pure SVG (no chart lib)
 * so it renders deterministically and stays crisp at any size.
 */
export function HealthGauge({ health, size = 104 }: { health: HealthScore; size?: number }) {
  const tone = statusTone(health.status);
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const score = health.score ?? 0;
  const dash = (score / 100) * circumference;
  const color = TONE_COLOR[tone];

  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 shadow-card">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`${health.label}: ${health.score ?? "not available"} out of 100, ${health.status}`}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth={stroke}
          />
          {health.score !== null && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${circumference - dash}`}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-xl font-semibold", TONE_CLASS[tone].text)}>
            {health.score ?? "—"}
          </span>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {health.status === "unavailable" ? "N/A" : titleCase(health.status)}
          </span>
        </div>
      </div>
      <span className="text-center text-xs font-medium text-foreground">{health.label}</span>
    </div>
  );
}
