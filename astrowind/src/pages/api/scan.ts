export const prerender = true;

import type { APIRoute } from 'astro';

const FIREBASE_FUNCTION_URL = import.meta.env.FIREBASE_FUNCTION_URL || '';

export const POST: APIRoute = async ({ request }) => {
  if (!FIREBASE_FUNCTION_URL) {
    const formData = await request.formData();
    const email = formData.get('email') || 'unknown';
    const demoJobId = `TS-DEMO-${Date.now()}`;
    console.log(`[TradeShield] Demo mode — email: ${email}`);
    return new Response(JSON.stringify({
      jobId: demoJobId,
      status: 'success',
      demo: true,
      overall_risk_score: 42,
      overall_recommendation: 'REVIEW',
      product_count: 3,
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const formData = await request.formData();
    const firebaseResponse = await fetch(FIREBASE_FUNCTION_URL, {
      method: 'POST',
      body: formData,
    });
    const result = await firebaseResponse.json();
    return new Response(JSON.stringify(result), {
      status: firebaseResponse.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    console.error('[TradeShield] Firebase proxy error:', error);
    return new Response(JSON.stringify({
      error: 'Upload service temporarily unavailable.',
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
