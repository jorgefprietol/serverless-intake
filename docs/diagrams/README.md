# Diagramas editables

Las fuentes están en [arquitectura](../architecture.md) y [flujo](../flow.md), con un bloque Mermaid por archivo. Los `.mmd` y `.svg` de esta carpeta son exportaciones de esos bloques. Edita primero el Markdown y regenera ambos formatos.

## Regenerar

Requiere Python 3.10+, Node.js, npm y Chrome o Chromium instalado. Desde la raíz del repositorio instala la herramienta de documentación sin descargar otro navegador:

```bash
PUPPETEER_SKIP_DOWNLOAD=true npm --prefix tools/diagrams install
python tools/render_diagrams.py --browser "$CHROME_BIN"
python tools/validate_docs.py
```

`CHROME_BIN` debe contener la ruta absoluta al ejecutable de tu navegador. En PowerShell configura `$env:PUPPETEER_SKIP_DOWNLOAD = 'true'`, ejecuta `npm --prefix tools/diagrams install` y pasa la ruta con `--browser "$env:CHROME_BIN"`.

El renderer usa Mermaid CLI 12.0.0 desde `tools/diagrams/node_modules`. Para una instalación existente puedes indicar `--cli /ruta/a/mermaid-cli/src/cli.js`. [theme.json](theme.json) mantiene el estilo y desactiva etiquetas HTML; no añadas `script` ni `foreignObject` al SVG.

El script valida el SVG antes de reemplazar cada exportación e incluye la huella SHA-256 del bloque Mermaid en `data-source-sha256`. [El validador](../../tools/validate_docs.py) comprueba esa huella, los enlaces y la coincidencia del `.mmd`. Regenerar sólo la imagen sin actualizar la fuente hará fallar esa comprobación.
