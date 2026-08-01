import { useEffect, useState } from "react";
import { fetchDocumentObjectUrl } from "../api";

/** Loads a document's original file as an object URL for the viewer, with cleanup. */
export function useDocumentFile(id: number | null) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id === null) {
      setUrl(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDocumentObjectUrl(id)
      .then((next) => {
        if (cancelled) {
          URL.revokeObjectURL(next);
          return;
        }
        objectUrl = next;
        setUrl(next);
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load file"))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  return { url, loading, error };
}
