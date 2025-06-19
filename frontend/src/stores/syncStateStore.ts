import { create } from 'zustand';
import { fetchEventSource, EventSourceMessage } from '@microsoft/fetch-event-source';
import { env } from '@/config/env';
import { apiClient } from '@/lib/api';
import { useOrganizationStore } from '@/lib/stores/organizations';

// Types for sync progress updates
export interface SyncProgressUpdate {
    entities_inserted: number;
    entities_updated: number;
    entities_deleted: number;
    entities_kept: number;
    entities_skipped: number;
    entities_encountered: Record<string, number>;
    is_complete?: boolean;
    is_failed?: boolean;
    error?: string;
}

// Individual subscription tracking
export interface SyncSubscription {
    jobId: string;
    sourceConnectionId: string;
    controller: AbortController;
    lastUpdate: SyncProgressUpdate;
    lastMessageTime: number;
    status: 'active' | 'completed' | 'failed';
}

// Store interface
interface SyncStateStore {
    // Map of sourceConnectionId -> SyncSubscription
    activeSubscriptions: Map<string, SyncSubscription>;

    // Subscribe to a sync job
    subscribe: (jobId: string, sourceConnectionId: string) => Promise<void>;

    // Unsubscribe from a sync job
    unsubscribe: (sourceConnectionId: string) => void;

    // Update progress for a source connection
    updateProgress: (sourceConnectionId: string, update: SyncProgressUpdate) => void;

    // Get current progress for a source connection
    getProgressForSource: (sourceConnectionId: string) => SyncProgressUpdate | null;

    // Check if a source has an active subscription
    hasActiveSubscription: (sourceConnectionId: string) => boolean;

    // Clean up all subscriptions
    cleanup: () => void;

    // Health check management
    startHealthCheck: () => void;
    stopHealthCheck: () => void;
}

// Keep track of the health check interval ID outside the store
let healthCheckIntervalId: NodeJS.Timeout | null = null;

