<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="DoubleAgent.scan" width="520">
  </picture>
</h1>

<p align="center">
  Find the hidden instructions in <code>AGENTS.md</code> that turn your AI agent into a <b>double agent</b>.<br>
  Text that <b>humans can't see, but agents read and obey.</b>
</p>

<p align="center">
  One Python file · no dependencies · no install · Windows, macOS and Linux
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/scanner-dark.svg">
    <img src="assets/scanner-light.svg" alt="Terminal: doubleagent_scan.py finds invisible Unicode, an HTML comment, bidi characters and phantom math in agent instruction files" width="860">
  </picture>
</p>

## ⚡ Quick start

```bash
curl -O https://raw.githubusercontent.com/DrCarles/DoubleAgent.scan/main/scripts/doubleagent_scan.py
python doubleagent_scan.py
```

That's it. It scans every agent instruction file under the current folder and tells you
what's hiding, where, and what it says.

| Exit code | Means |
| --- | --- |
| `0` | All clean |
| `1` | Something is hiding |
| `2` | A file couldn't be read |

> Read the script before you run it. It's one short file, and that's exactly the habit
> this project is about.

## 📄 Which files?

Give it files, directories, or both. Directories are searched recursively for agent
instruction files. Without arguments it searches the current folder. It looks for:

`AGENTS.md` · `AGENT.md` · `CLAUDE.md` · `CLAUDE.local.md` · `GEMINI.md` · `.cursorrules` ·
`.windsurfrules` · `.clinerules` · `copilot-instructions.md` · `SKILL.md` · `CONVENTIONS.md` ·
`*.mdc` · `*.instructions.md` · `*.prompt.md`

It skips `.git`, `node_modules`, virtual envs, `dist` and `build`.

```bash
python doubleagent_scan.py                       # agent files under the current folder
python doubleagent_scan.py ~/projects/my-app     # agent files under another folder
python doubleagent_scan.py --all docs/           # every Markdown and text file under docs/
python doubleagent_scan.py README.md src/        # mix files and folders
python doubleagent_scan.py --ascii AGENTS.md     # strict: flag any non-ASCII character
```

## 🎯 What it catches

| Trick | Level | Try it |
| --- | --- | --- |
| Invisible Unicode tag characters, **decoded back to text** | 🔴 HIGH | [01](samples/01-unicode-tags.md) |
| Zero-width characters | 🔴 HIGH | [02](samples/02-zero-width.md) |
| Bytes smuggled in variation selectors, **decoded** | 🔴 HIGH | [03](samples/03-variation-selectors.md) |
| Bidirectional controls that reorder text | 🔴 HIGH | [04](samples/04-bidi-controls.md) |
| HTML comments, including unclosed ones | 🔴 HIGH | [05](samples/05-html-comments.md) |
| Markdown `[//]: #` comments | 🔴 HIGH | [06](samples/06-markdown-comments.md) |
| HTML hidden with `hidden` or CSS | 🔴 HIGH | [07](samples/07-hidden-html.md) |
| Colored text (HTML colors, `\color` math) | 🔴 HIGH | [08](samples/08-colored-text.md) |
| Invisible `\phantom` math | 🔴 HIGH | [09](samples/09-invisible-math.md) |
| Collapsed `<details>` blocks | 🟡 WARN | [10](samples/10-collapsed-details.md) |
| Link titles and image alt text | 🟡 WARN | [11](samples/11-link-titles.md) |
| Text pushed off-screen | 🟡 WARN | [12](samples/12-off-screen-text.md) |
| Terminal escape codes that hide text in `cat` and `git diff` | 🔴 HIGH | [13](samples/13-terminal-escape.md) |
| Soft hyphens and lookalike spaces that dodge searches | 🔴 HIGH / 🟡 WARN | [14](samples/14-soft-hyphens-and-spaces.md) |
| Other control and invisible format characters | 🔴 HIGH | |
| Private-use characters, invalid UTF-8 | 🟡 WARN | |

HTML and Markdown inside code blocks is skipped, since it's shown as-is. Invisible
characters are flagged everywhere.

## 🤖 Run it in CI

Copy `doubleagent_scan.py` into your repo (for example `scripts/`), so you review it once and
it can't change under you. Then add `.github/workflows/hidden-instructions.yml`:

```yaml
name: Hidden instructions
on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/doubleagent_scan.py
```

Every pull request that touches an agent file with hidden content now fails.

## 🪝 Or as a pre-commit hook

Save as `.git/hooks/pre-commit` and make it executable (`chmod +x`):

```sh
#!/bin/sh
python3 scripts/doubleagent_scan.py
```

## 😈 Why this matters

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
    <img src="assets/hero-light.svg" alt="Same text: you see a harmless rule, the AI agent also reads a hidden malicious instruction" width="840">
  </picture>
</p>

Your coding agent **trusts** its instruction files. It runs commands, edits code and can
read secrets. A hidden line in a pull request, a copied template or a pasted snippet is
all it takes:

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/attack-dark.svg">
    <img src="assets/attack-light.svg" alt="Attack flow: an attacker hides instructions in AGENTS.md through a pull request, template or snippet. You review it and it looks fine, but the AI agent reads everything and runs the hidden instructions." width="840">
  </picture>
</p>

The worst tricks (samples 01 to 04) are invisible **even in the raw file and the PR diff**.
Careful reviewing won't save you. A scanner will.

> **True story:** while building this repo, example escape codes for invisible
> characters were written to disk as *real* invisible characters. Four times. The scanner
> caught every one. It's that easy.

## 🎓 Training & awareness: 14 live samples

The [samples/](samples/README.md) folder shows each trick in action. Every sample has:

- a short explanation: what you see, what the agent reads, how to spot it;
- a ready-made test `AGENTS.md` with a **harmless** hidden instruction.

Use them to train your team, or to see whether **your** AI agent falls for it.
[Test your agent](samples/README.md#-test-your-agent)

## 🛡️ Stay safe

- Scan every change to agent files, and every snippet you copy from the web.
- Review agent files **raw**, never just the pretty rendered page.
- Keep them plain ASCII, so anything else stands out (`--ascii`).
- Require code-owner review for `AGENTS.md`, `CLAUDE.md`, `.cursor/`, `.github/`.
- Don't dismiss GitHub's *"hidden or bidirectional Unicode"* warning.

## ⚠️ Limits

- It finds **hiding tricks**, not bad instructions written in plain sight. Still read them!
- It's a heuristic: a harmless `<details>` block or a link title will show up as `WARN`.
- It doesn't look at images, PDFs or web pages your agent fetches.

## 📁 What's inside

```
scripts/
   doubleagent_scan.py  the scanner
   make_samples.py      builds the samples
samples/             14 live demos + test guide
assets/              images
```

## 📜 License

[MIT](LICENSE). Use it, copy it, ship it.
