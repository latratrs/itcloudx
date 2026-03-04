import { GlobalConfig } from 'payload';

export const Header: GlobalConfig = {
  slug: 'header',
  access: {
    read: () => true,
  },
  fields: [
    {
      name: 'menuItems',
      type: 'array',
      label: 'Main Navigation Menu',
      admin: {
        initCollapsed: true,
      },
      fields: [
        {
          name: 'label',
          type: 'text',
          required: true,
          label: 'Menu Label (e.g., Use Cases)',
        },
        {
          name: 'link',
          type: 'text',
          label: 'URL Slug (Leave blank if this is just a dropdown parent)',
        },
        {
          name: 'subItems',
          type: 'array',
          label: 'Dropdown Items',
          fields: [
            {
              name: 'label',
              type: 'text',
              required: true,
            },
            {
              name: 'link',
              type: 'text',
              required: true,
              label: 'URL Slug (e.g., /la-neighborhoods)',
            },
          ],
        },
      ],
    },
  ],
};