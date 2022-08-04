import path from 'path';
import { promises as fs } from 'fs';
import logHit from '../../lib/supabase/private';

export default async function handler(req, res) {
  const jsonDirectory = path.join(process.cwd(), 'public');
  const fileContents = await fs.readFile(jsonDirectory + '/index.json', 'utf8');
  logHit(req);
  res.status(200).send(JSON.stringify(JSON.parse(fileContents)));  // remove whitespace
}
