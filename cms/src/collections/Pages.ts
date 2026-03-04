import { CollectionConfig } from 'payload';

export const Pages: CollectionConfig = {
  slug: 'pages',
  admin: {
    // Uses the internal page name for the list view title
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
      // Removed sidebar positioning to keep it in the main flow above the code editor
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
      name: 'canvasCode',
      type: 'code',
      label: 'Sherlock Canvas Code (HTML/Tailwind)',
      admin: {
        language: 'html',
        // Sets a larger initial height for the code editor window
        editorOptions: {
          // Monaco editor options
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