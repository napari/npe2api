import fs from "fs";
import path from "path";
import Link from "next/link";

export default function home({ data }) {
  return (
    <div>
      <h1>napari plugins</h1>
      <p><Link href={"https://github.com/napari/npe2api"}><a>source code for this site</a></Link></p>
      <h3>(This top page is for humans)</h3>
      <p>Plugin index: <Link href={`/api/plugins`}><a>/api/plugins</a></Link></p>
      <p>Summary info: <Link href={`/api/summary`}><a>/api/summary</a></Link></p>
      <p>Conda index: <Link href={`/api/conda`}><a>/api/conda</a></Link>  (see conda info for each plugin at /api/conda/pypi_name)</p>
      <p>Fetch errors: <Link href={`/errors.json`}><a>errors.json</a></Link></p>
      <h3>manifests</h3>
      <ul>
        {data.map((item) => (
          <li key={item.name}>
            <Link
              as={`/api/manifest/${item.name}`}
              href={`/api/manifest/[slug]`}
            >
              <a>
                {item.name}-{item.version}
              </a>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const getStaticProps = async () => {
  const source = fs.readFileSync(
    path.join(process.cwd(), "public", "summary.json")
  );
  return {
    props: {
      data: JSON.parse(source),
    },
  };
};
