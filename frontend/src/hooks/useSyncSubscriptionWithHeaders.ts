import { useEffect, useRef, useState } from "react";
import { env } from "../config/env";
import { SSEClient, createSSEConnection } from "../lib/sseClient";

interface SyncUpdate {
  updated?: number;
  inserted?: number;
  deleted?: number;
  [key: string]: any;
}

export function useSyncSubscriptionWithHeaders(jobId?: string | null) {
  const [updates, setUpdates] = useState<SyncUpdate[]>([]);
  const sseClientRef = useRef<SSEClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    // Create cleanup function
    let isMounted = true;
    const cleanup = () => {
      if (sseClientRef.current) {
        console.log("Closing sync subscription SSE client");
        sseClientRef.current.disconnect();
        sseClientRef.current = null;
        setIsConnected(false);
      }
    };

    // Setup SSE connection using the new client
    const setupSSEConnection = async () => {
      try {
        const url = `${env.VITE_API_URL}/sync/job/${jobId}/subscribe`;

        console.log(`Creating sync subscription to: ${jobId}`);

        const sseClient = createSSEConnection({
          url,
          onMessage: (data: SyncUpdate) => {
            console.log('[PubSub] Raw event received:', data);
            if (!isMounted) return;

            setUpdates((prev) => [...prev, data]);
          },
          onOpen: () => {
            setIsConnected(true);
            console.log('SSE connection established');
          },
          onClose: () => {
            setIsConnected(false);
            console.log('SSE connection closed');
          },
          onError: (error) => {
            console.error("Sync subscription failed:", error);
            setIsConnected(false);
          }
        });

        sseClientRef.current = sseClient;
        await sseClient.connect();

      } catch (error) {
        console.error("Error setting up sync subscription:", error);
        setIsConnected(false);
      }
    };

    // Start the connection
    void setupSSEConnection();

    // Return cleanup function
    return () => {
      isMounted = false;
      cleanup();
    };
  }, [jobId]);

  return {
    updates,
    latestUpdate: updates.length > 0 ? updates[updates.length - 1] : null,
    isConnected
  };
}
