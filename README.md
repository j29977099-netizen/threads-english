# Threads: «Английский по-американски»

Content and publishing system for an English tutor's Threads account. Claude plans and writes posts. GitHub Actions hands each one to Zernio (zernio.com, free for one account) up to 30 hours ahead with its exact time, and Zernio publishes it on the minute with its own Meta-approved app. GitHub's cron often runs only every few hours, so the timing never depends on it. Everything runs even when nobody's computer is on.

```
Claude cloud routine (weekly)          GitHub repo                      GitHub Actions (every 15 min)
  reads strategy + calendar + log  ─▶  content/queue/*.json   ─▶  tools/publish.py ─▶ Zernio ─▶ Threads
  writes posts, renders cards,         media/*.png (public URLs)       appends log/publications.jsonl
  runs QC, commits                     log/, reports/                  opens an issue on any failure
                                                                  Weekly: collect metrics
```

The Zernio API key lives only in GitHub Secrets. Claude never sees it, and the routine doesn't need it.

**Two publishing routes** (`PUBLISH_BACKEND`, a repository variable): `zernio` (default) needs no Meta developer account but can't post polls or reply under a post, so quizzes take answers in the comments and reveals are their own posts. `threads` uses Meta's Threads API directly with your own app and token, and adds native polls and reveals as replies. `tools/qc.py` rejects anything the active route can't post.

**Instagram** runs through the same publisher (`--platform instagram`) with its own queue and log. It needs the Instagram account connected in Zernio too (still free: up to 2 accounts).

## Layout

| Path | What it is |
|---|---|
| `strategy/STRATEGY.md` | Positioning, voice, series, mix, schedule, visual identity, QC rules. Source of truth |
| `strategy/calendar-30d.json` | Rolling 30-day plan |
| `strategy/ROUTINE.md` | What the weekly Claude cloud routine does: report, fill the queue, check, push |
| `strategy/COMMENTS.md` | What the 3×/day comment routine does: reply, escalate or skip each new comment |
| `brand/` | Colours, fonts, and the profile picture (`avatar.json` → `avatar.png`) |
| `content/queue/*.json` | Scheduled Threads posts (UTC `publish_at`), including answer reveals |
| `content/instagram/*.json` | Scheduled Instagram posts: captions plus 1–10 JPEG slides (`images`, `alt_text` lists) |
| `content/cards/*.json` | Specs for graphics; `tools/render_cards.py` turns them into `media/*.png` |
| `log/publications.jsonl`, `log/instagram.jsonl` | Append-only record of every publish attempt, retry, failure, skip, per platform |
| `log/comments.jsonl` | One decision per comment (replied, escalated, skipped): ids and our reply text, never what others wrote |
| `reports/` | Weekly metrics (`insights-*.json`) and the weekly report (`weekly-*.md`, emailed to you as a GitHub issue) |
| `tools/qc.py` | Mechanical checks: lengths, route limits, images, reveal linkage, duplicates |
| `tools/publish.py` | Publisher with duplicate guard, limited retries, stale-post skipping |
| `tools/comments.py` | Comment inbox, reply (with checks and a daily cap), escalate, skip |

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
python3 tools/publish.py --platform instagram --dry-run --now 2026-11-11T12:00:00Z
python3 -m unittest discover -s tests
```

Editing a queued post is fine until its time: the next run pushes the change to Zernio. Deleting a post from the queue after it has been handed to Zernio does not stop it; cancel it in Zernio's dashboard instead, and the next run records it as skipped.

When something fails, the publish workflow opens one GitHub issue per day with the run summary, so GitHub emails you. Nothing reports success unless Threads (directly or through Zernio) returned a published post id.
