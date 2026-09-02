---
name: drawio
description: Always use when user asks to create, generate, draw, or design a diagram, flowchart, architecture diagram, ER diagram, sequence diagram, class diagram, network diagram, mockup, wireframe, or UI sketch, or mentions draw.io, drawio, drawoi, .drawio files, or diagram export to PNG/SVG/PDF.
---

# Draw.io Diagram Skill

Generate draw.io diagrams as native `.drawio` files. Optionally export to PNG, SVG, or PDF with the diagram XML embedded (so the exported file remains editable in draw.io), or generate a browser URL that opens the diagram directly in the draw.io editor.

## How to create a diagram

1. **Generate draw.io XML** in mxGraphModel format for the requested diagram
2. **Write the XML** to a `.drawio` file in the current working directory using the Write tool
3. **Handle the requested output format**:
   - `png` / `svg` / `pdf` → locate the draw.io CLI (see [draw.io CLI](#drawio-cli)), export with `--embed-diagram`, then delete the source `.drawio` file. If the CLI is not found, keep the `.drawio` file and tell the user they can install the draw.io desktop app to enable export, or use `url` mode instead, or open the `.drawio` file directly
   - `url` → generate a browser URL from the XML and open it (see [Browser URL output](#browser-url-output)). Keep the `.drawio` file as a persistent local copy
   - *(no format)* → no extra step; the `.drawio` file is the output
4. **Open the result** — the exported file if exported, the browser URL if `url`, or the `.drawio` file otherwise. If the open command fails, print the file path (or URL) so the user can open it manually

## Choosing the output format

Check the user's request for a format preference. Examples:

- `/drawio create a flowchart` → `flowchart.drawio`
- `/drawio png flowchart for login` → `login-flow.drawio.png`
- `/drawio svg: ER diagram` → `er-diagram.drawio.svg`
- `/drawio pdf architecture overview` → `architecture-overview.drawio.pdf`
- `/drawio url flowchart for user login` → opens browser at `app.diagrams.net` with the diagram, keeps `login-flow.drawio` locally

If no format is mentioned, just write the `.drawio` file and open it in draw.io. The user can always ask to export later.

### Supported export formats

| Format | Embed XML | Notes |
|--------|-----------|-------|
| `png` | Yes (`-e`) | Viewable everywhere, editable in draw.io |
| `svg` | Yes (`-e`) | Scalable, editable in draw.io |
| `pdf` | Yes (`-e`) | Printable, editable in draw.io |
| `jpg` | No | Lossy, no embedded XML support |

PNG, SVG, and PDF all support `--embed-diagram` — the exported file contains the full diagram XML, so opening it in draw.io recovers the editable diagram.

## Browser URL output

When the user requests `url` format, generate a draw.io URL that opens the diagram directly in the browser editor at `app.diagrams.net` — no draw.io Desktop required.

### How it works

1. The `.drawio` file is written to disk as usual (gives the user a persistent local copy they can re-edit)
2. The XML is compressed with Node.js's built-in `zlib` and base64-encoded
3. The result is embedded in a `https://app.diagrams.net/#create=...` URL
4. The URL is opened in the default browser

This uses only Node.js built-in modules (`zlib`, `child_process`) — no external dependencies.

### URL generation

Run this `node -e` one-liner to read the `.drawio` file and print the URL (replace `DIAGRAM.drawio` with the actual filename):

```bash
URL=$(node -e '
const fs = require("fs");
const zlib = require("zlib");
const xml = fs.readFileSync(process.argv[1], "utf8");
const compressed = zlib.deflateRawSync(encodeURIComponent(xml)).toString("base64");
const payload = encodeURIComponent(JSON.stringify({ type: "xml", compressed: true, data: compressed }));
console.log("https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create=" + payload);
' DIAGRAM.drawio)
```

The URL format matches the MCP Tool Server. Node.js's `zlib.deflateRawSync` and `pako.deflateRaw` both implement RFC 1951 and produce identical output, so URLs from either source are interchangeable.

### Opening the URL

| Environment | Command |
|-------------|---------|
| macOS | `open "$URL"` |
| Linux (native) | `xdg-open "$URL"` |
| WSL2 | Write a temp `.url` file, open via `cmd.exe` (see below) |
| Windows (native) | Write a temp `.url` file, open via `start` (see below) |

**Why the `.url` workaround on Windows/WSL2?** `cmd.exe`'s `start` command treats `&` as a command separator and strips everything after `#` in URLs. The diagram payload lives in the `#create=...` fragment, so passing the URL directly causes it to be silently lost. A `.url` shortcut file preserves the URL intact.

**macOS / Linux example:**

```bash
open "$URL"      # macOS
xdg-open "$URL"  # Linux
```

**WSL2 example:**

```bash
TMPFILE=$(mktemp --suffix=.url)
printf '[InternetShortcut]\r\nURL=%s\r\n' "$URL" > "$TMPFILE"
cmd.exe /c start "" "$(wslpath -w "$TMPFILE")"
```

**Windows (native) example:**

```cmd
echo [InternetShortcut] > %TEMP%\drawio.url
echo URL=%URL% >> %TEMP%\drawio.url
start "" "%TEMP%\drawio.url"
```

### After opening

Print the URL so the user can copy or share it, and confirm the local file path:

```
Opened in browser: <URL>
Local file: DIAGRAM.drawio
```

The `.drawio` file stays on disk so the user can re-edit it later, attach it elsewhere, or export it to an image format on demand.

### URL length

The URL embeds the full compressed diagram in its hash fragment. Very large diagrams may hit browser URL length limits (typically ~32K–2MB depending on the browser). For complex diagrams that exceed the limit, fall back to writing the `.drawio` file and opening it locally.

## draw.io CLI

The draw.io desktop app includes a command-line interface for exporting.

### Locating the CLI

First, detect the environment, then locate the CLI accordingly:

#### WSL2 (Windows Subsystem for Linux)

WSL2 is detected when `/proc/version` contains `microsoft` or `WSL`:

```bash
grep -qi microsoft /proc/version 2>/dev/null && echo "WSL2"
```

On WSL2, use the Windows draw.io Desktop executable via `/mnt/c/...`:

```bash
DRAWIO_CMD=`/mnt/c/Program Files/draw.io/draw.io.exe`
```

The backtick quoting is required to handle the space in `Program Files` in bash.

If draw.io is installed in a non-default location, check common alternatives:

```bash
# Default install path
`/mnt/c/Program Files/draw.io/draw.io.exe`

# Per-user install (if the above does not exist)
`/mnt/c/Users/$WIN_USER/AppData/Local/Programs/draw.io/draw.io.exe`
```

#### macOS

```bash
/Applications/draw.io.app/Contents/MacOS/draw.io
```

#### Linux (native)

```bash
drawio   # typically on PATH via snap/apt/flatpak
```

#### Windows (native, non-WSL2)

```
"C:\Program Files\draw.io\draw.io.exe"
```

Use `which drawio` (or `where draw.io` on Windows) to check if it's on PATH before falling back to the platform-specific path.

### Export command

```bash
drawio -x -f <format> -e -b 10 -o <output> <input.drawio>
```

**WSL2 example:**

```bash
`/mnt/c/Program Files/draw.io/draw.io.exe` -x -f png -e -b 10 -o diagram.drawio.png diagram.drawio
```

Key flags:
- `-x` / `--export`: export mode
- `-f` / `--format`: output format (png, svg, pdf, jpg)
- `-e` / `--embed-diagram`: embed diagram XML in the output (PNG, SVG, PDF only)
- `-o` / `--output`: output file path
- `-b` / `--border`: border width around diagram (default: 0)
- `-t` / `--transparent`: transparent background (PNG only)
- `-s` / `--scale`: scale the diagram size
- `--width` / `--height`: fit into specified dimensions (preserves aspect ratio)
- `-a` / `--all-pages`: export all pages (PDF only)
- `-p` / `--page-index`: select a specific page (1-based)

### Opening the result

| Environment | Command |
|-------------|---------|
| macOS | `open <file>` |
| Linux (native) | `xdg-open <file>` |
| WSL2 | `cmd.exe /c start "" "$(wslpath -w <file>)"` |
| Windows | `start <file>` |

**WSL2 notes:**
- `wslpath -w <file>` converts a WSL2 path (e.g. `/home/user/diagram.drawio`) to a Windows path (e.g. `C:\Users\...`). This is required because `cmd.exe` cannot resolve `/mnt/c/...` style paths.
- The empty string `""` after `start` is required to prevent `start` from interpreting the filename as a window title.

**WSL2 example:**

```bash
cmd.exe /c start "" "$(wslpath -w diagram.drawio)"
```

## File naming

- Use a descriptive filename based on the diagram content (e.g., `login-flow`, `database-schema`)
- Use lowercase with hyphens for multi-word names
- For export, use double extensions: `name.drawio.png`, `name.drawio.svg`, `name.drawio.pdf` — this signals the file contains embedded diagram XML
- After a successful export, delete the intermediate `.drawio` file — the exported file contains the full diagram
- For `url` mode, keep the `.drawio` file (no double extension) — the URL is a view/edit handle and the local file is the persistent copy

## XML format

A `.drawio` file is native mxGraphModel XML. Always generate XML directly — Mermaid and CSV formats require server-side conversion and cannot be saved as native files.

### Basic structure

Every diagram must have this structure:

```xml
<mxGraphModel background="#FFFFFF" adaptiveColors="auto">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
  </root>
</mxGraphModel>
```

- Cell `id="0"` is the root layer
- Cell `id="1"` is the default parent layer
- All diagram elements use `parent="1"` unless using multiple layers
- Diagram cells go here, with `parent="1"`. Do not write that as an XML comment:
  comments are forbidden (see [XML well-formedness](#critical-xml-well-formedness))

### Page background, and what export actually renders

**Always set `background` explicitly.** Left unset, the page is transparent, and
the editor canvas colour you see is a UI theme that is *not* stored in the file,
so it never survives an export. The result is that what the author sees and what
they export are different pictures. Pinning `background` makes the two agree.

**Export renders light mode.** That has a consequence worth understanding before
choosing colours:

| The diagram should be | Do this |
|---|---|
| Light, everywhere | `background="#FFFFFF"`, light fills, dark fonts. Keep `adaptiveColors="auto"` only if a dark *editor* view matters more than a predictable export. |
| Dark in the exported image | Commit the palette to dark: `background="#1E1E1E"` (or similar), dark fills, light fonts, and **drop `adaptiveColors="auto"`**. |
| Correct in both editor themes, light on export | `background="#FFFFFF"` plus `light-dark(lightColor,darkColor)` per style. |

`adaptiveColors="auto"` and `light-dark()` both switch on the *viewer's* theme,
and export is always the light branch. So neither can produce a dark exported
image — a dark export needs a genuinely dark palette. Conversely, a pinned dark
`background` combined with adaptive or `light-dark()` fills exports light boxes
on a dark ground, which is broken. Pick one row of that table and be consistent.

On a dark page also set **`labelBackgroundColor`** to the page colour on every
edge that carries a label: draw.io punches edge labels out of their line with a
default light background, which shows up as pale strips.

Two colour rules that follow from pinning a background:

- Give every cell that has a `value` an explicit `fontColor`. An unset one
  renders black, which disappears on a dark page.
- No fill may match the page colour, or within a couple of percent of it. A
  container at `#FAFAFA` on a white page is invisible except for its border.

### Text only wraps if you ask it to

**Every cell with prose in it needs `whiteSpace=wrap` in its style**, including
`text;` shapes:

```
style="text;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
```

Without it a shape renders its label as a single unwrapped line that runs past
its own geometry, off the page, and is clipped on export. The `rounded=0;whiteSpace=wrap;html=1;`
prefix used for boxes already covers it; bare `text;` styles are the ones that
get missed, and a long paragraph is exactly where it hurts most.

Two related traps in `html=1` labels, which is all of them:

- A literal `<` or `>` in label text must be written `&amp;lt;` / `&amp;gt;`, not
  `&lt;` / `&gt;`. `&lt;env&gt;` reaches the renderer as `<env>`, which the HTML
  label parser treats as an unknown tag and **renders as nothing** — so
  placeholder names silently vanish. Double-escaping is correct here.
- Line breaks inside a label are `&#10;`.

## XML reference

For the complete draw.io XML reference including common styles, edge routing, containers, layers, tags, metadata, dark mode colors, and XML well-formedness rules, fetch and follow the instructions at:
https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| draw.io CLI not found | Desktop app not installed or not on PATH | Keep the `.drawio` file and tell the user to install the draw.io desktop app, use `url` mode instead, or open the file manually |
| Export produces empty/corrupt file | Invalid XML (e.g. double hyphens in comments, unescaped special characters) | Validate XML well-formedness before writing; see the XML well-formedness section below |
| Diagram opens but looks blank | Missing root cells `id="0"` and `id="1"` | Ensure the basic mxGraphModel structure is complete |
| Text runs off the page, or is clipped in the export | The cell's style has no `whiteSpace=wrap` | Add `whiteSpace=wrap` to every cell with a label, `text;` shapes included |
| Background is white on export but not in the editor | No `background` on `mxGraphModel`; the editor canvas colour is a UI theme and is not in the file | Set `background` explicitly, and pick a palette to match (see [Page background](#page-background-and-what-export-actually-renders)) |
| A placeholder like `<env>` renders as nothing | Written `&lt;env&gt;`, so the `html=1` label parser sees `<env>` and drops it as an unknown tag | Write `&amp;lt;env&amp;gt;` |
| Pale strips behind edge labels on a dark page | draw.io's default light edge-label background | Set `labelBackgroundColor` to the page colour on every labelled edge |
| Edges not rendering | Edge mxCell is self-closing (no child mxGeometry element) | Every edge must have `<mxGeometry relative="1" as="geometry" />` as a child element |
| File won't open after export | Incorrect file path or missing file association | Print the absolute file path so the user can open it manually |
| Browser opens with empty diagram in `url` mode | `cmd.exe` stripped the `#create=...` fragment | Use the `.url` temp-file workaround on Windows/WSL2 (see [Opening the URL](#opening-the-url)) — never pass the URL directly to `cmd.exe /c start` |
| URL is too long for the browser | Very large diagram exceeds browser URL length limit | Fall back to writing the `.drawio` file and opening it locally |

## CRITICAL: XML well-formedness

- **NEVER include ANY XML comments (`<!-- -->`) in the output.** XML comments are strictly forbidden — they waste tokens, can cause parse errors, and serve no purpose in diagram XML.
- Escape special characters in attribute values: `&amp;`, `&lt;`, `&gt;`, `&quot;`
- Always use unique `id` values for each `mxCell`