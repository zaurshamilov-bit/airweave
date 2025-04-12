import { useEffect, useRef, useState } from "react";
import { env } from "../config/env";

interface SyncUpdate {
  updated?: number;
  inserted?: number;
  deleted?: number;
  [key: string]: any;
}

export function useSyncSubscription(jobId?: string | null) {
  const [updates, setUpdates] = useState<SyncUpdate[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const url = `${env.VITE_API_URL}/sync/job/${jobId}/subscribe`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data: SyncUpdate = JSON.parse(event.data);
        setUpdates((prev) => [...prev, data]);
      } catch (err) {
        console.error("Failed to parse SSE data:", err);
      }
    };

    es.onerror = () => {
      console.error("Sync subscription failed. Closing connection.");
      es.close();
    };

    return () => {
      es.close();
    };
  }, [jobId]);

  return updates;
}
