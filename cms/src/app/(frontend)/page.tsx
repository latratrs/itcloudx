import { headers as getHeaders } from 'next/headers.js';
import Image from 'next/image';
import { getPayload } from 'payload';
import React from 'react';
import { fileURLToPath } from 'url';

import config from '@/payload.config';
import './styles.css';

export default async function HomePage() {
  console.log('[HomePage] DATABASE_URI from env:', process.env.DATABASE_URI);
  console.log('[HomePage] NODE_ENV:', process.env.NODE_ENV);

  const headers = await getHeaders();
  const payloadConfig = await config;

  let payload;
  let user = null;

  try {
    console.log('[HomePage] Attempting to initialize Payload...');
    payload = await getPayload({ config: payloadConfig });
    console.log('[HomePage] Payload initialized successfully');
    const authResult = await payload.auth({ headers });
    user = authResult.user;
    console.log('[HomePage] Auth user:', user ? user.email : 'none');
  } catch (err: any) {
    console.error('[HomePage] Payload initialization failed:', {
      message: err.message,
      stack: err.stack,
      cause: err.cause,
    });
    // Return error UI so preview doesn't hang forever
    return (
      <div style={{ padding: '2rem', color: 'red', fontFamily: 'sans-serif' }}>
        <h1>Error Loading Home Page</h1>
        <p>{err.message || 'Unknown error during Payload initialization'}</p>
        <p>Check the terminal logs for detailed stack trace.</p>
        <p>Most common cause: MongoDB connection failure. Verify DATABASE_URI in .env.</p>
      </div>
    );
  }

  const fileURL = `vscode://file/${fileURLToPath(import.meta.url)}`;

  return (
    <div className="home">
      <div className="content">
        <picture>
          <source srcSet="https://raw.githubusercontent.com/payloadcms/payload/main/packages/ui/src/assets/payload-favicon.svg" />
          <Image
            alt="Payload Logo"
            height={65}
            src="https://raw.githubusercontent.com/payloadcms/payload/main/packages/ui/src/assets/payload-favicon.svg"
            width={65}
          />
        </picture>
        {!user && <h1>Welcome to your new project.</h1>}
        {user && <h1>Welcome back, {user.email}</h1>}
        <div className="links">
          <a
            className="admin"
            href={payloadConfig.routes.admin}
            rel="noopener noreferrer"
            target="_blank"
          >
            Go to admin panel
          </a>
          <a
            className="docs"
            href="https://payloadcms.com/docs"
            rel="noopener noreferrer"
            target="_blank"
          >
            Documentation
          </a>
        </div>
      </div>
      <div className="footer">
        <p>Update this page by editing</p>
        <a className="codeLink" href={fileURL}>
          <code>app/(frontend)/page.tsx</code>
        </a>
      </div>
    </div>
  );
}