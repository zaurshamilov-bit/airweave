// Airweave API client for making requests

import { AirweaveConfig, SearchResponse } from './types.js';

export class AirweaveClient {
    constructor(private config: AirweaveConfig) { }

    async search(searchRequest: any): Promise<SearchResponse> {
        const { query, response_type, limit, offset, recency_bias } = searchRequest;

        // Mock mode for testing
        if (this.config.apiKey === 'test-key' && this.config.baseUrl.includes('localhost')) {
            return this.getMockResponse(searchRequest);
        }

        // Construct the search endpoint URL
        const endpoint = `/collections/${this.config.collection}/search`;
        const searchParams = new URLSearchParams({
            query,
            response_type,
            limit: limit.toString(),
            offset: offset.toString(),
        });

        // Add recency_bias only if provided
        if (recency_bias !== undefined) {
            searchParams.append('recency_bias', recency_bias.toString());
        }

        const url = `${this.config.baseUrl}${endpoint}?${searchParams.toString()}`;

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'x-api-key': this.config.apiKey,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Airweave API error (${response.status}): ${errorText}`);
        }

        const responseText = await response.text();
        let searchResponse: SearchResponse;

        try {
            searchResponse = JSON.parse(responseText);
        } catch (parseError) {
            console.error("Failed to parse JSON response:", responseText.substring(0, 500));
            throw new Error(`Invalid JSON response: ${responseText.substring(0, 200)}...`);
        }

        return searchResponse;
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
