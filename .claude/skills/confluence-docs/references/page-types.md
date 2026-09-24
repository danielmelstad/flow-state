# Page skeletons

One skeleton per document type. Fill in and delete what does not apply. Every skeleton
opens with the metadata header from `SKILL.md` Phase 2; it is shown in full once below
and abbreviated as `<!-- header -->` after that.

Bodies are HTML fragments. See `confluence-mechanics.md` before writing one.

## Explainer

Why it is this way. Concepts. Rarely changes. Reviewed annually.

```html
<blockquote>
  <p><strong>Area:</strong> AREA &middot; <strong>Type:</strong> Explainer &middot;
     <strong>Owner:</strong> ROLE &middot;
     <strong>Labels:</strong> <code>label-a</code>, <code>label-b</code></p>
  <p><strong>Purpose:</strong> One sentence: what this page answers and when you would need it.</p>
  <p><strong>Source of truth:</strong> this page &middot;
     <strong>Last reviewed:</strong> <time datetime="YYYY-MM-DD">D Month YYYY</time></p>
</blockquote>

<p>The headline, in two or three sentences. What this is, and why a reader is here.</p>

<h2>The short version</h2>
<p>The claim the rest of the page supports, stated once, plainly.</p>

<h2>Why it is this way</h2>
<p>The constraint or the forcing function. Name it; do not imply it.</p>

<h2>What follows from it</h2>
<ul><li><p>Consequence, with the page that covers it linked.</p></li></ul>

<h2>What this is not</h2>
<p>The nearest thing readers mistake this for, and the difference.</p>
```

## Reference

What it is. Factual. A short wrapper paragraph, then tables. Reviewed bi-annually.

```html
<!-- header, Type: Reference -->

<p>One paragraph: what this page lets you look up, and the one rule that governs it.</p>

<h2>THE THING</h2>
<table>
  <thead><tr><th>Name</th><th>What it is</th><th>Where it is defined</th></tr></thead>
  <tbody><tr><td>...</td><td>...</td><td><code>repo/path.py</code></td></tr></tbody>
</table>

<h2>THE OTHER THING</h2>
<table>...</table>

<h2>Where this is defined</h2>
<p>The repo file this page defers to, linked. Anything that changes when code changes
lives there, not here.</p>
```

## Runbook

How to do it. Step count and expected duration at the top. Reviewed quarterly.

```html
<!-- header, Type: Runbook -->

<div data-type="panel-info">
  <p><strong>N steps &middot; about M minutes.</strong> Run this when CONDITION.
     You need PREREQUISITE ACCESS.</p>
</div>

<h2>Before you start</h2>
<ul><li><p>Precondition that will waste your time if it is not true.</p></li></ul>

<h2>Steps</h2>
<ol>
  <li><p>Do the thing. <code>the exact command</code></p>
      <p>Expected: what you should see. If you see something else, go to Recovery.</p></li>
</ol>

<h2>Verify</h2>
<p>The check that proves it worked, not the check that proves the command ran.</p>

<h2>Recovery</h2>
<p>What to do when a step fails, and who to tell.</p>
```

A runbook whose steps are repo scripts stays in the repo. This page then becomes a
Reference index pointing at it, with the posture it implements.

## Decision

What was settled and what followed. Not reopened. Reviewed only on supersession.

```html
<!-- header, Type: Decision -->

<p><strong>Status:</strong> <span data-type="status" data-color="green">Settled</span> &middot;
   <strong>Decided:</strong> <time datetime="YYYY-MM-DD">D Month YYYY</time> &middot;
   <strong>Ticket:</strong> <a href="https://wiselausnir.atlassian.net/browse/ADA-NNN">ADA-NNN</a></p>

<h2>Context</h2>
<p>The forcing question, and the constraints that were real at the time.</p>

<h2>Decision</h2>
<p>One sentence in the present tense, stating what is true now.</p>

<h2>Consequences</h2>
<ul><li><p>What this makes easy, and what it makes hard or impossible.</p></li></ul>

<h2>What was rejected</h2>
<p>The alternative and the single reason it lost. One paragraph, not a debate.</p>
```

Statuses: `Settled` (green), `Superseded` (neutral, with a link to the record that
replaced it), `Cancelled` (neutral). A superseded record keeps its original text: the
marker goes at the top, and nothing below it is rewritten.

## Status

What is live and what remains, as of a date. Reviewed at each milestone.

```html
<!-- header, Type: Status -->

<div data-type="panel-note">
  <p>As of <time datetime="YYYY-MM-DD">D Month YYYY</time>. This page is dated on
     purpose: if the date is old, do not trust the table.</p>
</div>

<h2>Live today</h2>
<table>
  <thead><tr><th>Environment</th><th>What runs there</th><th>Since</th></tr></thead>
  <tbody>...</tbody>
</table>

<h2>In flight</h2>
<table>
  <thead><tr><th>Ticket</th><th>What it delivers</th><th>Blocked on</th></tr></thead>
  <tbody>...</tbody>
</table>

<h2>Known gaps</h2>
<table>
  <thead><tr><th>Ticket</th><th>Gap</th><th>Why it is acceptable for now</th></tr></thead>
  <tbody>...</tbody>
</table>
```

Prefer a live `jira` macro over a hand-copied ticket table where the query is stable:

```html
<div data-type="extension" data-extension-key="jira"
     data-extension-type="com.atlassian.confluence.macro.core"
     data-parameters='{"macroParams":{"jqlQuery":{"value":"parent = ADA-470 AND statusCategory != Done ORDER BY key"},"showSummary":{"value":"true"}},"macroMetadata":{"schemaVersion":{"value":"1"},"title":"Jira"}}'></div>
```

A hand-copied table goes stale the day after you write it; the macro does not.

## Section index page

A tree node that exists to route readers, not to hold content.

```html
<!-- header, Type: Reference -->

<p>One sentence: what lives under this section and who it is for.</p>

<h2>Pages under here</h2>
<ul>
  <li><p><strong>Page title</strong>: the one line that tells a reader whether to open it.</p></li>
</ul>
```

List the children by hand with a one-line summary each. The `children` macro renders
titles only, which does not help a reader choose.
