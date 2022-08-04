import { createClient } from "@supabase/supabase-js";
import crypto from "crypto";

export let logHit = async (req) => {};

if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
  console.log(
    "Missing env SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. Skipping logging."
  );
} else {
  const privateClient = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_KEY
  );

  logHit = async (req) => {
    // create unique user id without any personally identifiable information
    const anon_id = crypto
      .createHmac("sha256", process.env.SUPABASE_SALT || "supabase")
      .update(req.headers["x-forwarded-for"] + " " + req.headers["user-agent"])
      .digest("hex");

    // TODO:
    // a napari user agent will look something like this
    // ('napari', napari.__version__)
    // ('runtime', {briefcase, constructor, jupyter, ipython, python})
    // (platform.python_implementation(), platform.python_version())
    // (platform.system(), platform.release())
    // "napari/0.4.16 runtime/ipython CPython/3.9.13 Darwin/21.5.0"

    const data = {
      slug: req.url,
      uid: anon_id,
      dhost: req.headers.host,
      city: req.headers["x-vercel-ip-city"] || "",
      region: req.headers["x-vercel-ip-country-region"] || "",
      country: req.headers["x-vercel-ip-country"] || "",
    };

    return privateClient.rpc("log_hit", data);
  };
}
