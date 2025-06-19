# Organization Components

This folder contains all components related to organization management and functionality.

## Folder Structure

```
/components/organization/
├── modals/          # Modal dialogs for organization actions
├── forms/           # Reusable form components
├── cards/           # Card-based display components
├── tables/          # Table components for data display
└── index.ts         # Main export file
```

## Available Components

### Modals (`/modals/`)
- ✅ `CreateOrganizationModal` - Create new organizations
- ✅ `DeleteOrganizationModal` - Confirm organization deletion
- ✅ `InviteMemberModal` - Invite new members to organizations

### Future Components
- `EditOrganizationModal` - Edit organization details
- `LeaveOrganizationModal` - Confirm leaving an organization
- `TransferOwnershipModal` - Transfer ownership to another member
- `RemoveMemberModal` - Remove members from organization
- `ChangeRoleModal` - Change member roles

## Usage

Import components from the main organization index:

```tsx
import {
  CreateOrganizationModal,
  DeleteOrganizationModal,
  InviteMemberModal
} from '@/components/organization';
```

## Guidelines

1. **Modal Components** - Use for actions that require user confirmation or input
2. **Form Components** - Create reusable forms that can be used in modals or pages
3. **Card Components** - Use for displaying organization information in card format
4. **Table Components** - Use for displaying lists of organization data

## Integration

All organization components should:
- Use the `useOrganizationContext` hook for organization data
- Follow consistent naming conventions
- Include proper TypeScript interfaces
- Handle loading and error states
- Be accessible and responsive
