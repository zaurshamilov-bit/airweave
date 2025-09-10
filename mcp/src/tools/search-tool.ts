// Search tool implementation

import { z } from "zod";
import { AirweaveClient } from "../api/airweave-client.js";
import { formatSearchResponse, formatErrorResponse } from "../utils/error-handling.js";

export function createSearchTool(
    toolName: string,
    collection: string,
    airweaveClient: AirweaveClient
) {
    // Define the schema shape for MCP SDK (ZodRawShape format)
    const searchSchema = {
        query: z.string().min(1).max(1000).describe("The search query text to find relevant documents and data"),
        response_type: z.enum(["raw", "completion"]).optional().default("raw").describe("Format of the response: 'raw' returns search results, 'completion' returns AI-generated answers"),
        limit: z.number().min(1).max(1000).optional().default(100).describe("Maximum number of results to return"),
        offset: z.number().min(0).optional().default(0).describe("Number of results to skip for pagination"),
        recency_bias: z.number().min(0).max(1).optional().describe("How much to weigh recency vs similarity (0..1). 0 = no recency effect; 1 = rank by recency only")
    };

    // Create the full schema for validation
    const fullSchema = z.object(searchSchema);

    const parameterDescriptions = [
        "- `query`: The search query text to find relevant documents and data (required)",
        "- `response_type`: Format of the response: 'raw' returns search results, 'completion' returns AI-generated answers (optional, default: raw)",
        "- `limit`: Maximum number of results to return (optional, default: 100)",
        "- `offset`: Number of results to skip for pagination (optional, default: 0)",
        "- `recency_bias`: How much to weigh recency vs similarity (0..1). 0 = no recency effect; 1 = rank by recency only (optional)"
    ].join("\n");

    const naturalLanguageExamples = [
        "**Natural Language Examples:**",
        "- 'Find the first 5 results' → limit: 5",
        "- 'Show me results 11-20' → limit: 10, offset: 10",
        "- 'Give me a summary' → response_type: 'completion'",
        "- 'Find the most recent documents' → recency_bias: 0.8",
        "- 'Get the next 5 after the first 10' → limit: 5, offset: 10"
    ].join("\n");

    return {
        name: toolName,
        description: `Search within the Airweave collection '${collection}'\n\n**Parameters:**\n${parameterDescriptions}\n\n${naturalLanguageExamples}`,
        schema: searchSchema, // Use the shape, not the full ZodObject
        handler: async (params: any) => {
            try {
                // Zod will automatically validate and apply defaults
                const validatedParams = fullSchema.parse(params);
                const { response_type } = validatedParams;

                const searchResponse = await airweaveClient.search(validatedParams);
                return formatSearchResponse(searchResponse, response_type);
            } catch (error) {
                console.error("Error in search tool:", error);

                if (error instanceof z.ZodError) {
                    // Handle validation errors
                    const errorMessages = error.errors.map(e => `${e.path.join('.')}: ${e.message}`);
                    return {
                        content: [
                            {
                                type: "text" as const,
                                text: `**Parameter Validation Errors:**\n${errorMessages.join("\n")}`,
                            },
                        ],
                    };
                }

                return formatErrorResponse(error as Error, params);
            }
        }
    };
}
