import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { MotionConfig } from "framer-motion";
import { useEffect, useMemo, type ReactNode } from "react";

import { Compass, ServerCrash } from "lucide-react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { CommandPalette } from "../features/enterprise-platform";
import { OnboardingDialog } from "../features/onboarding";
import { Button } from "../components/ui/button";
import { makeErrorId, supportHref } from "../lib/errors";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="flex max-w-md flex-col items-center text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-secondary/50 text-muted-foreground">
          <Compass className="h-7 w-7" />
        </div>
        <h1 className="mt-5 text-6xl font-bold tracking-tight text-foreground">404</h1>
        <h2 className="mt-3 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button asChild>
            <Link to="/">Go home</Link>
          </Button>
          <Button variant="outline" onClick={() => history.back()}>
            Go back
          </Button>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  const ref = useMemo(() => makeErrorId(), []);
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="flex max-w-md flex-col items-center text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10 text-destructive">
          <ServerCrash className="h-7 w-7" />
        </div>
        <h1 className="mt-5 text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing, or head back home if the problem
          persists.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button
            onClick={() => {
              router.invalidate();
              reset();
            }}
          >
            Try again
          </Button>
          <Button variant="outline" asChild>
            <a href="/">Go home</a>
          </Button>
          <Button variant="ghost" asChild>
            <a href={supportHref(ref, "Support: application error")}>Contact support</a>
          </Button>
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          Reference <span className="font-mono text-foreground">{ref}</span>
        </p>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "AI Credit Intelligence Platform" },
      {
        name: "description",
        content:
          "AI-native credit risk, fraud detection, and lending decisioning platform for banks, NBFCs and fintechs.",
      },
      { name: "author", content: "AI Credit Intelligence Platform" },
      { property: "og:title", content: "AI Credit Intelligence Platform" },
      {
        property: "og:description",
        content: "Assess creditworthiness, detect fraud, and make explainable lending decisions.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      {/* Respect the OS "reduce motion" preference across all framer-motion animations. */}
      <MotionConfig reducedMotion="user">
        {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
        <Outlet />
        {/* Track 4 M1 — global ⌘K command palette (additive, self-contained). */}
        <CommandPalette />
        {/* Stage 2 M7 — first-run onboarding overlay (additive, self-contained). */}
        <OnboardingDialog />
      </MotionConfig>
    </QueryClientProvider>
  );
}
