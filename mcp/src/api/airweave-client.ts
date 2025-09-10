// Airweave API client using the official SDK

import { AirweaveSDKClient } from '@airweave/sdk';
import { AirweaveConfig, SearchResponse } from './types.js';

export class AirweaveClient {
    private client: AirweaveSDKClient;

    constructor(private config: AirweaveConfig) {
        this.client = new AirweaveSDKClient({
            apiKey: config.apiKey,
            baseUrl: config.baseUrl
        });
    }

    async search(searchRequest: any): Promise<SearchResponse> {
        const { query, response_type, limit, offset, recency_bias } = searchRequest;

        // Mock mode for testing
        if (this.config.apiKey === 'test-key' && this.config.baseUrl.includes('localhost')) {
            return this.getMockResponse(searchRequest);
        }

        try {
            // Use the official SDK for the search request
            const response = await this.client.collections.search(this.config.collection, {
                query,
                response_type,
                limit,
                offset,
                recency_bias
            });

            return response;
        } catch (error: any) {
            // Handle SDK errors and convert to our error format
            if (error.statusCode) {
                throw new Error(`Airweave API error (${error.statusCode}): ${error.message}`);
            } else {
                throw new Error(`Airweave API error: ${error.message}`);
            }
        }
    }

    private getMockResponse(request: any): SearchResponse {
        const { query, response_type, limit, offset, recency_bias } = request;

        // Generate mock results based on the query
        const mockResults = [];
        const resultCount = Math.min(limit || 100, 5); // Limit to 5 for testing

        for (let i = 0; i < resultCount; i++) {
            mockResults.push({
                score: 0.95 - (i * 0.1),
                payload: {
                    source_name: `Mock Source ${i + 1}`,
                    entity_id: `mock_${i + 1}`,
                    title: `Mock Document ${i + 1} about "${query}"`,
                    md_content: `This is a mock response for the query "${query}". This document contains relevant information about ${query} and demonstrates how the MCP server would return search results.`,
                    created_at: new Date(Date.now() - (i * 24 * 60 * 60 * 1000)).toISOString(), // Different dates
                    metadata: {
                        test: true,
                        query: query,
                        limit: limit,
                        offset: offset,
                        recency_bias: recency_bias
                    }
                }
            });
        }

        return {
            results: mockResults,
            response_type: response_type || "raw",
            status: "success",
            completion: response_type === "completion"
                ? `Based on the search results for "${query}", here's a comprehensive summary of the findings...`
                : undefined
        };
    }
}
