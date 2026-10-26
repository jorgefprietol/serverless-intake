"""Check documentation links and the editable sources of exported diagrams."""
import hashlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
failures = []
markdown_files = [ROOT/'README.md', *(ROOT/'docs').rglob('*.md')]
for markdown in markdown_files:
    text = markdown.read_text(encoding='utf-8')
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if '://' in link or link.startswith(('#', 'mailto:')):
            continue
        target = link.split('#', 1)[0]
        if target and not (markdown.parent/target).exists():
            failures.append(f'{markdown.relative_to(ROOT)}: missing {link}')

for kind in ('architecture', 'flow'):
    markdown = ROOT/'docs'/f'{kind}.md'
    mmd = ROOT/'docs/diagrams'/f'{kind}.mmd'
    svg = ROOT/'docs/diagrams'/f'{kind}.svg'
    try:
        blocks = re.findall(r'```mermaid\s*\n(.*?)```', markdown.read_text(encoding='utf-8'), re.S)
        if len(blocks) != 1:
            raise ValueError('expected one Mermaid source block')
        source = blocks[0].strip()+'\n'
        if source != mmd.read_text(encoding='utf-8'):
            raise ValueError('Markdown and .mmd sources differ')
        expected = hashlib.sha256(source.encode()).hexdigest()
        diagram = ET.parse(svg).getroot()
        if diagram.tag != '{http://www.w3.org/2000/svg}svg':
            raise ValueError('invalid SVG root')
        if diagram.get('data-source-sha256') != expected:
            raise ValueError('SVG must be regenerated after source changes')
        if not diagram.get('viewBox'):
            raise ValueError('SVG has no viewBox')
        if any(node.tag.rsplit('}', 1)[-1] in ('script', 'foreignObject') for node in diagram.iter()):
            raise ValueError('export must use portable vector labels')
    except (OSError, ET.ParseError, ValueError) as exc:
        failures.append(f'{kind}: {exc}')

if not (ROOT/'docs/technologies.md').is_file():
    failures.append('missing technology inventory')
if failures:
    raise SystemExit('\n'.join(failures))
print('Documentation links, two SVG exports and Mermaid source hashes OK')