// Create the store
export const useSyncStateStore = create<SyncStateStore>((set, get) => ({
    activeSubscriptions: new Map(),

    subscribe: async (jobId: string, sourceConnectionId: string) => {
        const state = get();

        // Start health check if it's the first subscription
        if (state.activeSubscriptions.size === 0) {
            state.startHealthCheck();
        }

        // Don't create duplicate subscriptions
        if (state.activeSubscriptions.has(sourceConnectionId)) {
            console.log(`Already subscribed to ${sourceConnectionId}`);
            return;
        }

        try {
            // Get token and organization ID for request
            const token = await apiClient.getToken();
            const organizationId = useOrganizationStore.getState().currentOrganization?.id;

            const headers: Record<string, string> = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            if (organizationId) {
                headers['X-Organization-Id'] = organizationId;
            } else {
                console.error('Cannot subscribe to SSE: No active organization selected.');
                return;
            }

            const controller = new AbortController();

            // Create and add the subscription to the store *before* connecting
            const subscription: SyncSubscription = {
                jobId,
                sourceConnectionId,
                controller,
                lastUpdate: {
                    entities_inserted: 0,
                    entities_updated: 0,
                    entities_deleted: 0,
                    entities_kept: 0,
                    entities_skipped: 0,
                    entities_encountered: {}
                },
                lastMessageTime: Date.now(),
                status: 'active'
            };

            const newSubscriptions = new Map(state.activeSubscriptions);
            newSubscriptions.set(sourceConnectionId, subscription);
            set({ activeSubscriptions: newSubscriptions });

            console.log(`✅ Subscribed to sync job ${jobId} for ${sourceConnectionId}`);

            // Use the proper API base URL from env config
            const apiBaseUrl = env.VITE_API_URL;
            // We don't await this call, so the UI doesn't block. It runs in the background.
            void fetchEventSource(`${apiBaseUrl}/sync/job/${jobId}/subscribe`, {
                signal: controller.signal,
                headers,
                onopen: async (response) => {
                    if (response.ok) {
                        console.log(`✅ SSE connection opened for ${sourceConnectionId}`);
                        return;
                    }

                    const status = response.status;
                    if (status === 401 || status === 403) {
                        apiClient.clearToken();
                        throw new Error(`SSE authentication failed with status ${status}`);
                    } else if (status === 404) {
                        throw new Error(`SSE endpoint not found for job ${jobId}.`);
                    } else {
                        throw new Error(`SSE connection failed with status ${status}: ${response.statusText}`);
                    }
                },
                onmessage: (event: EventSourceMessage) => {
                    try {
                        const data = JSON.parse(event.data);
                        console.log(`📨 SSE message for ${sourceConnectionId}:`, data);

                        // Skip non-progress messages
                        if (data.type === 'connected') {
                            console.log(`🔗 Connection established for ${sourceConnectionId}`);
                            return;
                        }

                        // Map the incoming data to our expected interface
                        // Backend sends: {inserted, updated, deleted, kept, skipped}
                        // We expect: {entities_inserted, entities_updated, etc.}
                        const mappedData: SyncProgressUpdate = {
                            entities_inserted: data.inserted ?? 0,
                            entities_updated: data.updated ?? 0,
                            entities_deleted: data.deleted ?? 0,
                            entities_kept: data.kept ?? 0,
                            entities_skipped: data.skipped ?? 0,
                            entities_encountered: data.entities_encountered || {},
                            is_complete: data.is_complete,
                            is_failed: data.is_failed,
                            error: data.error
                        };

                        // Update progress with mapped data
                        get().updateProgress(sourceConnectionId, mappedData);

                        // Handle completion
                        if (data.is_complete || data.is_failed) {
                            console.log(`Sync ${data.is_complete ? 'completed' : 'failed'} for ${sourceConnectionId}`);

                            // Wait a bit for final DB write, then switch to completed status
                            setTimeout(() => {
                                const sub = get().activeSubscriptions.get(sourceConnectionId);
                                if (sub) {
                                    const previousStatus = sub.status;
                                    sub.status = data.is_complete ? 'completed' : 'failed';
                                    console.log(`📊 Subscription status changed for ${sourceConnectionId}: ${previousStatus} -> ${sub.status}`);
                                    set({ activeSubscriptions: new Map(get().activeSubscriptions) });
                                }

                                // Unsubscribe after another delay
                                setTimeout(() => {
                                    get().unsubscribe(sourceConnectionId);
                                }, 2000);
                            }, 2000);
                        }
                    } catch (error) {
                        console.error('Error parsing SSE message:', error);
                    }
                },
                onerror: (error) => {
                    console.error(`SSE error for ${sourceConnectionId}, unsubscribing:`, error);
                    // Stop retrying by unsubscribing, which aborts the controller
                    get().unsubscribe(sourceConnectionId);
                    // Re-throw error to prevent the library from continuing
                    throw error;
                },
                onclose: () => {
                    console.log(`SSE connection closed for ${sourceConnectionId}.`);
                }
            });
        } catch (error) {
            console.error(`Failed to subscribe to ${sourceConnectionId}:`, error);
        }
    },

    unsubscribe: (sourceConnectionId: string) => {
        const state = get();
        const subscription = state.activeSubscriptions.get(sourceConnectionId);

        if (!subscription) {
            return;
        }

        // Close the EventSource connection
        subscription.controller.abort();

        // Remove from active subscriptions
        const newSubscriptions = new Map(state.activeSubscriptions);
        newSubscriptions.delete(sourceConnectionId);
        set({ activeSubscriptions: newSubscriptions });

        // If it was the last subscription, stop the health check
        if (newSubscriptions.size === 0) {
            get().stopHealthCheck();
        }

        console.log(`🔌 Unsubscribed from ${sourceConnectionId}`);
    },

    updateProgress: (sourceConnectionId: string, update: SyncProgressUpdate) => {
        const state = get();
        const subscription = state.activeSubscriptions.get(sourceConnectionId);

        if (!subscription) {
            console.warn(`No subscription found for ${sourceConnectionId}`);
            return;
        }

        console.log('🔄 Updating progress for', sourceConnectionId, {
            update,
            previousUpdate: subscription.lastUpdate,
            willTriggerRerender: true
        });

        // Update the subscription
        subscription.lastUpdate = update;
        subscription.lastMessageTime = Date.now();

        // Update the map to trigger re-render
        const newSubscriptions = new Map(state.activeSubscriptions);
        newSubscriptions.set(sourceConnectionId, { ...subscription });
        set({ activeSubscriptions: newSubscriptions });
    },

    getProgressForSource: (sourceConnectionId: string) => {
        const subscription = get().activeSubscriptions.get(sourceConnectionId);
        return subscription?.lastUpdate || null;
    },

    hasActiveSubscription: (sourceConnectionId: string) => {
        const subscription = get().activeSubscriptions.get(sourceConnectionId);
        return subscription?.status === 'active';
    },

    cleanup: () => {
        const state = get();

        // Close all EventSource connections
        state.activeSubscriptions.forEach((subscription) => {
            subscription.controller.abort();
        });

        // Clear the map
        set({ activeSubscriptions: new Map() });
        get().stopHealthCheck(); // Stop health checks

        console.log('🧹 Cleaned up all sync subscriptions');
    },

    startHealthCheck: () => {
        if (healthCheckIntervalId) {
            return; // Already running
        }
        console.log('🩺 Starting sync health check...');
        healthCheckIntervalId = setInterval(() => {
            const store = useSyncStateStore.getState();
            const now = Date.now();
            const staleThreshold = 60 * 60 * 1000; // 1 hour

            store.activeSubscriptions.forEach((subscription, sourceConnectionId) => {
                if (subscription.status === 'active' &&
                    (now - subscription.lastMessageTime) > staleThreshold) {
                    console.warn(`⚠️ No messages for ${sourceConnectionId} in 1 hour`);
                    // TODO: Implement verifyJobStatus check
                }
            });
        }, 5 * 60 * 1000);
    },

    stopHealthCheck: () => {
        if (healthCheckIntervalId) {
            console.log('🩺 Stopping sync health check...');
            clearInterval(healthCheckIntervalId);
            healthCheckIntervalId = null;
        }
    }
}));

// Set up a listener to clean up when the user leaves the app
window.addEventListener('beforeunload', () => {
    useSyncStateStore.getState().cleanup();
});
