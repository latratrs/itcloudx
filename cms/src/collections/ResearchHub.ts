import type { CollectionConfig } from 'payload'

export const ResearchHub: CollectionConfig = {
  slug: 'research-hub',
  access: {
    read: () => true,
  },
  admin: {
    useAsTitle: 'title',
    defaultColumns: ['title', 'slug', 'updatedAt'],
  },
  fields: [
    {
      name: 'title',
      type: 'text',
      required: true,
    },
    {
      name: 'slug',
      type: 'text',
      unique: true,
      index: true,
      admin: { position: 'sidebar' },
      hooks: {
        beforeValidate: [
          ({ value, data }) => {
            if (value) return value.toLowerCase().replace(/ /g, '-').replace(/[^\w-]+/g, '')
            if (data?.title) return data.title.toLowerCase().replace(/ /g, '-').replace(/[^\w-]+/g, '')
            return value
          },
        ],
      },
    },
    {
      name: 'summary',
      type: 'textarea',
      description: 'The 3-sentence AI summary from NotebookLM',
    },
    {
      name: 'videoUrl',
      type: 'text',
      description: 'Paste YouTube or Vimeo URL for the video overview.',
    },
    {
      name: 'tableData',
      type: 'array',
      fields: [
        {
          type: 'row',
          fields: [
            { name: 'col1', type: 'text', label: 'Column 1', admin: { width: '25%' } },
            { name: 'col2', type: 'text', label: 'Column 2', admin: { width: '25%' } },
            { name: 'col3', type: 'text', label: 'Column 3', admin: { width: '25%' } },
            { name: 'col4', type: 'text', label: 'Column 4', admin: { width: '25%' } },
          ],
        },
      ],
    },
    {
      name: 'quiz',
      type: 'array',
      admin: { description: 'Interactive Quiz based on the research content.' },
      fields: [
        {
          name: 'question',
          type: 'text',
          required: true,
        },
        {
          name: 'correctAnswer',
          type: 'textarea',
          required: true,
        },
      ],
    },
    {
      name: 'audioUrl',
      type: 'text',
      description: 'Link to the Audio Overview',
    },
    {
      name: 'mindMap',
      type: 'code',
      admin: { language: 'markdown' },
      description: 'Paste your Mermaid.js syntax here',
    },
    {
      name: 'flashcards',
      type: 'array',
      fields: [
        { name: 'question', type: 'text', required: true },
        { name: 'answer', type: 'textarea', required: true },
      ],
    },
  ],
}