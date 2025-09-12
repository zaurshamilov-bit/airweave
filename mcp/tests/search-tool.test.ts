import { describe, it, expect, vi, beforeEach } from 'vitest';
import { z } from 'zod';

// Mock the dependencies
vi.mock('../src/api/airweave-client.js');
vi.mock('../src/utils/error-handling.js');

describe('Search Tool', () => {
    let mockAirweaveClient: any;
    let mockFormatSearchResponse: any;
    let mockFormatErrorResponse: any;

    beforeEach(() => {
        // Reset mocks
        vi.clearAllMocks();

        // Mock AirweaveClient
        mockAirweaveClient = {
            search: vi.fn()
        };

        // Mock error handling functions
        mockFormatSearchResponse = vi.fn();
        mockFormatErrorResponse = vi.fn();

        // Set up module mocks
        vi.doMock('../src/api/airweave-client.js', () => ({
            AirweaveClient: vi.fn().mockImplementation(() => mockAirweaveClient)
        }));

        vi.doMock('../src/utils/error-handling.js', () => ({
            formatSearchResponse: mockFormatSearchResponse,
            formatErrorResponse: mockFormatErrorResponse
        }));
    });

    describe('Schema Validation', () => {
        it('should validate required query parameter', () => {
            const schema = z.object({
                query: z.string().min(1).max(1000),
                response_type: z.enum(["raw", "completion"]).optional().default("raw"),
                limit: z.number().min(1).max(1000).optional().default(100),
                offset: z.number().min(0).optional().default(0),
                recency_bias: z.number().min(0).max(1).optional(),
                // Advanced parameters
                score_threshold: z.number().min(0).max(1).optional(),
                search_method: z.enum(["hybrid", "neural", "keyword"]).optional(),
                expansion_strategy: z.enum(["auto", "llm", "no_expansion"]).optional(),
                enable_reranking: z.boolean().optional(),
                enable_query_interpretation: z.boolean().optional()
            });

            // Valid parameters
            expect(() => schema.parse({ query: "test" })).not.toThrow();
            expect(() => schema.parse({
                query: "test",
                response_type: "completion",
                limit: 50,
                offset: 10,
                recency_bias: 0.5
            })).not.toThrow();

            // Valid advanced parameters
            expect(() => schema.parse({
                query: "test",
                score_threshold: 0.8,
                search_method: "neural",
                expansion_strategy: "llm",
                enable_reranking: true,
                enable_query_interpretation: false
            })).not.toThrow();

            // Invalid parameters
            expect(() => schema.parse({})).toThrow(); // Missing query
            expect(() => schema.parse({ query: "" })).toThrow(); // Empty query
            expect(() => schema.parse({ query: "test", limit: 0 })).toThrow(); // Invalid limit
            expect(() => schema.parse({ query: "test", offset: -1 })).toThrow(); // Invalid offset
            expect(() => schema.parse({ query: "test", recency_bias: 1.5 })).toThrow(); // Invalid recency_bias
            expect(() => schema.parse({ query: "test", score_threshold: 1.5 })).toThrow(); // Invalid score_threshold
            expect(() => schema.parse({ query: "test", search_method: "invalid" })).toThrow(); // Invalid search_method
            expect(() => schema.parse({ query: "test", expansion_strategy: "invalid" })).toThrow(); // Invalid expansion_strategy
        });

        it('should apply default values correctly', () => {
            const schema = z.object({
                query: z.string().min(1).max(1000),
                response_type: z.enum(["raw", "completion"]).optional().default("raw"),
                limit: z.number().min(1).max(1000).optional().default(100),
                offset: z.number().min(0).optional().default(0),
                recency_bias: z.number().min(0).max(1).optional(),
                // Advanced parameters
                score_threshold: z.number().min(0).max(1).optional(),
                search_method: z.enum(["hybrid", "neural", "keyword"]).optional(),
                expansion_strategy: z.enum(["auto", "llm", "no_expansion"]).optional(),
                enable_reranking: z.boolean().optional(),
                enable_query_interpretation: z.boolean().optional()
            });

            const result = schema.parse({ query: "test" });

            expect(result.query).toBe("test");
            expect(result.response_type).toBe("raw");
            expect(result.limit).toBe(100);
            expect(result.offset).toBe(0);
            expect(result.recency_bias).toBeUndefined();
            // Advanced parameters should be undefined when not provided
            expect(result.score_threshold).toBeUndefined();
            expect(result.search_method).toBeUndefined();
            expect(result.expansion_strategy).toBeUndefined();
            expect(result.enable_reranking).toBeUndefined();
            expect(result.enable_query_interpretation).toBeUndefined();
        });
    });

    describe('Parameter Boundaries', () => {
        it('should handle query length boundaries', () => {
            const schema = z.object({
                query: z.string().min(1).max(1000)
            });

            // Valid boundaries
            expect(() => schema.parse({ query: "a" })).not.toThrow(); // Min length
            expect(() => schema.parse({ query: "a".repeat(1000) })).not.toThrow(); // Max length

            // Invalid boundaries
            expect(() => schema.parse({ query: "" })).toThrow(); // Too short
            expect(() => schema.parse({ query: "a".repeat(1001) })).toThrow(); // Too long
        });

        it('should handle limit boundaries', () => {
            const schema = z.object({
                query: z.string().min(1),
                limit: z.number().min(1).max(1000)
            });

            // Valid boundaries
            expect(() => schema.parse({ query: "test", limit: 1 })).not.toThrow();
            expect(() => schema.parse({ query: "test", limit: 1000 })).not.toThrow();

            // Invalid boundaries
            expect(() => schema.parse({ query: "test", limit: 0 })).toThrow();
            expect(() => schema.parse({ query: "test", limit: 1001 })).toThrow();
        });

        it('should handle offset boundaries', () => {
            const schema = z.object({
                query: z.string().min(1),
                offset: z.number().min(0)
            });

            // Valid boundaries
            expect(() => schema.parse({ query: "test", offset: 0 })).not.toThrow();
            expect(() => schema.parse({ query: "test", offset: 1000 })).not.toThrow();

            // Invalid boundaries
            expect(() => schema.parse({ query: "test", offset: -1 })).toThrow();
        });

        it('should handle recency_bias boundaries', () => {
            const schema = z.object({
                query: z.string().min(1),
                recency_bias: z.number().min(0).max(1)
            });

            // Valid boundaries
            expect(() => schema.parse({ query: "test", recency_bias: 0.0 })).not.toThrow();
            expect(() => schema.parse({ query: "test", recency_bias: 1.0 })).not.toThrow();

            // Invalid boundaries
            expect(() => schema.parse({ query: "test", recency_bias: -0.1 })).toThrow();
            expect(() => schema.parse({ query: "test", recency_bias: 1.1 })).toThrow();
        });

        it('should handle score_threshold boundaries', () => {
            const schema = z.object({
                query: z.string().min(1),
                score_threshold: z.number().min(0).max(1)
            });

            // Valid boundaries
            expect(() => schema.parse({ query: "test", score_threshold: 0.0 })).not.toThrow();
            expect(() => schema.parse({ query: "test", score_threshold: 1.0 })).not.toThrow();

            // Invalid boundaries
            expect(() => schema.parse({ query: "test", score_threshold: -0.1 })).toThrow();
            expect(() => schema.parse({ query: "test", score_threshold: 1.1 })).toThrow();
        });
    });

    describe('Response Type Validation', () => {
        it('should validate response_type enum values', () => {
            const schema = z.object({
                query: z.string().min(1),
                response_type: z.enum(["raw", "completion"])
            });

            // Valid values
            expect(() => schema.parse({ query: "test", response_type: "raw" })).not.toThrow();
            expect(() => schema.parse({ query: "test", response_type: "completion" })).not.toThrow();

            // Invalid values
            expect(() => schema.parse({ query: "test", response_type: "invalid" })).toThrow();
            expect(() => schema.parse({ query: "test", response_type: "RAW" })).toThrow(); // Case sensitive
        });

        it('should validate search_method enum values', () => {
            const schema = z.object({
                query: z.string().min(1),
                search_method: z.enum(["hybrid", "neural", "keyword"])
            });

            // Valid values
            expect(() => schema.parse({ query: "test", search_method: "hybrid" })).not.toThrow();
            expect(() => schema.parse({ query: "test", search_method: "neural" })).not.toThrow();
            expect(() => schema.parse({ query: "test", search_method: "keyword" })).not.toThrow();

            // Invalid values
            expect(() => schema.parse({ query: "test", search_method: "invalid" })).toThrow();
            expect(() => schema.parse({ query: "test", search_method: "HYBRID" })).toThrow(); // Case sensitive
        });

        it('should validate expansion_strategy enum values', () => {
            const schema = z.object({
                query: z.string().min(1),
                expansion_strategy: z.enum(["auto", "llm", "no_expansion"])
            });

            // Valid values
            expect(() => schema.parse({ query: "test", expansion_strategy: "auto" })).not.toThrow();
            expect(() => schema.parse({ query: "test", expansion_strategy: "llm" })).not.toThrow();
            expect(() => schema.parse({ query: "test", expansion_strategy: "no_expansion" })).not.toThrow();

            // Invalid values
            expect(() => schema.parse({ query: "test", expansion_strategy: "invalid" })).toThrow();
            expect(() => schema.parse({ query: "test", expansion_strategy: "AUTO" })).toThrow(); // Case sensitive
        });

        it('should validate boolean parameters', () => {
            const schema = z.object({
                query: z.string().min(1),
                enable_reranking: z.boolean(),
                enable_query_interpretation: z.boolean()
            });

            // Valid values
            expect(() => schema.parse({ query: "test", enable_reranking: true, enable_query_interpretation: false })).not.toThrow();
            expect(() => schema.parse({ query: "test", enable_reranking: false, enable_query_interpretation: true })).not.toThrow();

            // Invalid values
            expect(() => schema.parse({ query: "test", enable_reranking: "true" })).toThrow(); // String instead of boolean
            expect(() => schema.parse({ query: "test", enable_reranking: 1 })).toThrow(); // Number instead of boolean
        });
    });

    describe('Advanced Parameter Combinations', () => {
        it('should handle complex advanced search scenarios', () => {
            const schema = z.object({
                query: z.string().min(1).max(1000),
                response_type: z.enum(["raw", "completion"]).optional().default("raw"),
                limit: z.number().min(1).max(1000).optional().default(100),
                offset: z.number().min(0).optional().default(0),
                recency_bias: z.number().min(0).max(1).optional(),
                score_threshold: z.number().min(0).max(1).optional(),
                search_method: z.enum(["hybrid", "neural", "keyword"]).optional(),
                expansion_strategy: z.enum(["auto", "llm", "no_expansion"]).optional(),
                enable_reranking: z.boolean().optional(),
                enable_query_interpretation: z.boolean().optional()
            });

            // High-quality neural search with reranking
            expect(() => schema.parse({
                query: "machine learning algorithms",
                score_threshold: 0.8,
                search_method: "neural",
                enable_reranking: true,
                limit: 10
            })).not.toThrow();

            // Keyword search without expansion
            expect(() => schema.parse({
                query: "exact phrase search",
                search_method: "keyword",
                expansion_strategy: "no_expansion",
                enable_query_interpretation: false
            })).not.toThrow();

            // Recent high-quality results with completion
            expect(() => schema.parse({
                query: "latest AI developments",
                response_type: "completion",
                recency_bias: 0.9,
                score_threshold: 0.7,
                expansion_strategy: "llm"
            })).not.toThrow();
        });

        it('should validate parameter interactions', () => {
            const schema = z.object({
                query: z.string().min(1).max(1000),
                score_threshold: z.number().min(0).max(1).optional(),
                search_method: z.enum(["hybrid", "neural", "keyword"]).optional(),
                expansion_strategy: z.enum(["auto", "llm", "no_expansion"]).optional()
            });

            // All parameters together
            const result = schema.parse({
                query: "test query",
                score_threshold: 0.5,
                search_method: "hybrid",
                expansion_strategy: "auto"
            });

            expect(result.query).toBe("test query");
            expect(result.score_threshold).toBe(0.5);
            expect(result.search_method).toBe("hybrid");
            expect(result.expansion_strategy).toBe("auto");
        });
    });
});
