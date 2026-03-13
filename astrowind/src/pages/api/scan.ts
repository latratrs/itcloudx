/**
 * /api/scan — Server-side proxy for the Google Cloud Vision scan function.
 *
 * Accepts a multipart/form-data POST (file, email, company) and forwards it
 * to the Cloud Function defined by VISION_FUNCTION_URL.
 *
 * When VISION_FUNCTION_URL is not set the endpoint returns sample Vision API
 * data so the frontend can be developed and tested without a live backend.
 *
 * NOTE: This route requires SSR (output: 'server').  If the project is built
 * as fully static, the ScanWidget calls VISION_FUNCTION_URL directly from
 * the browser instead of going through this proxy.
 */

import type { APIRoute } from 'astro';

// Cloud Function URL deployed from functions/scan_handler.py
// Set in .env or Firebase environment:
//   VISION_FUNCTION_URL=https://<region>-<project>.cloudfunctions.net/scan_handler
const VISION_FUNCTION_URL = import.meta.env.VISION_FUNCTION_URL || '';

export const POST: APIRoute = async ({ request }) => {
  // ── Demo mode — no backend configured ──────────────────────────────
  if (!VISION_FUNCTION_URL) {
    const formData = await request.formData();
    const email    = (formData.get('email')   as string) || '';
    const company  = (formData.get('company') as string) || '';
    const file     = formData.get('file') as File | null;
    const filename = file?.name ?? 'sample-document.pdf';
    const jobId    = `VISION-DEMO-${Date.now()}`;

    console.log(`[TradeShield Vision] Demo mode — file: ${filename}, email: ${email}`);

    return new Response(
      JSON.stringify({
        status:     'success',
        job_id:     jobId,
        filename,
        email,
        company,
        page_count: 1,
        ocr_text: [
          'COMMERCIAL INVOICE',
          'Shipper: Acme Electronics Ltd.  Shanghai, China',
          'Consignee: Global Imports LLC  Los Angeles, CA 90001',
          '',
          'Item 1: Laptop Computer (15")   Qty: 50   Unit: $800   Total: $40,000',
          '        HS Code: 8471.30        Country of Origin: CN',
          'Item 2: USB-C Charging Cable    Qty: 500  Unit: $4     Total: $2,000',
          '        HS Code: 8544.42        Country of Origin: VN',
          '',
          'Barcode: 012345678901',
          'Invoice No: INV-2026-0042  Date: 2026-03-10  Total: $42,000 USD',
        ].join('\n'),
        labels: [
          { description: 'Document',    score: 0.99 },
          { description: 'Text',        score: 0.98 },
          { description: 'Invoice',     score: 0.95 },
          { description: 'Electronics', score: 0.87 },
          { description: 'Shipping',    score: 0.81 },
        ],
        objects: [
          { name: 'Document', score: 0.97 },
          { name: 'Paper',    score: 0.88 },
          { name: 'Text',     score: 0.85 },
        ],
        barcodes: [
          { type: 'UPC/EAN', value: '012345678901' },
        ],
        note: 'Demo mode — set VISION_FUNCTION_URL to enable live Vision API scanning.',
      }),
      {
        status:  200,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }

  // ── Production proxy — forward to Cloud Function ────────────────────
  try {
    const formData       = await request.formData();
    const visionResponse = await fetch(VISION_FUNCTION_URL, {
      method: 'POST',
      body:   formData,
    });
    const result = await visionResponse.json();
    return new Response(JSON.stringify(result), {
      status:  visionResponse.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('[TradeShield Vision] Proxy error:', message);
    return new Response(
      JSON.stringify({ status: 'error', error: 'Vision scan service temporarily unavailable.' }),
      {
        status:  503,
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }
};
