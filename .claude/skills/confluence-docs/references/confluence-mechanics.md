# Confluence authoring mechanics

Verified against `getContentFormatGuide` (toolName `createConfluencePage`) on
2026-09-24. These are the parts that cost a round trip if you get them wrong.

## Body format

Page bodies are **HTML fragments**. Not Markdown, not Confluence storage XML.

- Never emit `<ac:structured-macro>`, `<ac:rich-text-body>`, `<ac:plain-text-body>`,
  `<ri:page>`, or CDATA. It renders as raw text on the page.
- Never wrap the body in `<html>`, `<body>`, or `<head>`.
- Never wrap the body in Markdown code fences.

## Blocks you will actually use

| Element | Pattern |
| --- | --- |
| Heading | `<h1>` through `<h6>` |
| Paragraph | `<p>text</p>` |
| Metadata header | `<blockquote><p>...</p></blockquote>` |
| Table | `<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>c</td></tr></tbody></table>` |
| Code block | `<pre><code class="language-bash">...</code></pre>` |
| Panel | `<div data-type="panel-info">...</div>`, types: `info`, `note`, `warning`, `success`, `error` |
| Expand | `<details><summary>Title</summary><p>hidden</p></details>` |
| Task list | `<ul data-type="task-list"><li data-type="task-item"><input type="checkbox"> item</li></ul>` |
| Decision list | `<ul data-type="decision-list"><li data-type="decision-item" data-state="DECIDED">text</li></ul>` |
| Rule | `<hr>` |
| Date | `<time datetime="2026-09-24">24 September 2026</time>` |
| Status lozenge | `<span data-type="status" data-color="green">Done</span>` (colors: neutral, purple, blue, red, yellow, green) |

A panel may **not** contain a table, an expand, a blockquote, or another panel.

## Tables

- `<th>` for header cells, `<thead>`/`<tbody>` for grouping.
- **When editing an existing table, copy every cell's `data-colwidth` verbatim.**
  Dropping it resets the table to evenly distributed columns.
- Cell background uses `data-background="#DEEBFF"` from the supported palette only.

## Links

- A link whose text has to read as part of a sentence: plain `<a href="URL">text</a>`.
- A bare URL, a link alone in a paragraph, or an entry in a related-links list: a smart
  link, `<a href="URL" data-card-appearance="inline"></a>`. Leave the anchor **empty**:
  card appearances drop anchor text and render the target's live title.
- `block` for a single link the page is highlighting, `embed` for video and whiteboard
  URLs so the full view renders in place.
- Same-page jumps are `#Heading-text`: a hash, plus the heading text with whitespace
  replaced by hyphens. Duplicate headings get `.1`, `.2`. Never write "section 9" or an
  invented number and call it a link.

## Images and attachments

1. Attach the file to the page first.
2. Use the returned media id and collection in the figure pattern:

```html
<figure data-type="media-single" data-layout="center" data-width="80" data-width-type="percentage">
  <div data-type="media" data-media-type="file" data-id="MEDIA_ID" data-collection="COLLECTION"
       data-alt="What the diagram shows"></div>
</figure>
```

- Percentage widths: `80` for diagrams, `60` for screenshots, `100` sparingly.
- Local filesystem paths and `/wiki/download/attachments/...` URLs do **not** work.
- `data-alt` describes what the image conveys, not the filename.
- External images need no upload: `<img src="https://..." alt="..." width="400">`.

## Macros

Native macros use `data-extension-type="com.atlassian.confluence.macro.core"`:

```html
<div data-type="extension" data-extension-key="toc"
     data-extension-type="com.atlassian.confluence.macro.core"
     data-parameters='{"macroParams":{"maxLevel":{"value":"3"}},"macroMetadata":{"schemaVersion":{"value":"1"},"title":"Table of Contents"}}'></div>
```

Useful keys: `toc` (`minLevel`, `maxLevel`), `children` (`all`, `depth`),
`contentbylabel` (`cql`, `max`), `jira` (`jqlQuery`, `showSummary`),
`pagetree` and `livesearch` (inline, inside a `<p>`). Omit `macroId`: Confluence
generates it. All `macroParams` values are strings wrapped as `{"value":"..."}`.

## IDs you must never invent

`data-id`, `data-collection`, `data-media-id`, `data-media-collection`,
`data-resource-id`, `data-annotation-id`, and a mention's `data-user-id` (an Atlassian
account id). Copy them from fetched content or a tool response. When an account id is
unknown, write plain text such as `[@Platform Engineering]` instead of a mention.

`data-local-id` is the final 12 characters of a UUID, lowercase hex. Preserve fetched
ones; omit them on new nodes.

## Call sequence

`cloudId` is `wiselausnir.atlassian.net`. On every execute-family call it is a
**top-level** argument, a sibling of `name` and `inputs`, never inside `inputs`.

1. `getConfluenceSpace` for the target space, once per task. Apply any
   `spaceInstructions` it returns.
2. `getContentFormatGuide` with `toolName: "createConfluencePage"` if you need the full
   format reference beyond this file. That exact `toolName` is the only valid one;
   `createConfluenceContent` is rejected.
3. Create with `createConfluenceContent`, passing `parentId` to place the page in the
   tree. Update with `updateConfluencePage` through `executeWrite`.
4. Apply labels after create.
5. Read back with `getConfluenceContent` and `detail: "full"` to confirm the body
   rendered as intended. Fetch as HTML before editing anything: a Markdown fetch drops
   images, panels, and expands, and returns statuses and mentions as literal text.

If a fetched body looks incomplete or a publish fails validation, **stop and say what
looks unsupported**. Do not overwrite destructively.

## Discovery

The Confluence operations are a mix of primary tools (`searchConfluence`,
`getConfluenceContent`, `createConfluenceContent`) and discovered ones run through
`executeRead` / `executeWrite` / `executeDestructive`. When an operation name is not
already in the tool list, call `discover` with the goal rather than guessing a name.

Operations worth knowing: `listConfluenceContent` (one content type in one space),
`getConfluenceContentAncestors`, `listConfluenceAttachments`, `listConfluenceSpaces`,
`listConfluenceTemplates`.
