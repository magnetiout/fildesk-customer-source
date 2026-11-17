import { download } from '@/lib/fildesk-download-handler.mjs';
import release from '@/config/fildesk-public-download.json';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) {
    const directory = process.env.FIL_CUSTOMER_RELEASE_DIRECTORY;
    if (!directory) return new Response('Release unavailable', {status: 503, headers: {'Cache-Control': 'no-store'}});
    return download(request, {release, directory});
}
export const HEAD = GET;
