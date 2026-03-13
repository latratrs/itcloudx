export const prerender = true;
import type { APIRoute } from 'astro';
const FIREBASE_PROJECT_ID = 'itcloudx-com';
export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const jobId = url.searchParams.get('jobId');
  if (!jobId) return new Response(JSON.stringify({ error: 'Missing jobId' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  try {
    const firestoreUrl = `https://firestore.googleapis.com/v1/projects/${FIREBASE_PROJECT_ID}/databases/(default)/documents/compliance_audits/${encodeURIComponent(jobId)}`;
    const res = await fetch(firestoreUrl);
    if (!res.ok) return new Response(JSON.stringify({ error: 'Report not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });
    const doc = await res.json();
    const fields = doc.fields || {};
    function parseVal(v) { if (v.stringValue!==undefined) return v.stringValue; if (v.integerValue!==undefined) return parseInt(v.integerValue); if (v.doubleValue!==undefined) return v.doubleValue; if (v.booleanValue!==undefined) return v.booleanValue; if (v.mapValue!==undefined) return parseDoc(v.mapValue.fields||{}); if (v.arrayValue!==undefined) return (v.arrayValue.values||[]).map(parseVal); return null; }
    function parseDoc(f) { const r={}; for (const [k,v] of Object.entries(f)) r[k]=parseVal(v); return r; }
    return new Response(JSON.stringify(parseDoc(fields)), { status: 200, headers: { 'Content-Type': 'application/json' } });
  } catch(e) { return new Response(JSON.stringify({ error: 'Failed' }), { status: 500, headers: { 'Content-Type': 'application/json' } }); }
};
