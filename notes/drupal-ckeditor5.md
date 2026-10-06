# Pasting custom HTML into the NJIT Drupal sites (CKEditor 5)

The body text on cs.njit.edu is edited in Drupal's CKEditor 5. Pasting HTML in
**Source** mode is not the last word: when the page is saved, CKEditor parses the HTML
into its own document model and writes it back out. Markup that does not map cleanly
onto that model gets rewritten, sometimes in ways that wreck the layout.

## Case: PhD student directory (October 2026)

Page: <https://cs.njit.edu/phd-student-directory>

**What was pasted.** A card with a `<ul>`; each `<li>` was a flex row holding a
`<strong>` name and a `<span style="display:block;flex:1.4 1 340px">` that wrapped the
link buttons (Email, Website, LinkedIn, ...), separated by spaces.

**Symptom.** The buttons were thrown to opposite edges of the row, two per line, with big
empty gaps between them.

**What Drupal actually saved** (from the live DOM):

```html
<li style="display:flex; ...">
  <strong style="...">Name</strong>
  <a style="...button..." href="mailto:..."><span style="display:block;flex:1.4 1 340px;..."><strong><img ...>Email</strong></span></a>
  <span style="display:block;flex:1.4 1 340px;..."> </span>
  <a style="...button..." href="https://..."><span style="display:block;flex:1.4 1 340px;..."><strong><img ...>Website</strong></span></a>
  ...
</li>
```

The one wrapping `<span>` was pushed *inside* every link and copied onto every space
between links. Each copied space became a 340px-wide flex item in the row, which is what
pushed the buttons apart.

**Fix.** Rebuilt with `<div>`s only (see the rules below). Checked with a CKEditor round
trip (the output was identical, and stable on a second save) and against the live theme
CSS at desktop and phone widths. The fixed markup, ready to paste into Source mode, is
[examples/phd-student-directory.html](examples/phd-student-directory.html).

## Why it happens

CKEditor 5 handles two kinds of elements differently:

- **Blocks and containers**: `<p>`, headings, `<div>`, `<table>`, lists. These stay real
  elements in the document tree, so their attributes and styles survive as written.
- **Inline formatting**: `<a>`, `<span>`, `<strong>`, `<em>`, etc. These are stored as
  *attributes on runs of text*, not as elements. On save, CKEditor rebuilds the tags
  around each run in its own nesting order (the link outermost). Any inline element that
  wraps more than one run (several links, or links plus the spaces between them) is split
  into one copy per run and moved inside the link.

## Other rewrites seen on save

- `font-weight:600` (or `bold`) in a `style` is removed and replaced with a `<strong>`
  wrapper.
- `width` / `height` in an `<img>` style move to `width` / `height` attributes.
- Style properties are reordered alphabetically, and some shorthands are expanded
  (`border:0` became `border-*-width:0`; `background:` became `background-color:`).
- List items get a `data-list-item-id` attribute.
- Kept as written: inline `style`, `role`, `aria-*`, `title`, `target`, `rel`, `href`,
  and `<img>` icons loaded from cdn.jsdelivr.net.

## Rules for paste-in HTML

1. Build every layout box (cards, flex rows, columns, grids) out of `<div>`. Never use
   `<span>`, `<strong>` or `<a>` as a layout container.
2. Let an inline element wrap only **one** thing, such as a single button's icon and
   label.
3. Put a row of links directly inside a flex `<div>` and space them with `gap`. Leave no
   spaces or `&nbsp;` between the `<a>` tags.
4. Don't use `<ul>` / `<li>` for layout. Use `<div role="list">` and
   `<div role="listitem">`, which keeps the list semantics for screen readers.
5. Write bold as `<strong>`, not `font-weight`, and size images with `width` / `height`
   attributes, so what you paste is already in the form CKEditor saves.
6. Use inline `style` attributes only. Not tested yet: `<style>` blocks, `<script>`,
   inline `<svg>`.

The pattern the directory now uses:

```html
<div role="list">
  <div role="listitem" style="display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;">
    <div style="flex:1 1 245px;min-width:0;"><strong>Name</strong></div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;flex:1.4 1 340px;min-width:0;"><a href="..." style="...button..."><strong><img src="..." width="16" height="16" alt="">Email</strong></a><a href="..." style="...button..."><strong><img src="..." width="16" height="16" alt="">Website</strong></a></div>
  </div>
</div>
```

## Testing before you paste

**1. CKEditor round trip.** Open any page on `cdn.jsdelivr.net` (for example
<https://cdn.jsdelivr.net/npm/ckeditor5@43.3.1/package.json>), open the browser
DevTools console, and run:

```js
const C = await import('https://cdn.jsdelivr.net/npm/ckeditor5@43.3.1/dist/browser/ckeditor5.js');
document.body.innerHTML = '<div id="ed"></div>';
const ed = await C.ClassicEditor.create(document.getElementById('ed'), {
  plugins: [C.Essentials, C.Paragraph, C.Heading, C.Bold, C.Italic, C.Link, C.List,
            C.Image, C.ImageInline, C.ImageBlock, C.LinkImage, C.Table, C.BlockQuote,
            C.GeneralHtmlSupport, C.HtmlComment, C.SourceEditing],
  // Same as Drupal's "Full HTML": allow any element, attribute, class and style.
  htmlSupport: { allow: [{ name: /.*/, attributes: true, classes: true, styles: true }] },
});
const roundTrip = html => { ed.setData(html); return ed.getData(); };

// Paste your markup between the backticks:
const out = roundTrip(`<div>...</div>`);
console.log(out);
console.log('stable on second save:', roundTrip(out) === out);
```

Compare `out` with what you pasted. Look for spans that were split or moved inside links,
and for wrappers that disappeared. This setup reproduced the broken directory markup
exactly. It doesn't load Drupal's own plugins, though, so the real save is still the final
check.

**2. Theme check.** On the live page, open DevTools, swap the old block for the new
markup (Elements panel, right-click, *Edit as HTML*), and look at the result at desktop
and phone widths. This only changes your own browser tab. The NJIT theme CSS did not
interfere with div-based layouts styled with inline `style`.
