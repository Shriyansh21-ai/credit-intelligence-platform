import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  AtSign,
  BadgeCheck,
  Briefcase,
  Building2,
  Check,
  Fingerprint,
  Maximize2,
  Minimize2,
  Network,
  Shield,
  User,
} from "lucide-react";

import { AppShell } from "@/components/dashboard/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMyAccess } from "@/features/operations";
import { useNavigation } from "@/navigation";
import { useProfile, useUpdateProfile } from "@/lib/profile";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({ component: SettingsPage });

function SettingsPage() {
  return (
    <AppShell
      title="Profile & Settings"
      description="Manage your account details and personalise how the workspace looks."
      icon={User}
    >
      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="account">Account</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="account" className="space-y-6">
          <AccountTab />
        </TabsContent>
        <TabsContent value="appearance" className="space-y-6">
          <AppearanceTab />
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Profile tab — editable display name & job title (client-side presentation).
// ---------------------------------------------------------------------------

function ProfileTab() {
  const profile = useProfile();
  const updateProfile = useUpdateProfile();
  const [displayName, setDisplayName] = useState(profile.displayName);
  const [jobTitle, setJobTitle] = useState(profile.jobTitle);
  const [department, setDepartment] = useState(profile.department ?? "");
  const [organization, setOrganization] = useState(profile.organization);
  const [saved, setSaved] = useState(false);

  // Keep the form in sync once the profile loads / changes (e.g. another tab).
  useEffect(() => {
    setDisplayName(profile.displayName);
    setJobTitle(profile.jobTitle);
    setDepartment(profile.department ?? "");
    setOrganization(profile.organization);
  }, [profile.displayName, profile.jobTitle, profile.department, profile.organization]);

  const dirty =
    displayName !== profile.displayName ||
    jobTitle !== profile.jobTitle ||
    department !== (profile.department ?? "") ||
    organization !== profile.organization;

  function handleSave() {
    updateProfile.mutate(
      {
        full_name: displayName.trim() || profile.displayName,
        job_title: jobTitle.trim(),
        department: department.trim(),
        organization: organization.trim(),
      },
      {
        onSuccess: () => {
          setSaved(true);
          window.setTimeout(() => setSaved(false), 2000);
        },
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>
          This is how you appear across the workspace — in the sidebar, top bar and reports.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-gradient-accent text-xl font-semibold text-accent-foreground">
            {profile.initials}
          </div>
          <div className="min-w-0">
            <div className="truncate text-lg font-semibold text-foreground">
              {profile.displayName}
            </div>
            <div className="truncate text-sm text-muted-foreground">
              {profile.jobTitle}
              {profile.organization ? ` · ${profile.organization}` : ""}
            </div>
          </div>
        </div>

        <Separator />

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="displayName">Display name</Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your full name"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="jobTitle">Job title</Label>
            <Input
              id="jobTitle"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="e.g. Senior Credit Analyst"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="department">Department</Label>
            <Input
              id="department"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="e.g. Credit Risk"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="organization">Organization</Label>
            <Input
              id="organization"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              placeholder="e.g. HDFC Bank"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button onClick={handleSave} disabled={!dirty || updateProfile.isPending}>
            {updateProfile.isPending ? "Saving…" : "Save changes"}
          </Button>
          {saved && (
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-500">
              <Check className="h-4 w-4" /> Saved
            </span>
          )}
          {updateProfile.isError && (
            <span className="text-sm font-medium text-destructive">
              Couldn’t save. Please try again.
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Account tab — the signed-in identity (from the JWT + RBAC), read-only.
// ---------------------------------------------------------------------------

function AccountTab() {
  const profile = useProfile();
  const { data, isLoading } = useMyAccess();

  const roles = data?.roles ?? [];
  const permissionCount = data?.permissions?.length ?? 0;
  const email = data?.email ?? profile.email;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Account details</CardTitle>
          <CardDescription>
            Your account identity. These values come from your login and are managed by an
            administrator.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          <DetailRow icon={BadgeCheck} label="Full name" value={profile.displayName} />
          <DetailRow icon={AtSign} label="Username" value={profile.username} mono />
          <DetailRow icon={User} label="Email" value={email ?? "Not signed in"} mono />
          <DetailRow icon={Briefcase} label="Job title" value={profile.jobTitle} />
          <DetailRow icon={Network} label="Department" value={profile.department ?? "—"} />
          <DetailRow icon={Building2} label="Organization" value={profile.organization} />
          <DetailRow
            icon={Fingerprint}
            label="User ID"
            value={data?.user_id != null ? String(data.user_id) : isLoading ? "Loading…" : "—"}
            mono
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Roles &amp; access</CardTitle>
          <CardDescription>
            Roles determine what you can see and do. Contact an administrator to change these.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {isLoading && <span className="text-sm text-muted-foreground">Loading roles…</span>}
            {!isLoading && roles.length === 0 && (
              <span className="text-sm text-muted-foreground">
                No roles assigned{email ? "" : " — sign in to view your access"}.
              </span>
            )}
            {roles.map((role) => (
              <Badge key={role} variant="secondary" className="gap-1">
                <Shield className="h-3 w-3" />
                {role}
              </Badge>
            ))}
          </div>
          {permissionCount > 0 && (
            <p className="text-sm text-muted-foreground">
              {permissionCount} effective permission{permissionCount === 1 ? "" : "s"} granted.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: typeof User;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border py-3 last:border-0">
      <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <div className={cn("truncate text-sm font-medium text-foreground", mono && "font-mono")}>
        {value}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Appearance tab — layout preferences, incl. the full-screen / hide-sidebar toggle.
// ---------------------------------------------------------------------------

function AppearanceTab() {
  const { hidden, toggleHidden, collapsed, toggleCollapsed } = useNavigation();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Layout</CardTitle>
        <CardDescription>Control how much chrome the workspace shows.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        <PreferenceRow
          icon={hidden ? Maximize2 : Minimize2}
          title="Full-screen mode"
          description="Hide the sidebar entirely for a distraction-free view. Toggle any time with Ctrl+\\ or the button in the top bar."
          checked={hidden}
          onChange={toggleHidden}
        />
        <Separator />
        <PreferenceRow
          icon={Minimize2}
          title="Collapse sidebar to icons"
          description="Keep the sidebar as a slim icon rail that expands on hover. Toggle with Ctrl+B."
          checked={collapsed}
          onChange={toggleCollapsed}
          disabled={hidden}
        />
      </CardContent>
    </Card>
  );
}

function PreferenceRow({
  icon: Icon,
  title,
  description,
  checked,
  onChange,
  disabled,
}: {
  icon: typeof User;
  title: string;
  description: string;
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 py-4", disabled && "opacity-50")}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-secondary/40 text-muted-foreground">
          <Icon className="h-4 w-4" />
        </div>
        <div className="space-y-1">
          <div className="text-sm font-medium text-foreground">{title}</div>
          <p className="max-w-md text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} disabled={disabled} aria-label={title} />
    </div>
  );
}
