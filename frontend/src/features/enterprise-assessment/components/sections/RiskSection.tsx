import { ShieldAlert } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { SectionCard } from "../shared/SectionCard";
import { SelectInput } from "../shared/fields";
import { CONCENTRATION_OPTIONS, EXPANSION_STAGE_OPTIONS, RISK_BAND_OPTIONS } from "../../constants";
import type { EnterpriseAssessmentFormValues } from "../../validation";

interface Props {
  register: UseFormRegister<EnterpriseAssessmentFormValues>;
  errors: FieldErrors<EnterpriseAssessmentFormValues>;
}

export function RiskSection({ register, errors }: Props) {
  const e = errors.risk_profile;
  return (
    <SectionCard
      step={4}
      title="Business Risk"
      description="Qualitative exposure across market, geography and concentration."
      icon={ShieldAlert}
    >
      <SelectInput label="Industry risk" options={RISK_BAND_OPTIONS} registration={register("risk_profile.industry_risk")} error={e?.industry_risk?.message} />
      <SelectInput label="Geographical risk" options={RISK_BAND_OPTIONS} registration={register("risk_profile.geographical_risk")} error={e?.geographical_risk?.message} />
      <SelectInput label="Supplier concentration" options={CONCENTRATION_OPTIONS} registration={register("risk_profile.supplier_concentration")} error={e?.supplier_concentration?.message} />
      <SelectInput label="Customer concentration" options={CONCENTRATION_OPTIONS} registration={register("risk_profile.customer_concentration")} error={e?.customer_concentration?.message} />
      <SelectInput label="Business expansion stage" options={EXPANSION_STAGE_OPTIONS} registration={register("risk_profile.business_expansion_stage")} error={e?.business_expansion_stage?.message} />
    </SectionCard>
  );
}
