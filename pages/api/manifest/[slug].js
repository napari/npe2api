import path from "path";
import { promises as fs } from "fs";

export default async function handler(req, res) {
  const { slug } = req.query;
  const normalizedSlug = normalizeName(slug);
  const jsonDirectory = path.join(process.cwd(), "public", "manifest");
  const fileContents = await fs.readFile(
    jsonDirectory + `/${normalizedSlug}.json`,
    "utf8"
  );
  res.status(200).send(JSON.stringify(JSON.parse(fileContents)));
}

function normalizeName(name) {
  return name.replace(/[-_.]+/g, "-").toLowerCase();
}