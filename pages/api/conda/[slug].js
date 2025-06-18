import path from "path";
import { promises as fs } from "fs";

export default async function handler(req, res) {
  const { slug } = req.query;
  const jsonDirectory = path.join(process.cwd(), "public", "conda");
  const fileContents = await fs.readFile(
    jsonDirectory + `/${slug}.json`,
    "utf8"
  );
  res.status(200).send(JSON.stringify(JSON.parse(fileContents)));
}
