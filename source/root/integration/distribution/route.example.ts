// Next.js App Router: app/downloads/fildesk/releases/[version]/FilDesk-Destek-Windows.exe/route.ts
// Copy the reviewed server module and approved manifest into your integration.
// This example is not deployed and is deliberately unconfigured.
import { download } from './download.mjs';
import release from './release.example.json';
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
  const directory = process.env.FIL_RELEASE_DIRECTORY;
  if (!directory) return new Response('Release unavailable', { status: 503 });
  return download(request, { release, directory });
}
export const HEAD = GET;
