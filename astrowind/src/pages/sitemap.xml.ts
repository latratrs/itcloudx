import type { APIRoute } from 'astro';

export const GET: APIRoute = async () => {
  // Fetch CMS pages
  let cmsPages: string[] = [];
  try {
    const response = await fetch('http://127.0.0.1:3000/api/pages?limit=1000');
    const data = await response.json();
    cmsPages = data.docs?.map((page: any) => `https://itcloudx.com/${page.slug}`) || [];
  } catch (e) {}

  // Static pages
  const staticPages = [
    'https://itcloudx.com/',
    'https://itcloudx.com/about',
    'https://itcloudx.com/services',
    'https://itcloudx.com/contact',
    'https://itcloudx.com/blog',
    'https://itcloudx.com/pricing',
  ];

  const allPages = [...staticPages, ...cmsPages];

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${allPages.map(url => `  <url>
    <loc>${url}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`).join('\n')}
</urlset>`;

  return new Response(sitemap, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
