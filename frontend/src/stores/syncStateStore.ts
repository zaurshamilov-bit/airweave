import { create } from 'zustand';
import { EventSourcePolyfill } from 'event-source-polyfill';
import { env } from '@/config/env';
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
}

// Individual subscription tracking
export interface SyncSubscription {
    jobId: string;
    sourceConnectionId: string;
    eventSource: EventSourcePolyfill;
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
    cleanup: () => void;
}

// Create the store
export const useSyncStateStore = create<SyncStateStore>((set, get) => ({
    activeSubscriptions: new Map(),

    subscribe: async (jobId: string, sourceConnectionId: string) => {
        const state = get();

        // Don't create duplicate subscriptions
        if (state.activeSubscriptions.has(sourceConnectionId)) {
            console.log(`Already subscribed to ${sourceConnectionId}`);
            return;
        }

        try {
            // Check if we have existing progress data (from restoration)
            const existingSubscription = state.activeSubscriptions.get(sourceConnectionId);
            const existingProgress = existingSubscription?.lastUpdate;

            // Create EventSource with auth token
            const token = localStorage.getItem('authToken');

            // Use the proper API base URL from env config
            const apiBaseUrl = env.VITE_API_URL;
            const eventSource = new EventSourcePolyfill(
                `${apiBaseUrl}/sync/job/${jobId}/subscribe`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );

            // Handle incoming messages
            eventSource.onmessage = (event) => {
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
                            const sub = state.activeSubscriptions.get(sourceConnectionId);
                            if (sub) {
                                const previousStatus = sub.status;
                                sub.status = data.is_complete ? 'completed' : 'failed';
                                console.log(`📊 Subscription status changed for ${sourceConnectionId}: ${previousStatus} -> ${sub.status}`);
                                set({ activeSubscriptions: new Map(state.activeSubscriptions) });
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
            };

            // Handle errors
            eventSource.onerror = (error) => {
                console.error(`SSE error for ${sourceConnectionId}:`, error);

                // Log more details about the error
                if (error instanceof Event && error.target) {
                    const target = error.target as EventSourcePolyfill;
                    console.error(`SSE Connection State: readyState=${target.readyState}, url=${target.url}`);
                }

                // Don't immediately unsubscribe - SSE will auto-reconnect
                // But if we get a 404, the endpoint doesn't exist
                if ((error as any).status === 404) {
                    console.error(`SSE endpoint not found for job ${jobId}. The sync job may not exist or the endpoint is incorrect.`);
                }
            };

            // Add open handler for debugging
            eventSource.onopen = () => {
                console.log(`✅ SSE connection opened for ${sourceConnectionId}`);
            };

            // Create subscription object, preserving existing progress if available
            const subscription: SyncSubscription = {
                jobId,
                sourceConnectionId,
                eventSource,
                lastUpdate: existingProgress || {
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

            // Add to active subscriptions
            const newSubscriptions = new Map(state.activeSubscriptions);
            newSubscriptions.set(sourceConnectionId, subscription);
            set({ activeSubscriptions: newSubscriptions });

            console.log(`✅ Subscribed to sync job ${jobId} for ${sourceConnectionId}`,
                existingProgress ? 'with restored progress' : 'with fresh progress');

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
        subscription.eventSource.close();

        // Remove from active subscriptions
        const newSubscriptions = new Map(state.activeSubscriptions);
        newSubscriptions.delete(sourceConnectionId);
        set({ activeSubscriptions: newSubscriptions });

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
                eventSource: null as any, // Will be replaced when real subscription starts
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

    cleanup: () => {
        const state = get();

        // Close all EventSource connections
        state.activeSubscriptions.forEach((subscription) => {
            subscription.eventSource.close();
        });

        // Clear the map
        set({ activeSubscriptions: new Map() });

        console.log('🧹 Cleaned up all sync subscriptions');
    }
}));

// Health check interval (runs every 5 minutes)
setInterval(() => {
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
