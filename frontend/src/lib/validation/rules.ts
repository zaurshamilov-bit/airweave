/**
 * Validation rules for the collection creation flow
 */

import type { FieldValidation, ValidationResult } from './types';

/**
 * Collection name validation
 * Requirements: 4-64 characters
 */
export const collectionNameValidation: FieldValidation<string> = {
  field: 'collectionName',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    // Too short
    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? 's' : ''} needed`,
        severity: 'info'
      };
    }

    // Too long
    if (trimmed.length > 64) {
      return {
        isValid: false,
        hint: 'Maximum 64 characters',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Source connection name validation
 * Requirements: 4-42 characters
 */
export const sourceConnectionNameValidation: FieldValidation<string> = {
  field: 'sourceConnectionName',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    const trimmed = value.trim();

    if (!trimmed) {
      return { isValid: true, severity: 'info' };
    }

    if (trimmed.length < 4) {
      return {
        isValid: false,
        hint: `${4 - trimmed.length} more character${4 - trimmed.length > 1 ? 's' : ''} needed`,
        severity: 'info'
      };
    }

    if (trimmed.length > 42) {
      return {
        isValid: false,
        hint: 'Maximum 42 characters',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * API key validation
 */
export const apiKeyValidation: FieldValidation<string> = {
  field: 'api_key',
  debounceMs: 0,
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    // Check for placeholder values
    const placeholders = ['your-api-key', 'xxx', 'api-key-here', 'paste-here'];
    if (placeholders.some(p => value.toLowerCase().includes(p))) {
      return {
        isValid: false,
        hint: 'Enter your actual API key',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * URL validation
 */
export const urlValidation: FieldValidation<string> = {
  field: 'url',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    try {
      new URL(value);
      return { isValid: true, severity: 'info' };
    } catch {
      return {
        isValid: false,
        hint: 'Invalid URL format',
        severity: 'info'
      };
    }
  }
};

/**
 * Email validation
 */
export const emailValidation: FieldValidation<string> = {
  field: 'email',
  debounceMs: 500,
  showOn: 'change',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(value)) {
      return {
        isValid: false,
        hint: 'Invalid email format',
        severity: 'info'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * OAuth Client ID validation
 */
export const clientIdValidation: FieldValidation<string> = {
  field: 'clientId',
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    if (value.toLowerCase().includes('your-client-id')) {
      return {
        isValid: false,
        hint: 'Enter your actual Client ID',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * OAuth Client Secret validation
 */
export const clientSecretValidation: FieldValidation<string> = {
  field: 'clientSecret',
  showOn: 'blur',
  validate: (value: string): ValidationResult => {
    if (!value) return { isValid: true, severity: 'info' };

    if (value.toLowerCase().includes('your-secret')) {
      return {
        isValid: false,
        hint: 'Enter your actual Client Secret',
        severity: 'warning'
      };
    }

    return { isValid: true, severity: 'info' };
  }
};

/**
 * Get validation for a specific auth field type
 */
export function getAuthFieldValidation(fieldType: string): FieldValidation<string> | null {
  switch (fieldType) {
    case 'api_key':
    case 'token':
    case 'access_token':
    case 'personal_access_token':
      return apiKeyValidation;
    case 'url':
    case 'endpoint':
    case 'base_url':
    case 'cluster_url':
      // Note: 'host' is NOT included - database hosts don't need http:// prefix
      return urlValidation;
    case 'email':
    case 'username':
      return emailValidation;
    case 'client_id':
      return clientIdValidation;
    case 'client_secret':
      return clientSecretValidation;
    default:
      return null;
  }
}
