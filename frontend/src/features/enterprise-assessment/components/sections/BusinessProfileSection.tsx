import { Building2 } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { SectionCard } from "../shared/SectionCard";
import { NumberInput, SelectInput, TextInput } from "../shared/fields";
import { BUSINESS_TYPE_OPTIONS, INDUSTRY_OPTIONS } from "../../constants";
import type { EnterpriseAssessmentFormValues } from "../../validation";

interface Props {
  register: UseFormRegister<EnterpriseAssessmentFormValues>;
  errors: FieldErrors<EnterpriseAssessmentFormValues>;
}

export function BusinessProfileSection({ register, errors }: Props) {
  const e = errors.business_profile;
  return (
    <SectionCard
      step={1}
      title="Business Profile"
      description="Identity and standing of the borrowing entity."
      icon={Building2}
    >
      <TextInput label="Company name" required registration={register("business_profile.company_name")} error={e?.company_name?.message} />
      <SelectInput label="Industry" required options={INDUSTRY_OPTIONS} registration={register("business_profile.industry")} error={e?.industry?.message} />
      <SelectInput label="Business type" required options={BUSINESS_TYPE_OPTIONS} registration={register("business_profile.business_type")} error={e?.business_type?.message} />
      <NumberInput label="Years in business" required min={0} registration={register("business_profile.years_in_business")} error={e?.years_in_business?.message} />
      <NumberInput label="Employee count" required min={1} registration={register("business_profile.employee_count")} error={e?.employee_count?.message} />
      <TextInput label="Head office" required registration={register("business_profile.head_office")} error={e?.head_office?.message} />
      <TextInput label="Country" required registration={register("business_profile.country")} error={e?.country?.message} />
      <TextInput label="Registration number" registration={register("business_profile.registration_number")} error={e?.registration_number?.message} hint="Optional" />
      <TextInput label="GST number" registration={register("business_profile.gst_number")} error={e?.gst_number?.message} hint="Optional" />
      <TextInput label="Website" registration={register("business_profile.website")} error={e?.website?.message} hint="Optional" placeholder="https://" />
    </SectionCard>
  );
}
