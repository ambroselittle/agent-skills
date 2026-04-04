# Personal Preferences — ambroselittle

## Parallel Sessions

- If a message seems unrelated to the current task or project context, confirm before acting -- the
  user runs many parallel sessions and may have pasted into the wrong one. A quick "This seems
  unrelated to [current work] -- intended for this session?" saves wasted effort.

## Clipboard for Runnable Commands

- When giving the user a command to run (especially multi-line or long commands), **pipe it to
  `pbcopy`** so it's on their clipboard. Then say something like "Copied to your clipboard — paste
  in a terminal to run."
- Terminal output mangles copy-paste — newlines, prompts, and formatting all break. `pbcopy` avoids this.
- This applies to: install commands, verification commands, URLs, file paths the user needs to
  navigate to — anything the user will need to copy from your output and use elsewhere.

## General Standards

- Analyze before acting -- consider multiple approaches and explain your choice
- If uncertain about a requirement, ask user rather than assuming
- Closely follow repo-specific standards -- they may override these general ones
- Your work should be provable/testable -- design for that and write thorough tests, following repo guidelines
- **When reporting timestamps** -- always include the timezone identifier (e.g. `18:05 UTC`, `2:05 PM EDT`). Never show a bare time.
