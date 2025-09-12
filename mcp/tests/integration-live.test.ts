// Integration tests against live Airweave API
// These tests require a running Airweave instance

import { describe, it, expect, beforeAll } from 'vitest';
import { AirweaveClient } from '../src/api/airweave-client.js';
import { AirweaveConfig } from '../src/api/types.js';

// Check if we have the required environment variables
const hasApiCredentials = !!(process.env.AIRWEAVE_API_KEY && process.env.AIRWEAVE_COLLECTION);

describe('MCP Server Integration with Live API', () => {
    let airweaveClient: AirweaveClient;
    let config: AirweaveConfig;

    beforeAll(() => {
        if (!hasApiCredentials) {
            console.log('⚠️  Skipping integration tests - AIRWEAVE_API_KEY and AIRWEAVE_COLLECTION environment variables are required');
            return;
        }

        // Get configuration from environment variables
        const apiKey = process.env.AIRWEAVE_API_KEY!;
        const collection = process.env.AIRWEAVE_COLLECTION!;
        const baseUrl = process.env.AIRWEAVE_BASE_URL || 'http://localhost:8001';

        config = { apiKey, collection, baseUrl };
        airweaveClient = new AirweaveClient(config);
    });

    describe('Basic Search Functionality', () => {
        it('should perform a basic search', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test search',
                limit: 5
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
            expect(Array.isArray(response.results)).toBe(true);
            expect(response.status).toBeDefined();
        });

        it('should handle pagination parameters', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                limit: 3,
                offset: 0
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results.length).toBeLessThanOrEqual(3);
        });

        it('should handle recency bias parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                recency_bias: 0.8
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
        });

        it('should handle response type parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                response_type: 'completion'
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.response_type).toBe('completion');
        });
    });

    describe('Advanced Search Functionality', () => {
        it('should handle score threshold parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                score_threshold: 0.5
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
            // All results should have score >= threshold (if any results returned)
            if (response.results.length > 0) {
                response.results.forEach(result => {
                    expect(result.score).toBeGreaterThanOrEqual(0.5);
                });
            }
        });

        it('should handle search method parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                search_method: 'neural'
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
        });

        it('should handle expansion strategy parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                expansion_strategy: 'no_expansion'
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
        });

        it('should handle reranking parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                enable_reranking: false
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
        });

        it('should handle query interpretation parameter', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'test',
                enable_query_interpretation: false
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
        });

        it('should handle complex advanced search combinations', async () => {
            if (!hasApiCredentials) return;

            const searchRequest = {
                query: 'machine learning',
                score_threshold: 0.7,
                search_method: 'neural',
                expansion_strategy: 'llm',
                enable_reranking: true,
                enable_query_interpretation: true,
                limit: 5,
                response_type: 'completion'
            };

            const response = await airweaveClient.search(searchRequest);

            expect(response).toBeDefined();
            expect(response.results).toBeDefined();
            expect(response.response_type).toBe('completion');
            expect(response.results.length).toBeLessThanOrEqual(5);

            // All results should meet the score threshold
            if (response.results.length > 0) {
                response.results.forEach(result => {
                    expect(result.score).toBeGreaterThanOrEqual(0.7);
                });
            }
        });
    });

    // Error handling tests require real API credentials
    // These will be added back when running in CI with real credentials

    describe('Response Format', () => {
        it('should return properly formatted response', async () => {
            if (!hasApiCredentials) return;

            const response = await airweaveClient.search({ query: 'test' });

            expect(response).toHaveProperty('results');
            expect(response).toHaveProperty('response_type');
            expect(response).toHaveProperty('status');
            expect(Array.isArray(response.results)).toBe(true);
        });

        it('should include completion for completion response type', async () => {
            if (!hasApiCredentials) return;

            const response = await airweaveClient.search({
                query: 'test',
                response_type: 'completion'
            });

            if (response.response_type === 'completion') {
                expect(response.completion).toBeDefined();
            }
        });
    });
});
