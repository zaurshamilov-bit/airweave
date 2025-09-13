import React, { useEffect, useState } from 'react';
import { useAuthProvidersStore } from '@/lib/stores/authProviders';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { Check } from 'lucide-react';
import { getAuthProviderIconUrl } from '@/lib/utils/icons';
import { ValidatedInput } from '@/components/ui/validated-input';
import { authConfigIdValidation, accountIdValidation, workflowIdValidation } from '@/lib/validation/rules';

interface AuthProviderSelectorProps {
  selectedProvider?: string;
  onProviderSelect: (providerId: string) => void;
  onConfigChange: (config: Record<string, any>) => void;
}

export const AuthProviderSelector: React.FC<AuthProviderSelectorProps> = ({
  selectedProvider,
  onProviderSelect,
  onConfigChange,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const {
    authProviderConnections,
    isLoadingConnections,
    fetchAuthProviderConnections,
  } = useAuthProvidersStore();

  const [providerConfig, setProviderConfig] = useState<Record<string, any>>({});

  useEffect(() => {
    fetchAuthProviderConnections();
  }, [fetchAuthProviderConnections]);

  // Reset config when provider changes
  useEffect(() => {
    setProviderConfig({});
    onConfigChange({});
  }, [selectedProvider]);

  const handleConfigFieldChange = (fieldName: string, value: string) => {
    const newConfig = { ...providerConfig, [fieldName]: value };
    setProviderConfig(newConfig);
    onConfigChange(newConfig);
  };

  // Provider-specific config fields
  const getProviderConfigFields = (providerShortName: string) => {
    switch (providerShortName) {
      case 'composio':
        return [
          { name: 'auth_config_id', label: 'Auth Config ID', placeholder: 'config_xyz789', required: true, validation: authConfigIdValidation },
          { name: 'account_id', label: 'Account ID', placeholder: 'account_abc123', required: true, validation: accountIdValidation },
        ];
      case 'pipedream':
        return [
          { name: 'workflow_id', label: 'Workflow ID', placeholder: 'p_abc123', required: true, validation: workflowIdValidation },
          { name: 'account_id', label: 'Account ID', placeholder: 'account_123', required: true, validation: accountIdValidation },
        ];
      default:
        return [];
    }
  };

  if (isLoadingConnections) {
    return (
      <div className="flex justify-center py-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 dark:border-gray-100" />
      </div>
    );
  }

  if (authProviderConnections.length === 0) {
    return (
      <div className={cn(
        "p-3 rounded-lg border text-center",
        isDark ? "border-gray-800 bg-gray-900/30" : "border-gray-200 bg-gray-50"
      )}>
        <p className={cn(
          "text-xs",
          isDark ? "text-gray-500" : "text-gray-500"
        )}>
          No auth providers connected.
          <a
            href="/organization/settings"
            target="_blank"
            className={cn(
              "ml-1 hover:underline",
              isDark ? "text-blue-400" : "text-blue-600"
            )}
          >
            Connect one →
          </a>
        </p>
      </div>
    );
  }

  const selectedProviderConnection = authProviderConnections.find(
    p => p.readable_id === selectedProvider
  );

  return (
    <div className="space-y-3">
      {/* Provider Selection */}
      <div className="space-y-2">
        <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Select Provider
        </label>
        <div className="space-y-2">
          {authProviderConnections.map((provider) => (
            <button
              key={provider.readable_id}
              onClick={() => onProviderSelect(provider.readable_id)}
              className={cn(
                "w-full flex items-center gap-3 p-2.5 rounded-lg border transition-all text-left",
                selectedProvider === provider.readable_id
                  ? isDark
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-blue-500/50 bg-blue-50/50"
                  : isDark
                    ? "border-gray-800 hover:border-gray-700 bg-gray-900/30"
                    : "border-gray-200 hover:border-gray-300 bg-white"
              )}
            >
              <div className={cn(
                "w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0",
                selectedProvider === provider.readable_id
                  ? "border-blue-500 bg-blue-500"
                  : isDark
                    ? "border-gray-600"
                    : "border-gray-400"
              )}>
                {selectedProvider === provider.readable_id && (
                  <Check className="h-3 w-3 text-white" />
                )}
              </div>
              <img
                src={getAuthProviderIconUrl(provider.short_name, resolvedTheme)}
                alt={provider.short_name}
                className="w-5 h-5 object-contain flex-shrink-0"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
              <div className={cn(
                "text-sm flex-1 min-w-0",
                isDark ? "text-gray-200" : "text-gray-700"
              )}>
                {provider.readable_id}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Provider Configuration */}
      {selectedProviderConnection && (
        <div className="space-y-2.5">
        <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Provider Configuration
        </label>

          {getProviderConfigFields(selectedProviderConnection.short_name).map((field) => (
            <div key={field.name}>
              <label className={cn(
                "block text-sm mb-1",
                isDark ? "text-gray-300" : "text-gray-600"
              )}>
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              <ValidatedInput
                type="text"
                placeholder={field.placeholder}
                value={providerConfig[field.name] || ''}
                onChange={(value) => handleConfigFieldChange(field.name, value)}
                validation={field.validation}
                className={cn(
                  "focus:border-gray-400 dark:focus:border-gray-600",
                  isDark
                    ? "bg-gray-800 border-gray-700 text-white placeholder:text-gray-500"
                    : "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
                )}
              />
            </div>
          ))}

          <p className={cn(
            "text-xs mt-1",
            isDark ? "text-gray-500" : "text-gray-500"
          )}>
            Find these values in your {selectedProviderConnection.short_name.charAt(0).toUpperCase() + selectedProviderConnection.short_name.slice(1)} dashboard
          </p>
        </div>
      )}
    </div>
  );
};
