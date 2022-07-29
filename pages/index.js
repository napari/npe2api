import fs from "fs";
import path from "path";
import Link from "next/link";

export default function home({ data }) {
  return (
    <ul>
      {data.map((item) => (
        <li key={item.name}>
          <Link as={`/api/manifest/${item.name}`} href={`/api/manifest/[slug]`}>
            <a>
              {item.name}-{item.version}
            </a>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export const getStaticProps = async () => {
  const source = fs.readFileSync(
    path.join(process.cwd(), "public", "index.json")
  );
  return {
    props: {
      data: JSON.parse(source),
    },
  };
};
