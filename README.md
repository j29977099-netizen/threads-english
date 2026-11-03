# Threads: «Английский по-американски»

Content and publishing system for an English tutor's Threads account. Claude plans and writes posts; GitHub Actions publishes them through Zernio (zernio.com, free for one account), which posts with its own Meta-approved app. Everything runs even when nobody's computer is on.

```
Claude cloud routine (weekly)          GitHub repo                      GitHub Actions (every 15 min)
  reads strategy + calendar + log  ─▶  content/queue/*.json   ─▶  tools/publish.py ─▶ Zernio ─▶ Threads
  writes posts, renders cards,         media/*.png (public URLs)       appends log/publications.jsonl
  runs QC, commits                     log/, reports/                  opens an issue on any failure
                                                                  Weekly: collect metrics
```

The Zernio API key lives only in GitHub Secrets. Claude never sees it, and the routine doesn't need it.

**Two publishing routes** (`PUBLISH_BACKEND`, a repository variable): `zernio` (default) needs no Meta developer account but can't post polls or reply under a post, so quizzes take answers in the comments and reveals are their own posts. `threads` uses Meta's Threads API directly with your own app and token, and adds native polls and reveals as replies. `tools/qc.py` rejects anything the active route can't post.

## Layout

| Path | What it is |
|---|---|
| `strategy/STRATEGY.md` | Positioning, voice, series, mix, schedule, visual identity, QC rules. Source of truth |
| `strategy/calendar-30d.json` | Rolling 30-day plan |
| `strategy/ROUTINE.md` | What the weekly Claude cloud routine does: report, fill the queue, check, push |
| `brand/` | Colours, fonts, and the profile picture (`avatar.json` → `avatar.png`) |
| `content/queue/*.json` | Scheduled posts (UTC `publish_at`), including answer reveals |
| `content/cards/*.json` | Specs for graphics; `tools/render_cards.py` turns them into `media/*.png` |
| `log/publications.jsonl` | Append-only record of every publish attempt, retry, failure, skip |
| `reports/` | Weekly metrics (`insights-*.json`) and the weekly report (`weekly-*.md`, emailed to you as a GitHub issue) |
| `tools/qc.py` | Mechanical checks: lengths, route limits, images, reveal linkage, duplicates |
| `tools/publish.py` | Publisher with duplicate guard, limited retries, stale-post skipping |

## Post format

```json
{
  "id": "2026-11-09-p1-look-forward-to",
  "publish_at": "2026-11-09T06:00:00Z",
  "kind": "quiz",
  "text": "…≤ 500 characters, options A) … D) in the text…",
  "answer": "B",
  "topic_tag": "Английский язык"
}
```

`kind` is one of intro, quiz, challenge, lesson, tip, promo, reveal, reply. A `reveal` has `reply_to` (the quiz id), must mention the quiz's `answer`, and goes out only after its quiz is published. On the `zernio` route it is a standalone post, so it restates the question. Image posts have `image` and `alt_text`. `poll` and `kind: reply` work only on the `threads` route.

## One-time setup (owner)

1. **Instagram as a Creator account.** Zernio connects Threads through the Instagram account that owns it, and its docs require a Business or Creator account. Switching is free and reversible (Instagram → Settings → Account type and tools).
2. **Zernio.** Sign up at zernio.com (free for 1–2 connected accounts, no card). Connect Threads and approve Meta's screen. You can revoke it any time in Threads → Settings → Account → Website permissions. Then create an API key at zernio.com/dashboard/api-keys. It is shown once.
3. **GitHub.** Run `gh auth login` in your own terminal. Create a public repository from this folder (public, because Threads fetches images from public URLs).
4. **Secret.** Paste it yourself; never send keys in chat:
   ```
   gh secret set ZERNIO_API_KEY
   ```
5. **Test.** Actions → *Publish to Threads* → Run workflow with *dry run* ticked. Then let the schedule take over.
6. **Claude routines.** Connect the repo to Claude Code on the web, and Claude creates the weekly content routine.

To use the `threads` route instead, create a Meta app with the *Access the Threads API* use case (this needs a verified Meta developer account). Add your account as a Threads Tester, then store a long-lived token with `gh secret set THREADS_ACCESS_TOKEN`. Add `gh secret set GH_SECRETS_PAT` for the weekly refresh, and set the repository variable `PUBLISH_BACKEND` to `threads`.

## Operating

```bash
python3 tools/render_cards.py content/cards/<file>.json
python3 tools/qc.py
python3 tools/publish.py --dry-run --now 2026-11-09T06:05:00Z
python3 -m unittest discover -s tests
```

When something fails, the publish workflow opens one GitHub issue per day with the run summary, so GitHub emails you. Nothing reports success unless Threads (directly or through Zernio) returned a published post id.
