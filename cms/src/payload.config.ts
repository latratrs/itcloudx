import { buildConfig } from 'payload';
import path from 'path';
import { fileURLToPath } from 'url';
import { mongooseAdapter } from '@payloadcms/db-mongodb'; 
import { lexicalEditor } from '@payloadcms/richtext-lexical';

// --- SHERLOCK IMPORTS ---
import { Pages } from './collections/Pages';
import { Users } from './collections/Users';
import { Header } from './globals/Header';

const filename = fileURLToPath(import.meta.url);
const dirname = path.dirname(filename);

export default buildConfig({
  admin: {
    // Points to the 'users' slug in your Users.ts
    user: Users.slug, 
    autoLogin: process.env.NODE_ENV === 'development' ? {
      email: 'dev@itcloudx.com',
      password: 'test',
      prefillOnly: true,
    } : false,
  },
  collections: [
    Pages,
    Users,
  ],
  globals: [
    Header,
  ],
  editor: lexicalEditor({}),
  // Bedrock of Truth: Verified secret from your verified .env
  secret: process.env.PAYLOAD_SECRET || 'SHERLOCK_SECRET_2026',
  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },
  db: mongooseAdapter({
    // Direct link to your verified Atlas Cluster0 URI
    url: process.env.DATABASE_URI || '',
  }),
});