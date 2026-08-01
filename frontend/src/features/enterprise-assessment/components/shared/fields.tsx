/**
 * Re-exports the shared form primitives (promoted to components/form during
 * Phase 2). Kept here so existing imports within this feature stay stable.
 */
export {
  FieldShell,
  TextInput,
  NumberInput,
  SelectInput,
  controlClass,
  type SelectOption,
} from "@/components/form/fields";
