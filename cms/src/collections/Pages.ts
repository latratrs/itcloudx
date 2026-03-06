import { CollectionConfig } from 'payload';
export const Pages: CollectionConfig = {
  slug: 'pages',
  admin: {
    useAsTitle: 'pageName',
    defaultColumns: ['pageName', 'title', 'slug', 'updatedAt'],
  },
  access: {
    read: () => true,
    update: () => true,
    create: () => true,
    delete: () => true,
  },
  fields: [
    {
      name: 'pageName',
      type: 'text',
      required: true,
      label: 'Page Name (Internal / Menu Label)',
    },
    {
      name: 'title',
      type: 'text',
      required: true,
      label: 'Display Title (Public Header)',
    },
    {
      name: 'slug',
      type: 'text',
      required: true,
      unique: true,
      label: 'URL Slug',
      hooks: {
        beforeValidate: [
          ({ value, data }) => {
            if ((!value || value.length > 20) && data?.pageName) {
              return data.pageName
                .toLowerCase()
                .replace(/ /g, '-')
                .replace(/[^\w-]+/g, '');
            }
            return value;
          },
        ],
      },
    },
    {
      name: 'summary',
      type: 'textarea',
      label: 'SEO Summary (Meta Description)',
      admin: {
        description: 'Short description for Google search results. Keep under 160 characters.',
      },
    },
    {
      name: 'canvasCode',
      type: 'code',
      label: 'Sherlock Canvas Code (HTML/Tailwind)',
      admin: {
        language: 'html',
        editorOptions: {
          automaticLayout: true,
        },
      },
    },
    {
      name: 'content',
      type: 'richText',
      label: 'Standard Content (Lexical)',
    },
  ],
};
