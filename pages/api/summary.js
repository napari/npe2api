import path from 'path';
import { promises as fs } from 'fs';
import { logHit } from '../../lib/supabase/private';

export default async function handler(req, res) {
  const jsonDirectory = path.join(process.cwd(), 'public');
  const fileContents = await fs.readFile(jsonDirectory + '/summary.json', 'utf8');
  logHit(req);
  res.status(200).json(JSON.parse(fileContents));
}
