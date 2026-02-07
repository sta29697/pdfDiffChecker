# 00_base_rules.md — Global Rules (pdfDiffChecker)

You must follow this file exactly.

## 0. Mandatory Requirements
- Strictly adhere to the repository structure and constraints as described below:
- Maintain all identifiers and file paths exactly as specified (do not translate or rename).
- Do not create new files or folders not included in the plan. If adding, clearly state the reason and obtain permission.
- Do not implement code unless explicitly requested.
- If implementation is requested, implement only within the scope of the specified milestone.
- Always include DocStrings using the Google style.
- In multilingual-enabled areas, code numbers will remain in the code, but include English comments explaining the content.
- When instructed by line number, either modify from the end of the file to prevent line number shifts, or convert the line number to its first few characters and memorize it to avoid editing the wrong line even if the number changes.
- Do not delete or edit Tasks.md without permission. Modifications are permitted, but deletion of history is not allowed.
- When editing `./Tasks.md`, prefer append-only updates (add new lines) over modifying existing lines.
- Never “fix” a patch mismatch by replacing large blocks of `./Tasks.md` (large replacements are effectively shown as delete + re-add in diffs).
- For `./Tasks.md` edits, always target by anchor text (a distinctive existing line) and keep the patch hunk minimal.
- Before applying a patch to `./Tasks.md`, re-read the exact surrounding lines and ensure whitespace matches exactly (tabs, full-width spaces, and trailing spaces).
- Do not normalize or reformat `./Tasks.md` (no whitespace cleanup, no line wrapping, no line-ending changes).
- Preserve Markdown forced line breaks (two trailing spaces) exactly as-is.

## 1. Language Policy
- Chat responses: Japanese (code symbols, file paths, commands, and identifiers remain in English).
- `./Tasks.md`: Descriptions, notes, and checklists are in Japanese. AI creates them and gets my approval. Keep the following in English:
  - Commands, paths, filenames, identifiers, and checklist check numbers (e.g., AC-M0-**).
- `./docs/prompts/**.md`: English (as these are instruction files)

## 2. Markdown Formatting Rules (Important)
- To force a line break within a paragraph or list item, add **two spaces** at the end of the line (Markdown forced line break).
- Prioritize readable structure:
  - Use headings and lists over long paragraphs.
  - Keep AC lines like `AC-M0-01:` to **one item per line**, splitting long sentences with forced line breaks if necessary.
- Avoid “overly long lines” that make review difficult.

## 3. Checklist Format (`./Tasks.md`)
When asking users to verify something, format it as a checklist item:
- Start text with `[]` immediately after the list marker.
  - Example: `- [] Verify the window icon appears in the title bar.`
- Users replace as follows:
  - If OK: `[✅]`
  - If NG: Add `[✖]` and describe the reason and symptoms on a new line starting with `⇒`.
- In the next revision, always:
  - Leave the user's `⇒ ...` line unchanged.
  - On the next line, describe the fix in Japanese starting with `→`.
    - Example:
      - `[✖] ...`
      - `⇒ The icon is not applied to the Windows taskbar.`
      - `→ アイコン参照先を ./images/icon.ico に修正し、生成手順を更新しました。`
      - `⇒ OK`
      and change `[✖]` to `[✅]`