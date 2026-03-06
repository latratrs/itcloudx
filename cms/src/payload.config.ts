import { buildConfig } from 'payload';
import path from 'path';
import { fileURLToPath } from 'url';
import { mongooseAdapter } from '@payloadcms/db-mongodb';
import { lexicalEditor } from '@payloadcms/richtext-lexical';

// Your collections and globals
import { Pages } from './collections/Pages';
import { Users } from './collections/Users';
import { Header } from './globals/Header';

const filename = fileURLToPath(import.meta.url);
const dirname = path.dirname(filename);

export default buildConfig({
  admin: {
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

  secret: process.env.PAYLOAD_SECRET || 'SHERLOCK_SECRET_2026',

  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },

  db: mongooseAdapter({
    // Primary: Firebase Studio built-in local MongoDB (Unix socket)
    url: process.env.DATABASE_URI || 'mongodb://%2Ftmp%2Fmongodb%2Fmongodb.sock/itcloudx?directConnection=true&serverSelectionTimeoutMS=15000&connectTimeoutMS=15000',

    // Alternative fallback: your Atlas cluster (uncomment if you prefer cloud)
    // url: process.env.DATABASE_URI || 'mongodb+srv://yuriy_admin:6OfppGyrwBFDE56R@cluster0.r7l4onf.mongodb.net/itcloudx?retryWrites=true&w=majority',
  }),
});