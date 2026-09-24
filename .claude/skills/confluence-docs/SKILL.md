---
name: confluence-docs
description: Use when writing, updating, or restructuring documentation that lives in Confluence. Enforces the house format (one declared document type per page, a metadata header, single source of truth cited not copied), and carries the Confluence authoring mechanics that otherwise cost a round trip. Invoke as /confluence-docs [PAGE-OR-TREE].
user-invocable: true
---

# Confluence Docs

Author and maintain a Confluence documentation set to one format, so the set reads as
one thing rather than as a pile of pages by different hands on different days.

## Inputs

- `PAGE-OR-TREE`: the page or tree being written or updated. If omitted, use the target
  from session context; if ambiguous, ask before writing anything.
- The target space and tree root come from the **Documentation home** section of
  `CLAUDE.local.md`. If that section is missing, ask for the space key and tree root
  and offer to record them there. Never hardcode a space in a page or a script.

## Phase 1: Place the page before writing it

1. Read `CLAUDE.local.md` for the documentation home: space key, space id, tree root,
   label prefix.
2. Call `getConfluenceSpace` once for the target space and apply any `spaceInstructions`
   it returns to the whole body, not just the title.
3. Find the parent. A page belongs under exactly one section of the tree. If it fits
   under two, it is two pages.
4. Decide the document **type** before the first sentence. One type per page. Mixing
   types on one page is the single most common way a set becomes unreadable: split
   instead.

| Type | Answers | Shape | Review |
| --- | --- | --- | --- |
| Explainer | Why it is this way. Concepts. | Prose. Rarely changes. | Annual |
| Reference | What it is. Factual. | Tables over prose. A short wrapper paragraph, then 2-3 tables. | Bi-annual |
| Runbook | How to do it. | Numbered steps. Step count and expected duration at the top. | Quarterly |
| Decision | What was settled and what followed from it. | Context, decision, consequences, status, ticket. | On supersession only |
| Status | What is live and what remains, as of a date. | Dated. Tables of open items with ticket ids. | Each milestone |

A Decision page is not reopened. A disagreement becomes a new record that supersedes
it, and the old record keeps its text with a superseded marker.

## Phase 2: The header every page carries

The first block of every page is a `<blockquote>`:

```html
<blockquote>
  <p><strong>Area:</strong> Azure Platform &middot; <strong>Type:</strong> Reference &middot;
     <strong>Owner:</strong> Platform Engineering &middot;
     <strong>Labels:</strong> <code>azure-platform</code>, <code>identity</code></p>
  <p><strong>Purpose:</strong> One sentence saying what this page answers and when you would need it.</p>
  <p><strong>Source of truth:</strong> <code>wise-azure-infra/docs/data-plane-architecture-decisions.md</code> &middot;
     <strong>Last reviewed:</strong> <time datetime="2026-09-24">24 September 2026</time></p>
</blockquote>
```

- **Owner** is a role, never a person. An unowned page is a page nobody will fix.
- **Labels** are 2 to 5, starting with the tree's label prefix. Reuse existing labels
  before inventing one.
- **Source of truth** is the repo path the page defers to, or `this page` when the page
  is itself authoritative.
- **Last reviewed** is a real `<time datetime>` element, not prose.

Apply the same labels to the page in Confluence after creating it, not just in the
header text. The header is for the reader; the labels are for search.

## Phase 3: Single source of truth, cited not copied

**The test: if the thing changes when code changes, the repo owns it and the page links
to it.**

| Lives in the repo, linked from Confluence | Lives in Confluence |
| --- | --- |
| Decision records, in full | The decisions index: one line of outcome and status each |
| Executable runbooks that reference repo scripts | The operations index, and the posture those runbooks implement |
| Configuration layouts, naming rules, schemas | The narrative that explains why they look like that |
| Workflow and pipeline definitions | How release and deploy work end to end |
| | The why, the current status, the operator-facing overview, the glossary |

Copying a repo file into Confluence creates a second copy that rots and a reader who
cannot tell which one is true. Link instead, and quote at most the one line that makes
the link worth following.

## Phase 4: Writing standards

- **No em dashes.** Anywhere. Use commas, colons, or parentheses.
- **State current behavior and why. Never narrate what it used to be.** Superseded
  reasoning is cited from the decision record, not copied into the page.
- **Write for someone six months behind you.** Every abbreviation expanded on first use.
  Every tool named with a link.
- **Lead with the headline, not the history.** The first paragraph after the header
  answers: what is this, and when would I need it.
- **Tables over prose for reference data.** If you are writing "X is Y, and X2 is Y2",
  it is a table.
- **Runbooks declare step count and expected duration** at the top, so the reader can
  judge whether to start now or later.
- **No dead links.** Every internal link resolves. Every external link is dated.
- **Real dates use `<time datetime="YYYY-MM-DD">`.** Never plain text, and never for
  durations or versions.

## Phase 5: Maintenance

- A ticket that changes platform behavior updates the affected page **in the same
  ticket**. Documentation is not a follow-up.
- A new page is linked from its section index by hand, in the same change.
- A page that should die is **retired, not deleted**: move it under an `Archive` child,
  re-title it with the retirement date, and point it at its replacement. This keeps the
  history an audit can ask for.
- When a page's Source of truth file moves or is deleted, the page is stale by
  definition. Fix the link or retire the page.

## Anti-patterns

| Pattern | Why it hurts | Do instead |
| --- | --- | --- |
| The copy-paste silent branch | Two near-identical pages drift apart, and neither says which is current. | Edit the source page. |
| The lore page | 3000 words of why, burying the how. | Split the Explainer from the Runbook and link them. |
| The "Misc" page | Unrelated items collected because nobody decided where each belongs. | One page per topic, linked from an index. |
| The unowned page | Nobody reviews it, so it rots silently. | Set the Owner role before publishing. |
| The repo mirror | A page that duplicates a repo file instead of linking to it. | Link it, and quote the one line worth quoting. |

## References

- `references/page-types.md`: a skeleton per document type, ready to fill in.
- `references/confluence-mechanics.md`: the authoring mechanics and the MCP call
  sequence. Read it before writing a page body; the body format is not Markdown and is
  not Confluence storage XML.
