import { create } from 'zustand';
import { fetchEventSource, EventSourceMessage } from '@microsoft/fetch-event-source';
import { env } from '@/config/env';
import { apiClient } from '@/lib/api';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { syncStorageService } from '@/services/syncStorageService';

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
    started_at?: string;
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

    // Restore progress from storage (for page reloads)
    restoreProgressFromStorage: (sourceConnectionId: string, jobId: string) => void;

    // Clean up all subscriptions
    cleanup: (clearStorage?: boolean) => void;

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

            if (!token) {
                console.error('Cannot subscribe to SSE: No authentication token available.');
                return;
            }

            if (!organizationId) {
                console.error('Cannot subscribe to SSE: No active organization selected.');
                return;
            }

            const headers: Record<string, string> = {
                'Authorization': `Bearer ${token}`,
                'X-Organization-ID': organizationId
            };

            const controller = new AbortController();

            // Check for existing progress data to preserve during subscription
            const existingSubscription = state.activeSubscriptions.get(sourceConnectionId);
            const storedData = syncStorageService.getProgressForSource(sourceConnectionId);

            // Determine what progress data to use (priority: existing > stored > default zeros)
            let lastUpdate: SyncProgressUpdate;
            if (existingSubscription && existingSubscription.jobId === jobId) {
                // Same job, preserve existing progress
                lastUpdate = existingSubscription.lastUpdate;
                console.log(`🔄 Preserving existing progress for ${sourceConnectionId}:`, lastUpdate);
            } else if (storedData && storedData.jobId === jobId && storedData.status === 'active') {
                // Different job or fresh subscription, but we have stored data for this job
                lastUpdate = storedData.lastUpdate;
                console.log(`💾 Using stored progress for ${sourceConnectionId}:`, lastUpdate);
            } else {
                // No existing data, start fresh
                lastUpdate = {
                    entities_inserted: 0,
                    entities_updated: 0,
                    entities_deleted: 0,
                    entities_kept: 0,
                    entities_skipped: 0,
                    entities_encountered: {}
                };
                console.log(`🆕 Starting fresh progress for ${sourceConnectionId}`);
            }

            // Create and add the subscription to the store *before* connecting
            const subscription: SyncSubscription = {
                jobId,
                sourceConnectionId,
                controller,
                lastUpdate,
                lastMessageTime: Date.now(),
                status: 'active'
            };

            const newSubscriptions = new Map(state.activeSubscriptions);
            newSubscriptions.set(sourceConnectionId, subscription);
            set({ activeSubscriptions: newSubscriptions });

            // Use the proper API base URL from env config
            const apiBaseUrl = env.VITE_API_URL;
            const sseUrl = `${apiBaseUrl}/sync/job/${jobId}/subscribe`;

            console.log(`✅ Starting SSE subscription:`, {
                url: sseUrl,
                jobId,
                sourceConnectionId,
                hasToken: !!token,
                organizationId,
                headers
            });

            // We don't await this call, so the UI doesn't block. It runs in the background.
            void fetchEventSource(sseUrl, {
                signal: controller.signal,
                headers,
                onopen: async (response) => {
                    if (response.ok) {
                        console.log(`✅ SSE connection opened for ${sourceConnectionId}`);
                        return;
                    }

                    const status = response.status;
                    const errorText = await response.text();
                    console.error(`❌ SSE connection failed:`, {
                        status,
                        statusText: response.statusText,
                        errorText,
                        url: sseUrl,
                        headers
                    });

                    if (status === 401 || status === 403) {
                        apiClient.clearToken();
                        throw new Error(`SSE authentication failed with status ${status}: ${errorText}`);
                    } else if (status === 404) {
                        throw new Error(`SSE endpoint not found for job ${jobId}.`);
                    } else {
                        throw new Error(`SSE connection failed with status ${status}: ${response.statusText} - ${errorText}`);
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

        syncStorageService.removeProgress(sourceConnectionId);
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

        syncStorageService.saveProgress(sourceConnectionId, subscription.jobId, update);
    },

    getProgressForSource: (sourceConnectionId: string) => {
        const subscription = get().activeSubscriptions.get(sourceConnectionId);
        return subscription?.lastUpdate || null;
    },

    hasActiveSubscription: (sourceConnectionId: string) => {
        const subscription = get().activeSubscriptions.get(sourceConnectionId);
        return subscription?.status === 'active';
    },

    restoreProgressFromStorage: (sourceConnectionId: string, jobId: string) => {
        const storedData = syncStorageService.getProgressForSource(sourceConnectionId);

        console.log(`🔍 Checking stored progress for ${sourceConnectionId}:`, {
            found: !!storedData,
            storedData,
            requestedJobId: jobId,
            storedJobId: storedData?.jobId,
            matches: storedData?.jobId === jobId,
            storedStatus: storedData?.status
        });

        if (storedData && storedData.jobId === jobId && storedData.status === 'active') {
            console.log(`🔄 Restoring saved progress for ${sourceConnectionId} from session storage:`, storedData);

            // Create a "restored" subscription with the saved progress
            const subscription: SyncSubscription = {
                jobId,
                sourceConnectionId,
                controller: new AbortController(), // Placeholder, will be replaced by subscribe
                lastUpdate: storedData.lastUpdate,
                lastMessageTime: storedData.timestamp,
                status: 'active'
            };

            const newSubscriptions = new Map(get().activeSubscriptions);
            newSubscriptions.set(sourceConnectionId, subscription);
            set({ activeSubscriptions: newSubscriptions });

            console.log(`✅ Progress restored successfully for ${sourceConnectionId}`);
        } else {
            console.log(`❌ Could not restore progress for ${sourceConnectionId}:`, {
                hasStoredData: !!storedData,
                jobIdMatch: storedData?.jobId === jobId,
                statusIsActive: storedData?.status === 'active'
            });
        }
    },

    cleanup: (clearStorage: boolean = false) => {
        const state = get();

        // Close all EventSource connections
        state.activeSubscriptions.forEach((subscription) => {
            subscription.controller.abort();
        });

        // Clear the map
        set({ activeSubscriptions: new Map() });
        get().stopHealthCheck(); // Stop health checks

        // Only clear session storage if explicitly requested (e.g., user logout)
        if (clearStorage) {
            syncStorageService.clearAll();
            console.log('🧹 Cleaned up all sync subscriptions and cleared storage');
        } else {
            console.log('🧹 Cleaned up all sync subscriptions (preserving storage)');
        }
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
