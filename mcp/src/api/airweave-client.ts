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
        // Mock mode for testing
        if (this.config.apiKey === 'test-key' && this.config.baseUrl.includes('localhost')) {
            return this.getMockResponse(searchRequest);
        }

        try {
            // Check if this should use advanced search (POST endpoint)
            const hasAdvancedParams = this.hasAdvancedParameters(searchRequest);

            if (hasAdvancedParams) {
                // Use the official SDK for advanced search
                const response = await this.client.collections.searchAdvanced(this.config.collection, searchRequest);
                return response;
            } else {
                // Use the official SDK for basic search
                const { query, response_type, limit, offset, recency_bias } = searchRequest;
                const response = await this.client.collections.search(this.config.collection, {
                    query,
                    response_type,
                    limit,
                    offset,
                    recency_bias
                });
                return response;
            }
        } catch (error: any) {
            // Handle SDK errors and convert to our error format
            if (error.statusCode) {
                throw new Error(`Airweave API error (${error.statusCode}): ${error.message}`);
            } else {
                throw new Error(`Airweave API error: ${error.message}`);
            }
        }
    }

    private hasAdvancedParameters(params: any): boolean {
        return !!(
            params.score_threshold !== undefined ||
            params.search_method !== undefined ||
            params.expansion_strategy !== undefined ||
            params.enable_reranking !== undefined ||
            params.enable_query_interpretation !== undefined
        );
    }

    private getMockResponse(request: any): SearchResponse {
        const { query, response_type, limit, offset, recency_bias, score_threshold, search_method, expansion_strategy, enable_reranking, enable_query_interpretation } = request;

        // Generate mock results based on the query
        const mockResults = [];
        const resultCount = Math.min(limit || 100, 5); // Limit to 5 for testing
        const hasAdvancedParams = this.hasAdvancedParameters(request);

        for (let i = 0; i < resultCount; i++) {
            const score = 0.95 - (i * 0.1);

            // Apply score threshold if specified
            if (score_threshold !== undefined && score < score_threshold) {
                continue;
            }

            mockResults.push({
                score: score,
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
                        recency_bias: recency_bias,
                        score_threshold: score_threshold,
                        search_method: search_method,
                        expansion_strategy: expansion_strategy,
                        enable_reranking: enable_reranking,
                        enable_query_interpretation: enable_query_interpretation,
                        used_advanced_search: hasAdvancedParams
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
