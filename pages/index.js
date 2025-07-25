import fs from "fs";
import path from "path";
import Link from "next/link";

export default function home({ data }) {
  return (
    <div>
      <h1>napari plugins</h1>
      <p><Link href={"https://github.com/napari/npe2api"}>source code for this site</Link></p>
      <h3>(This top page is for humans)</h3>
      <p>Plugin index: <Link href={`/api/plugins`}>/api/plugins</Link></p>
      <p>Summary info: <Link href={`/api/extended_summary`}>/api/extended_summary</Link></p>
      <p>PyPI information: see PyPI info for each plugin at /api/pypi/pypi_name</p>
      <p>Conda index: <Link href={`/api/conda`}>/api/conda</Link>  (see conda info for each plugin at /api/conda/pypi_name)</p>
      <p>Fetch errors: <Link href={`/errors.json`}>errors.json</Link></p>
      <h3>manifests</h3>
      <ul>
        {data.map((item) => (
          <li key={item.name}>
            <Link
              as={`/api/manifest/${item.name}`}
              href={`/api/manifest/[slug]`}
            >

              {item.name}-{item.version}

            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const getStaticProps = async () => {
  const source = fs.readFileSync(
    path.join(process.cwd(), "public", "extended_summary.json")
  );
  return {
    props: {
      data: JSON.parse(source),
    },
  };
};
