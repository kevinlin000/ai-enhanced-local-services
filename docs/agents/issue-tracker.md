# Issue tracker: Local Markdown

Issues and PRDs for this repo live as markdown files in `.scratch/`.

This project may be used for school/demo/interview work, so agent-generated planning artifacts should stay local by default. Do not create GitHub issues, PR comments, or other externally visible tracker entries unless the user explicitly asks for that exact action.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The PRD is `.scratch/<feature-slug>/PRD.md`
- Implementation issues are `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is recorded as a `Status:` line near the top of each issue file; see `triage-labels.md`
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/`, creating the directory if needed.

## When a skill says "fetch the relevant ticket"

Read the referenced markdown file. The user will normally pass the path or issue number directly.
