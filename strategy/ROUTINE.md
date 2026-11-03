# Weekly content run

Instructions for the Claude cloud routine that keeps the queue filled. It runs every Monday at 07:00 UTC, after the metrics job (04:17 UTC). GitHub Actions does the publishing; this run never calls Zernio or Threads.

## 0. Set up

```bash
python -m pip install -q -r requirements.txt
```

Use `python -m pip`, not plain `pip`: in the cloud environment `pip` belongs to a different Python than `python`.

Today means the current UTC date (`date -u +%F`).

## 1. Read

- `strategy/STRATEGY.md`, all of it. It is the source of truth for voice, series, mix, rhythm, the QC list and what to escalate.
- `strategy/calendar-30d.json`
- every file in `content/queue/` and `content/cards/`
- `log/publications.jsonl`, to see what went out, what failed and what was skipped
- the newest `reports/insights-*.json`, if there is one

## 2. Weekly report

If the newest `reports/insights-YYYY-MM-DD.json` has no matching `reports/weekly-YYYY-MM-DD.md`, write one in English:

- posts published that week (from the log), with views, likes, comments and shares for each, plus totals
- follower count and change
- best and worst topics and formats
- anything that failed or was skipped, and why (from the log)
- three concrete changes for the coming week

Use only numbers from the files. Where there are none, say "no data yet". Never estimate. Apply the three changes to the posts you write in step 3.

## 3. Fill the queue

For every date from max(tomorrow, 2026-11-09) through today + 12 days that has no queued post other than a reveal, write that day's posts. Put them in one new file, `content/queue/<first date>_auto.json`, in the same format as the existing queue files.

- **Slots:** p1 at 06:00Z (engagement) and p2 at 16:00Z (education), following that date's calendar entry and STRATEGY.md's mix.
- **Reveals:** every `quiz` and `challenge` gets a reveal: `kind: "reveal"` with `reply_to` set to the quiz id. It goes out the next day at 06:15Z for a morning quiz, or 16:15Z for an evening one.
- **Publishing route (Zernio):** no `poll` field.
  - Quizzes list the options in the text as `A) … B) … C) … D) …`, ask for the letter in the comments, and set `answer` to the letter.
  - A reveal is its own post, not a reply. It restates the question, then gives `Правильно — <letter>) …` and the explanation.
- **Every post:** `topic_tag: "Английский язык"`. The id has the form `YYYY-MM-DD-p1-short-slug`, `YYYY-MM-DD-p2-…` or `YYYY-MM-DD-r-…`.
- **Mini-tasks:** a lesson or tip that asks readers to translate, fill in or answer something also gets a next-day reveal, the same way a quiz does.
- **Russian:** the teacher's own first-person past tense is masculine («прожил», «преподавал»). Forms for the reader stay neutral.
  - Address the reader as «ты» throughout, never «вы».
  - Prefer wording that needs no gender at all («самостоятельно», «как прошёл день»). Use a form like выбрал(а) only when nothing neutral fits.
  - Grammar must be correct: agreement («во 2-м и 3-м пунктах»), and no деепричастие without its own subject («Слушая, …» followed by «нужно …» is wrong).
- **Series markers:** use only the markers from STRATEGY.md §3. Questions to the audience use 🗣.
- **No promises the system can't keep:** comments are not read automatically yet, so never write that answers will be collected, turned into posts or replied to.
- **Examples:** don't reuse an example sentence that already appeared in the last 30 days.
- **No name:** posts never name the teacher. Use the first person or the brand «Английский по-американски».
- **Facts only:** never invent stories, students, results, testimonials, prices, discounts, free trials or vote counts. If a calendar topic needs a fact about the teacher that STRATEGY.md doesn't give, replace it with another topic from the same series.
- **English:** it must be correct, natural American English, and each quiz has exactly one defensible answer. If you are not sure an item is correct, choose a different item.
- **No repeats:** don't reuse a topic from the last 30 days of the queue or the log.
- **Graphics:** when the calendar entry has `"graphic": true` and a template fits (`quiz`, `versus`, `mistakes`):
  1. Add the spec to `content/cards/<same name as the queue file>.json`.
  2. Run `python tools/render_cards.py` on it.
  3. Open every PNG it produced and check the text.
  4. Set `image` and `alt_text` on the post.

  If no template fits, write a text post.
- **Calendar:** if it ends within 14 days of today, add the next 30 days to `strategy/calendar-30d.json`, with the same structure, series and mix.

Never edit or delete a post dated today or earlier, or any post that appears in the log.

## 4. Check

```bash
python tools/qc.py
python -m unittest discover -s tests
```

Both must pass. Fix your own posts until they do. If they still fail, don't push. End the run with a short description of the problem.

## 5. Publish to the repo

Commit only these paths:

- `content/queue/`
- `content/cards/`
- `media/`
- `strategy/calendar-30d.json`
- `reports/weekly-*.md`

Use a message such as `content: queue 2026-11-14..2026-11-21`, then run `git push origin HEAD:main`. If main moved, run `git pull --rebase origin main` and push again.

Never change `tools/`, `tests/`, `.github/`, `README.md`, `strategy/STRATEGY.md` or this file, and never touch the Threads or Instagram accounts. Anything that needs the teacher (see STRATEGY.md §9) goes in the weekly report under "For you", not in a post.
