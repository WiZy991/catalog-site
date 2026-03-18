import re
from pathlib import Path


def main() -> None:
    xml_path = Path(r"C:\Users\Антон\Desktop\web\import0_1.xml")
    ids: list[str] = []

    # Stream-read: the file is huge.
    with xml_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "<Ид>" not in line:
                continue
            m = re.search(r"<Ид>([^<]+)</Ид>", line)
            if not m:
                continue
            ids.append(m.group(1).strip())

    full_unique = set(ids)
    base_unique = {i.split("#", 1)[0] for i in ids}
    nohash_long = [i for i in ids if "#" not in i and len(i) > 36]

    print("Id total:", len(ids))
    print("unique full:", len(full_unique))
    print("unique base:", len(base_unique))
    print("nohash_long:", len(nohash_long))
    print("sample nohash_long:", nohash_long[:10])


if __name__ == "__main__":
    main()

