import { createClient } from "@supabase/supabase-js";
import crypto from "crypto";

if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
  throw new Error("Missing env vars SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
}

const privateClient = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

export default async function logHit(req) {
  const obfuscated_uid = crypto
    .createHmac("sha256", process.env.SUPABASE_SALT || "supabase")
    .update(req.headers["x-forwarded-for"] + " " + req.headers["user-agent"])
    .digest("hex");
    
  const data = {
    slug: req.url,
    uid: obfuscated_uid,
    dhost: req.headers.host,
    city: req.headers["x-vercel-ip-city"] || "",
    region: req.headers["x-vercel-ip-country-region"] || "",
    country: req.headers["x-vercel-ip-country"] || "",
  };

  return privateClient.rpc("log_hit", data);
}
