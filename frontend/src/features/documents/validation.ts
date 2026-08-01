import { ACCEPTED_MIME_TYPES, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from "./constants";

export interface RejectedFile {
  name: string;
  reason: string;
}

export interface FileValidationResult {
  accepted: File[];
  rejected: RejectedFile[];
}

/** Client-side pre-flight validation before uploading (mirrors backend rules). */
export function validateFiles(files: File[]): FileValidationResult {
  const accepted: File[] = [];
  const rejected: RejectedFile[] = [];

  for (const file of files) {
    if (!ACCEPTED_MIME_TYPES.includes(file.type)) {
      rejected.push({ name: file.name, reason: "Unsupported type (PDF, PNG, JPG only)" });
      continue;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      rejected.push({ name: file.name, reason: `Exceeds ${MAX_UPLOAD_MB} MB limit` });
      continue;
    }
    accepted.push(file);
  }

  return { accepted, rejected };
}
