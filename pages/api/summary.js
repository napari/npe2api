import path from 'path';
import { promises as fs } from 'fs';
import supabase from '../../lib/supabase/private';

export default async function handler(req, res) {
  await supabase.rpc('increment_views', { page_slug: req.url });
  const jsonDirectory = path.join(process.cwd(), 'public');
  const fileContents = await fs.readFile(jsonDirectory + '/summary.json', 'utf8');
  res.status(200).send(JSON.stringify(JSON.parse(fileContents)));  // remove whitespace
}
