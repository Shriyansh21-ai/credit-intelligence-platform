import { createFileRoute } from "@tanstack/react-router";

import {
  MetricCard,
  OpsLayout,
  SectionCard,
  StateWrap,
  StatusBadge,
  num,
  pct,
  useApproveModel,
  useModels,
  usePromoteModel,
  useRollbackModel,
  useSubmitModel,
  type MLModel,
} from "@/features/ml-platform";

export const Route = createFileRoute("/ml-registry")({ component: MLRegistryPage });

function MLRegistryPage() {
  const { data, isLoading, error } = useModels();
  const submit = useSubmitModel();
  const approve = useApproveModel();
  const promote = usePromoteModel();
  const rollback = useRollbackModel();

  const models = data?.models ?? [];
  const production = models.filter((m) => m.production_status === "production");
  const pending = models.filter((m) => m.approval_status === "pending");

  return (
    <OpsLayout
      title="Model Registry"
      description="Every trained model version, its metrics, governance state and deployment lifecycle. Promote, approve or roll back production models."
    >
      <StateWrap loading={isLoading} error={(error as Error)?.message ?? null} empty={!isLoading && !models.length}
        emptyMessage="No models registered yet. Train one from the Training Dashboard.">
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Registered Models" value={models.length} />
            <MetricCard label="In Production" value={production.length}
              tone={production.length ? "text-emerald-500" : undefined} />
            <MetricCard label="Awaiting Approval" value={pending.length}
              tone={pending.length ? "text-amber-500" : undefined} />
            <MetricCard label="Model Families" value={new Set(models.map((m) => m.model_key)).size} />
          </div>

          <SectionCard title="Registered models" description="Newest versions first, grouped by model family.">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-3">Model</th>
                    <th className="py-2 pr-3">Ver</th>
                    <th className="py-2 pr-3">ROC-AUC</th>
                    <th className="py-2 pr-3">KS</th>
                    <th className="py-2 pr-3">Gini</th>
                    <th className="py-2 pr-3">Approval</th>
                    <th className="py-2 pr-3">Production</th>
                    <th className="py-2 pr-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <ModelRow
                      key={m.id}
                      model={m}
                      busy={submit.isPending || approve.isPending || promote.isPending || rollback.isPending}
                      onSubmit={() => submit.mutate(m.id)}
                      onApprove={() => approve.mutate(m.id)}
                      onPromote={() => promote.mutate(m.id)}
                      onRollback={() => rollback.mutate(m.model_key)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      </StateWrap>
    </OpsLayout>
  );
}

function ModelRow({
  model,
  busy,
  onSubmit,
  onApprove,
  onPromote,
  onRollback,
}: {
  model: MLModel;
  busy: boolean;
  onSubmit: () => void;
  onApprove: () => void;
  onPromote: () => void;
  onRollback: () => void;
}) {
  const metrics = model.metrics ?? {};
  return (
    <tr className="border-b border-border/60">
      <td className="py-2 pr-3 font-medium text-foreground">{model.model_key}</td>
      <td className="py-2 pr-3 font-mono text-muted-foreground">v{model.version}</td>
      <td className="py-2 pr-3">{pct(metrics.roc_auc as number, 1)}</td>
      <td className="py-2 pr-3">{num(metrics.ks_statistic as number, 3)}</td>
      <td className="py-2 pr-3">{num(metrics.gini as number, 3)}</td>
      <td className="py-2 pr-3"><StatusBadge status={model.approval_status} /></td>
      <td className="py-2 pr-3"><StatusBadge status={model.production_status} /></td>
      <td className="py-2 pr-3">
        <div className="flex flex-wrap gap-1.5">
          {model.approval_status === "draft" && <ActionBtn label="Submit" onClick={onSubmit} disabled={busy} />}
          {model.approval_status === "pending" && <ActionBtn label="Approve" onClick={onApprove} disabled={busy} />}
          {model.approval_status === "approved" && model.production_status !== "production" && (
            <ActionBtn label="Promote" onClick={onPromote} disabled={busy} tone="primary" />
          )}
          {model.production_status === "production" && (
            <ActionBtn label="Rollback" onClick={onRollback} disabled={busy} tone="danger" />
          )}
        </div>
      </td>
    </tr>
  );
}

function ActionBtn({
  label,
  onClick,
  disabled,
  tone = "default",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "primary" | "danger";
}) {
  const toneClass =
    tone === "primary"
      ? "bg-primary text-primary-foreground hover:opacity-90"
      : tone === "danger"
        ? "border border-red-500/40 text-red-500 hover:bg-red-500/10"
        : "border border-border text-foreground hover:bg-muted";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${toneClass}`}
    >
      {label}
    </button>
  );
}
