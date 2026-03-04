import type { CollectionConfig } from 'payload'

export const GlobalSettings: CollectionConfig = {
  slug: 'global-settings',
  admin: {
    useAsTitle: 'siteName',
    // Logic: Restrict this to a single entry so it acts as a Global config
    pagination: false,
  },
  access: {
    read: () => true,
  },
  fields: [
    {
      name: 'siteName',
      type: 'text',
      defaultValue: 'itcloudx',
      required: true,
    },
    {
      name: 'contactEmail',
      type: 'text',
      defaultValue: 'latraveltours@gmail.com', // Your primary business email
    },
    {
      name: 'contactPhone',
      type: 'text',
      description: 'Format: 555-555-5555', // Enforcing your dash preference
    },
    {
      name: 'footerText',
      type: 'textarea',
      defaultValue: 'Powered by the Baker Street Mesh.',
    },
  ],
}