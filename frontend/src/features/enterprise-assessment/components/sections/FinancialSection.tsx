import { LineChart } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";
import { SectionCard } from "../shared/SectionCard";
import { NumberInput } from "../shared/fields";
import type { EnterpriseAssessmentFormValues } from "../../validation";

interface Props {
  register: UseFormRegister<EnterpriseAssessmentFormValues>;
  errors: FieldErrors<EnterpriseAssessmentFormValues>;
}

export function FinancialSection({ register, errors }: Props) {
  const e = errors.financials;
  return (
    <SectionCard
      step={2}
      title="Financial Performance"
      description="Latest full-year P&L, balance-sheet and cash-flow figures."
      icon={LineChart}
    >
      <NumberInput label="Annual revenue" required min={0} registration={register("financials.annual_revenue")} error={e?.annual_revenue?.message} />
      <NumberInput label="Gross profit" registration={register("financials.gross_profit")} error={e?.gross_profit?.message} />
      <NumberInput label="Net profit" registration={register("financials.net_profit")} error={e?.net_profit?.message} hint="May be negative" />
      <NumberInput label="EBITDA" registration={register("financials.ebitda")} error={e?.ebitda?.message} hint="May be negative" />
      <NumberInput label="Operating expenses" min={0} registration={register("financials.operating_expenses")} error={e?.operating_expenses?.message} />
      <NumberInput label="Cash & equivalents" min={0} registration={register("financials.cash_and_cash_equivalents")} error={e?.cash_and_cash_equivalents?.message} />
      <NumberInput label="Working capital" registration={register("financials.working_capital")} error={e?.working_capital?.message} hint="CA − CL" />
      <NumberInput label="Current assets" min={0} registration={register("financials.current_assets")} error={e?.current_assets?.message} />
      <NumberInput label="Current liabilities" min={0} registration={register("financials.current_liabilities")} error={e?.current_liabilities?.message} />
      <NumberInput label="Inventory" min={0} registration={register("financials.inventory")} error={e?.inventory?.message} />
      <NumberInput label="Accounts receivable" min={0} registration={register("financials.accounts_receivable")} error={e?.accounts_receivable?.message} />
      <NumberInput label="Accounts payable" min={0} registration={register("financials.accounts_payable")} error={e?.accounts_payable?.message} />
      <NumberInput label="Long-term debt" min={0} registration={register("financials.long_term_debt")} error={e?.long_term_debt?.message} />
      <NumberInput label="Short-term debt" min={0} registration={register("financials.short_term_debt")} error={e?.short_term_debt?.message} />
      <NumberInput label="Operating cash flow" registration={register("financials.operating_cash_flow")} error={e?.operating_cash_flow?.message} hint="May be negative" />
      <NumberInput label="Interest expense" min={0} registration={register("financials.interest_expense")} error={e?.interest_expense?.message} />
      <NumberInput label="Free cash flow" registration={register("financials.free_cash_flow")} error={e?.free_cash_flow?.message} hint="May be negative" />
      <NumberInput label="Net worth" registration={register("financials.net_worth")} error={e?.net_worth?.message} />
    </SectionCard>
  );
}
