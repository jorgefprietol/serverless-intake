"""Regenerate the repository's portable SVG diagrams from Markdown sources."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", required=True, type=Path,
                        help="Installed Chrome or Chromium executable")
    parser.add_argument("--cli", type=Path,
                        default=ROOT/"tools/diagrams/node_modules/@mermaid-js/mermaid-cli/src/cli.js")
    args = parser.parse_args()
    node = shutil.which("node")
    if not node or not args.cli.is_file() or not args.browser.is_file():
        parser.error("Install Node.js and Mermaid CLI, then provide an existing --browser executable")
    folder = ROOT/"docs/diagrams"
    theme = folder/"theme.json"
    settings = json.loads(theme.read_text(encoding="utf-8"))
    if settings.get("htmlLabels") is not False or settings.get("flowchart", {}).get("htmlLabels") is not False:
        parser.error("theme.json must disable htmlLabels for portable SVG labels")
    for kind in ("architecture", "flow"):
        markdown = (ROOT/"docs"/(kind+".md")).read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\s*\n(.*?)```", markdown, re.S)
        if len(blocks) != 1:
            raise ValueError(kind+".md must contain exactly one Mermaid block")
        source = blocks[0].strip()+"\n"
        with tempfile.TemporaryDirectory(prefix="render-", dir=folder) as temporary:
            work = Path(temporary)
            mmd, svg, browser = work/(kind+".mmd"), work/(kind+".svg"), work/"browser.json"
            mmd.write_text(source, encoding="utf-8")
            browser.write_text(json.dumps({"executablePath": str(args.browser.resolve()), "headless": True}), encoding="utf-8")
            subprocess.run([node, str(args.cli.resolve()), "-i", str(mmd), "-o", str(svg),
                            "-c", str(theme), "-p", str(browser), "-b", "#ffffff"], check=True, timeout=60)
            exported = svg.read_text(encoding="utf-8")
            document = ET.fromstring(exported)
            if document.tag != "{http://www.w3.org/2000/svg}svg" or not document.get("viewBox"):
                raise ValueError("Renderer returned an invalid SVG: "+kind)
            if any(element.tag.rsplit("}", 1)[-1] in ("script", "foreignObject") for element in document.iter()):
                raise ValueError("SVG must not contain scripts or foreignObject labels: "+kind)
            digest = hashlib.sha256(source.encode()).hexdigest()
            exported = exported.replace("<svg ", '<svg data-source-sha256="'+digest+'" ', 1)
            if ET.fromstring(exported).get("data-source-sha256") != digest:
                raise ValueError("Could not attach source fingerprint: "+kind)
            svg.write_text(exported, encoding="utf-8")
            mmd.replace(folder/(kind+".mmd"))
            svg.replace(folder/(kind+".svg"))
        print(kind+": Mermaid and SVG regenerated")


if __name__ == "__main__":
    main()
