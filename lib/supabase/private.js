import { createClient } from '@supabase/supabase-js'

if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
    throw new Error('Missing env vars SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
}

const privateClient = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_KEY
)

export default async function logHit(req) {
    return privateClient.rpc('increment_views2', { page_slug: req.url, headers: JSON.stringify(req.headers) });
}

