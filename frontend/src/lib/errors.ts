/**
 * Enterprise error classification. Turns any thrown value / error string into a
 * friendly, categorised message so the UI can show helpful, recoverable errors
 * (network, permission, validation, server, AI, connector …) instead of raw
 * stack text. See ErrorState for the presentation layer.
 */

export type ErrorCategory =
  | "network"
  | "permission"
  | "notFound"
  | "validation"
  | "server"
  | "ai"
  | "connector"
  | "unknown";

export interface FriendlyError {
  category: ErrorCategory;
  title: string;
  message: string;
  status?: number;
  /** The original, raw message (useful for a details/expand affordance). */
  detail?: string;
}

function messageOf(err: unknown): string {
  if (err == null) return "";
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  if (typeof err === "object" && "message" in err) {
    return String((err as { message?: unknown }).message ?? "");
  }
  return String(err);
}

function statusOf(err: unknown): number | undefined {
  if (err && typeof err === "object") {
    const o = err as { status?: unknown; statusCode?: unknown; response?: { status?: unknown } };
    const s = o.status ?? o.statusCode ?? o.response?.status;
    if (typeof s === "number") return s;
  }
  const m = messageOf(err).match(/\b(4\d\d|5\d\d)\b/);
  return m ? Number(m[1]) : undefined;
}

const COPY: Record<ErrorCategory, { title: string; message: string }> = {
  network: {
    title: "Connection problem",
    message: "We couldn't reach the server. Check your connection and try again.",
  },
  permission: {
    title: "Access denied",
    message:
      "You don't have permission to view this. Contact your administrator if you believe this is a mistake.",
  },
  notFound: {
    title: "Not found",
    message: "The requested resource could not be found. It may have been moved or deleted.",
  },
  validation: {
    title: "Check your input",
    message: "Some of the submitted values were invalid. Please review and try again.",
  },
  server: {
    title: "Something went wrong",
    message: "The server ran into an unexpected problem. Please try again in a moment.",
  },
  ai: {
    title: "AI service unavailable",
    message:
      "The AI service couldn't complete this request. It may be busy — please retry shortly.",
  },
  connector: {
    title: "Connector unavailable",
    message: "A connected data source didn't respond. Check the connector status and try again.",
  },
  unknown: {
    title: "Something went wrong",
    message: "An unexpected error occurred. You can retry, or return home if the problem persists.",
  },
};

export function classifyError(err: unknown): FriendlyError {
  const raw = messageOf(err);
  const lower = raw.toLowerCase();
  const status = statusOf(err);
  let category: ErrorCategory = "unknown";

  if (
    status === 401 ||
    status === 403 ||
    /forbidden|unauthori[sz]ed|permission|access denied/.test(lower)
  ) {
    category = "permission";
  } else if (status === 404 || /not found/.test(lower)) {
    category = "notFound";
  } else if (status === 400 || status === 422 || /invalid|validation|required field/.test(lower)) {
    category = "validation";
  } else if (
    /failed to fetch|network|networkerror|connection|timeout|timed out|offline|econnrefused/.test(
      lower,
    )
  ) {
    category = "network";
  } else if (/\bllm\b|model|prompt|inference|hallucinat|token limit/.test(lower)) {
    category = "ai";
  } else if (/connector|gst|mca|bureau|aggregator|erp|webhook|upstream/.test(lower)) {
    category = "connector";
  } else if ((status && status >= 500) || /server error|internal/.test(lower)) {
    category = "server";
  }

  return { category, ...COPY[category], status, detail: raw || undefined };
}

/** Short, human-quotable reference id for a support ticket (client-side). */
export function makeErrorId(): string {
  const now = typeof performance !== "undefined" ? Math.floor(performance.now()) : 0;
  const rand = Math.floor(Math.random() * 0xfffff);
  return `ERR-${(now ^ rand).toString(36).toUpperCase().slice(-6).padStart(6, "0")}`;
}

/** Build a "Contact support" mailto that pre-fills the error reference. */
export function supportHref(ref?: string, subject = "Support request"): string {
  const body = ref ? `\n\n---\nReference: ${ref}` : "";
  return `mailto:support@aicreditplatform.com?subject=${encodeURIComponent(subject)}${
    body ? `&body=${encodeURIComponent(body)}` : ""
  }`;
}
