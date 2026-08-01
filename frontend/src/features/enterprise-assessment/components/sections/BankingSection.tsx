import { Landmark } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { SectionCard } from "../shared/SectionCard";
import { NumberInput, SelectInput } from "../shared/fields";
import { COMPLIANCE_OPTIONS, PRIOR_DEFAULTS_OPTIONS } from "../../constants";
import type { EnterpriseAssessmentFormValues } from "../../validation";

interface Props {
  register: UseFormRegister<EnterpriseAssessmentFormValues>;
  errors: FieldErrors<EnterpriseAssessmentFormValues>;
}

export function BankingSection({ register, errors }: Props) {
  const e = errors.banking;
  return (
    <SectionCard
      step={3}
      title="Banking & Credit"
      description="Banking behaviour, existing obligations and credit conduct."
      icon={Landmark}
    >
      <NumberInput label="Avg monthly balance" min={0} registration={register("banking.average_monthly_balance")} error={e?.average_monthly_balance?.message} />
      <NumberInput label="Avg monthly inflow" min={0} registration={register("banking.average_monthly_inflow")} error={e?.average_monthly_inflow?.message} />
      <NumberInput label="Avg monthly outflow" min={0} registration={register("banking.average_monthly_outflow")} error={e?.average_monthly_outflow?.message} />
      <NumberInput label="Existing loans" min={0} registration={register("banking.existing_loans")} error={e?.existing_loans?.message} />
      <NumberInput label="Existing EMI (monthly)" min={0} registration={register("banking.existing_emi")} error={e?.existing_emi?.message} />
      <NumberInput label="Credit utilization" min={0} max={100} prefix="%" registration={register("banking.credit_utilization")} error={e?.credit_utilization?.message} />
      <SelectInput label="Tax compliance" options={COMPLIANCE_OPTIONS} registration={register("banking.tax_compliance")} error={e?.tax_compliance?.message} />
      <SelectInput label="GST compliance" options={COMPLIANCE_OPTIONS} registration={register("banking.gst_compliance")} error={e?.gst_compliance?.message} />
      <NumberInput label="Cheque bounce count" min={0} registration={register("banking.cheque_bounce_count")} error={e?.cheque_bounce_count?.message} />
      <SelectInput label="Previous defaults" options={PRIOR_DEFAULTS_OPTIONS} registration={register("banking.previous_defaults")} error={e?.previous_defaults?.message} />
    </SectionCard>
  );
}
