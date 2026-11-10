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

For every date from max(tomorrow, 2026-11-09) through today + 12 days that has no queued p1 or p2 post (reveals and idioms don't count), write that day's posts. Also give every date in that range that has no idiom one. Put them in one new file, `content/queue/<first date>_auto.json`, in the same format as the existing queue files.

- **Slots:** p1 at 06:00Z (engagement) and p2 at 16:00Z (education), following that date's calendar entry and STRATEGY.md's mix. Every day also gets an idiom at 09:30Z (see **Idioms**).
- **Idioms (🗽 Идиома дня):** `kind: "lesson"`, `topic: "idiom: <idiom>"`, id `YYYY-MM-DD-i-short-slug`. Follow the format of the posts in `content/queue/2026-11-11_idioms.json`:
  - `🗽 Идиома дня: <idiom>`, then «Дословно — «…».» and «На самом деле — …».
  - Two examples, each `✔️ <English>` with its Russian translation on the next line after «— ».
  - At most one short plain-text note (a related phrase, British vs American, a grammar point). Then an open question with 👇.
  - Pick idioms Americans really use in everyday speech, understandable at B1. No rude or dated ones.
  - Never repeat an idiom from the queue or the log, ever. Check `topic` and the text of every file.
  - The question is open (no right answer), so an idiom never gets a reveal.
- **Reveals:** every `quiz` and `challenge` gets a reveal: `kind: "reveal"` with `reply_to` set to the quiz id. It goes out the next day at 06:15Z for a morning quiz, or 16:15Z for an evening one.
- **Publishing route (Zernio):** no `poll` field.
  - Quizzes list the options in the text as `A) … B) … C) … D) …`, ask for the letter in the comments, and set `answer` to the letter.
  - A reveal goes out as a reply right under its quiz, so it doesn't restate the question. It opens with `✅ Разбор: правильно — <letter>) …`, then gives the explanation.
- **Every post:** `topic_tag: "Английский язык"`. The id has the form `YYYY-MM-DD-p1-short-slug`, `YYYY-MM-DD-p2-…`, `YYYY-MM-DD-i-…` or `YYYY-MM-DD-r-…`.
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

Never edit or delete a post dated today or earlier, or any post that appears in the log. Posts up to 30 hours ahead may already be scheduled in Zernio: editing one is fine (the publisher pushes the change), but removing it from the queue does not stop it.

## 3b. Instagram

For the same dates, write one Instagram post per day at 15:00Z (18:00 MSK). Put them in `content/instagram/<first date>_auto.json`, in the same format as the files already there. Adapt the day's best Threads post (usually the morning quiz) rather than copying it, and follow STRATEGY.md §12.

- **Slides:** every post is images, and the answer goes on a later slide, never in a next-day post. Add the specs to `content/cards/ig-<first date>.json`, saving to `media/ig/<date>-<slug>-<n>.jpg` (JPEG only), and run `python tools/render_cards.py` on it.
  - A quiz: slide 1 uses `quiz` with prompt «Листай → ответ на следующем слайде»; slide 2 uses `answer`.
  - A phrase or lesson: use `phrase` and/or `list` (2–3 slides), or `versus` / `mistakes` for a single image.
  - Open every slide and check the text. The renderer refuses a quiz that is too long for one card: shorten the sentence or the options.
- **Caption:** at most 2,200 characters, in the same Russian rules as Threads.
  - Start with a hook line.
  - Say where the answer is («Листай — ответ на втором слайде 👉»), give one useful sentence of explanation, and ask one question for the comments.
  - End with 4–6 hashtags from STRATEGY.md §12.
- **Fields:** `images` and `alt_text` are lists, with one Russian description per slide, and the answer slide's description contains the answer. Ids look like `ig-YYYY-MM-DD-slug`. There is no `topic_tag`, `poll` or `reply_to`.

## 4. Check

```bash
python tools/qc.py
python -m unittest discover -s tests
```

Both must pass. Fix your own posts until they do. If they still fail, don't push. End the run with a short description of the problem.

## 5. Publish to the repo

Commit only these paths:

- `content/queue/`
- `content/instagram/`
- `content/cards/`
- `media/`
- `strategy/calendar-30d.json`
- `reports/weekly-*.md`

Use a message such as `content: queue 2026-11-14..2026-11-21`, then run `git push origin HEAD:main`. If main moved, run `git pull --rebase origin main` and push again.

Never change `tools/`, `tests/`, `.github/`, `README.md`, `strategy/STRATEGY.md` or this file, and never touch the Threads or Instagram accounts. Anything that needs the teacher (see STRATEGY.md §9) goes in the weekly report under "For you", not in a post.
