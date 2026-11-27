# Weekly content run

Instructions for the Claude cloud routine that keeps the queue filled. It runs every Monday at 07:00 UTC, after the metrics job (04:17 UTC). GitHub Actions does the publishing; this run never calls Zernio or Threads.

## 0. Set up

```bash
python -m pip install -q -r requirements.txt
```

Use `python -m pip`, not plain `pip`: in the cloud environment `pip` belongs to a different Python than `python`.

The Instagram Reels (step 3b) need ffmpeg. If `ffmpeg -version` fails, install the pip package that ships one; the renderer finds it by itself:

```bash
python -m pip install -q imageio-ffmpeg
```

Today means the current UTC date (`date -u +%F`).

## 1. Read

- `strategy/STRATEGY.md`, all of it. It is the source of truth for voice, series, mix, rhythm, the QC list and what to escalate.
- `strategy/students.json`: all that the teacher has told about their own students. A post about them uses this file and nothing else (see **Students** in step 3)
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
- the situation series (💬 ➡️ 🛟 💪) next to the grammar quizzes (🧩 🔥 🇷🇺 → 🇺🇸): views and replies for each post. Report the numbers only; the teacher decides which series stay
- the week's 🎓 post about the teacher's students, if one went out: its views and replies. If the next ones would need a fact that `strategy/students.json` doesn't give, say under "For you" what the teacher could tell (one line)
- the work-and-life-in-the-US pillar and the posts with an image card (STRATEGY.md §4, market study of 2026-11-17): views and replies next to the rest of the week's posts. Numbers only; the teacher decides what stays
- the knowing-speaking posts and the starting-again post, if one went out (STRATEGY.md §4, learner study of 2026-11-17): views and replies next to the rest of the week's posts. Numbers only; the teacher decides what stays
- three concrete changes for the coming week

Use only numbers from the files. Where there are none, say "no data yet". Never estimate. Apply the three changes to the posts you write in step 3.

## 3. Fill the queue

For every date from max(tomorrow, 2026-11-09) through today + 12 days, write whichever of that day's two posts the queue lacks. A day has two posts and no others: the morning post at 06:00Z (p1) and the evening post at 16:00Z (p2). Whatever is queued at 06:00Z is that day's morning post and whatever is queued at 16:00Z is its evening post, whichever series or id it has; an answer posted as a reply is neither. A date that already has its morning post still needs its evening post, and the other way round. Never add a third post to a date: the teacher asked for fewer posts on 2026-11-12, after Threads removed one of the account's replies as spam (STRATEGY.md §5). Put them in one new file, `content/queue/<first date>_auto.json`, in the same format as the existing queue files.

- **Slots:** p1 at 06:00Z (engagement), following that date's calendar entry and STRATEGY.md's mix. p2 at 16:00Z is the one evening post, and it rotates: over a week one 🎓 post about the teacher's students (see **Students**), about three idioms (see **Idioms**), one or two «Как сказать по-английски» posts (see **Как сказать**), and the rest from the calendar's p2 entries (💪, a lesson, a mistakes card, a tip, at most one promo). Never the same series on two evenings in a row. Nothing goes out at 09:30Z or 18:00Z any more.
- **How the text looks:** STRATEGY.md §2 has the rule and the numbers behind it; read it before writing anything.
  - A line break ends the thought, so most lines have no period, and the last line never has one.
  - At most one pair of quotation marks and one long dash in a post, usually none. English needs no quotation marks. Two colons at most, no semicolons.
  - The series marker plus two emoji at most. Never ✔️ or • as bullets in front of examples.
  - Posts of one series don't share a skeleton: word the fixed parts differently each time, and don't close every post with a question and 👇.
  - `python tools/qc.py` refuses a post that breaks the countable parts. Reword the post; never work around the count with look-alike characters.
- **Pillar: English for work and life in the US** (STRATEGY.md §4, from 2026-11-17): in each week (Monday to Sunday) at least two posts are set at work or in daily life in the US, written in the existing series (☕️, ➡️, 🛟, 💪, a lesson): a call with a client, an email, small talk with colleagues, the bank, the doctor, the landlord, a parent meeting at school. They take the place of other topics, never extra posts. Hypothetical situations («Клиент звонит и…»), never a story about the teacher or a student, and only English you are sure Americans use there.
- **Images on Threads** (from 2026-11-17): one or two posts a week carry an image card. The week's 🎓 post gets a `phrase` card for its English phrase, and one lesson or 👀 mistakes post gets a fitting card. Add the spec to `content/cards/<same name as the queue file>.json`, save to `media/<date>-<slug>.png`, run `python tools/render_cards.py` on it, open the image and check every word, then set `image` and `alt_text` (Russian, including the phrase and the examples). See `content/cards/2026-11-18_students.json`. On the days of the Instagram 🎓 Reel, the Threads post can reuse the Reel's `phrase` slide spec as its card.
- **Hooks** (from 2026-11-17): a lesson or tip opens with one short line of a real situation before the rule, never a dry rule first. An idiom opens with the funny literal picture, then what it really means. A grammar post or quiz opens with the moment where the rule changes what you mean, never with the rule's name, and stays at A2 to B1: most learners who name their level are A0 to A2 (learner study, STRATEGY.md §4). A hook may use a phrase learners use about themselves, such as «с нуля», «понимаю, но не могу сказать», «начинать и бросать» or «стесняюсь говорить», never a quote from a real person's post.
- **The knowing-speaking gap** (STRATEGY.md §4, from 2026-11-17): in each week (Monday to Sunday) at least two posts in 🛟, ➡️, ☕️ or a lesson start from the moment the reader knows the words but can't get them out: the phone rings, a neighbour says «Hi, how are you?», a colleague asks something in a meeting. Give one or two short phrases that buy time or keep the talk going. They may be the pillar's posts; never extra posts. Hypothetical situations only, never a story about the teacher or a student.
- **Starting again** (from 2026-11-17): in every second week, one practical-advice post in a p2 entry speaks to people who start and quit: why it so often ends after a few days or weeks, and one small thing to do on a hard day. No blame, no «просто будь дисциплинированным», nothing about the teacher's own students or results.
- **Readers outside Russia** (from 2026-11-17): many readers live in Kazakhstan, Ukraine or abroad. Examples don't assume the reader lives in Russia or went to a Russian school.
- **Idioms (🗽 Идиома дня):** `kind: "lesson"`, `topic: "idiom: <idiom>"`, id `YYYY-MM-DD-i-short-slug`, in the 16:00Z slot. Follow the posts published from 2026-11-15 on in `content/queue/2026-11-11_idioms.json`; the earlier ones were written before the style rule:
  - `🗽 Идиома дня: <idiom>`, then one line with the literal translation and one with what it really means. Word these two lines differently from post to post («Дословно получается…», «Слово в слово это…», «А на деле…», «А по смыслу…»), without quotation marks.
  - Two examples: the English sentence on one line, its Russian translation on the next. No ✔️ and no dash in front.
  - At most one short plain-text note (a related phrase, British vs American, a grammar point). Then an open question, with or without 👇.
  - Pick idioms Americans really use in everyday speech, understandable at B1. No rude or dated ones.
  - Never repeat an idiom from the queue or the log, ever. Check `topic` and the text of every file.
  - The question is open (no right answer), so an idiom never gets a reveal.
- **Как сказать (Как сказать по-английски «…»):** `kind: "lesson"`, `topic: "how to say: <Russian phrase>"`, id `YYYY-MM-DD-s-short-slug`, in the 16:00Z slot, about every fourth evening. Follow the posts published from 2026-11-14 on in `content/queue/2026-11-11_how_to_say.json`:
  - `Как сказать по-английски: <Russian phrase>` and one emoji that fits the topic. No quotation marks. This series has no fixed marker.
  - Four lines, `<English> - <Russian>`, with a plain hyphen and no period, from the mildest way to say it to the strongest.
  - `И ловушка`, then one trap: a near-identical word, form or preposition that changes the meaning, each side joined to its Russian meaning by «это» or «значит». Close with one short line and 👀.
  - Pick a feeling or everyday situation that Russian names in one colloquial phrase and that learners tend to translate word for word. The English is what Americans actually say.
  - The trap must be a real, checkable difference in meaning, not a matter of taste. If you aren't sure of it, choose another phrase.
  - Write the Russian side so it needs no gender («мне лень», «у меня нет слов»), not «я устал(а)».
  - Never repeat a phrase or a trap from the queue or the log. There is no task, so no reveal.
- **Situation series (pilot since 2026-11-13; STRATEGY.md §3 and §4):** each week (Monday to Sunday) gets one post of each: 💬, ➡️ and 🛟 in p1 slots and 💪 in a p2 slot, on four different days, plus at most one ✏️ in a p2 slot.
  - They take the place of that day's calendar entry; they are never an extra post. Replace a grammar quiz (🧩, 🔥, 🇷🇺 → 🇺🇸) first, otherwise a vocabulary or tip entry. Never replace a holiday-tied or promo entry. Where the calendar already names one of these series for a date, write that topic.
  - Follow the posts published from 2026-11-14 on in `content/queue/2026-11-13_situations.json`.
  - 💬 Что он имел в виду?: `kind: "quiz"` with readings A–C and `answer` set to the most likely one. Its reply opens `✅ Чаще всего это <letter>) …`, then says what in the words points to that reading, what is only a guess, and gives one phrase to clarify.
  - ➡️ А дальше что? and 🛟 Спасаем разговор: `kind: "challenge"`. The situation, then an open task in your own words. The reply gives 2–3 natural lines and why they work.
  - 💪 Английский с характером: `kind: "lesson"`. The situation in one or two lines, then three ways, each under its own label line («Мягко», «Твёрдо», «С условием», no colon), one line of advice and an open 🗣 question. No reveal.
  - ✏️ Было → стало: `kind: "lesson"`. A flat but correct answer, the livelier one, and what changed. Call it a typical answer; never present it as a student's.
  - One recognisable everyday situation per post: work, friends, a shop, texting. It is hypothetical («Коллега просит…»), never a story about the teacher or a student.
  - What a phrase usually means differs between people. Write «часто» or «чаще всего», never «всегда», and only what you are sure Americans say and mean. If you aren't sure, choose another situation.
  - `topic` starts with the series: "what did they mean: …", "what next: …", "conversation rescue: …", "english with a backbone: …", "before and after: …".
- **Students (🎓 Мои ученики; STRATEGY.md §1 and §3):** one post a week, added 2026-11-16 at the teacher's request. `kind: "lesson"`, in the 16:00Z slot, id `YYYY-MM-DD-p2-students-<group>`. Posts are already queued through 2026-12-23; write one for each later week whose evenings have none.
  - `topic` is exactly `students: <group>`, with a key from `strategy/students.json`, or `students: all` for a post about several groups at once. Take the groups in turn, and never the same group twice within four weeks.
  - Say about the students only what the file gives for that group, in your own words. Add nothing: no name, age, job, city, level, exam score, result, quote or length of time that is not there. Always several students («несколько моих учеников», «кто-то из учеников»), never one person's story, and nothing about all of the teacher's students at once («все», «никто», «каждый»).
  - What the file gives under `all` holds for the students as a whole, in the teacher's own measure («большинство моих учеников со мной уже больше четырёх лет»). Any 🎓 post may say it in that measure; never turn it into a fact about one group, and never make «большинство» into «все».
  - Follow the posts in `content/queue/2026-11-18_students.json`: the marker and a title, two or three lines about the group, then something for the reader that needs no new fact: one English phrase that fits, what it means and an example sentence that is plainly not about a student, or a thought about learning. Then an open 🗣 question. No task, so no reveal.
  - It is not a promo: no invitation to write, and nothing about lessons, prices or what the reader would achieve. Never on the evening before or after the promo.
  - Don't repeat a phrase or an angle from an earlier 🎓 post. When a post would need a fact the file doesn't give, don't write it: give that evening to another series and say so under "For you" in the weekly report.
  - `python tools/qc.py` refuses a post that speaks of the teacher's students without this `topic`, that carries a number the group's facts don't give or any quotation marks, or that speaks of one student. The rest is yours to check: read the finished post against the file, line by line.
- **Reveals:** every `quiz` and `challenge` gets a reveal: `kind: "reveal"` with `reply_to` set to the quiz id. It goes out the next day at 06:15Z for a morning quiz, or 16:15Z for an evening one.
- **Publishing route (Zernio):** no `poll` field.
  - Quizzes list the options in the text as `A) … B) … C) … D) …`, ask for the letter in the comments, and set `answer` to the letter.
  - A reveal goes out as a reply right under its quiz, so it doesn't restate the question. It opens with `✅ Правильно <letter>) …`, then gives the explanation.
- **Every post:** `topic_tag: "Английский язык"`. The id has the form `YYYY-MM-DD-p1-short-slug`, `YYYY-MM-DD-p2-…`, `YYYY-MM-DD-i-…`, `YYYY-MM-DD-s-…` or `YYYY-MM-DD-r-…`.
- **Mini-tasks:** a lesson or tip that asks readers to translate, fill in or answer something also gets a next-day reveal, the same way a quiz does.
- **Russian:** the teacher's own first-person past tense is masculine («прожил», «преподавал»). Forms for the reader stay neutral.
  - Address the reader as «ты» throughout, never «вы».
  - Prefer wording that needs no gender at all («самостоятельно», «как прошёл день»). Use a form like выбрал(а) only when nothing neutral fits.
  - Grammar must be correct: agreement («во 2-м и 3-м пунктах»), and no деепричастие without its own subject («Слушая, …» followed by «нужно …» is wrong).
- **Series markers:** use only the markers from STRATEGY.md §3. Questions to the audience use 🗣.
- **No promises the system can't keep:** comments are not read automatically yet, so never write that answers will be collected, turned into posts or replied to.
- **Direct messages:** only the week's one promo post mentions writing to the teacher, once and in passing («Если думаешь про занятия, напиши мне»). No other post invites anyone to write (STRATEGY.md §7).
- **Examples:** don't reuse an example sentence that already appeared in the last 30 days.
- **No name:** posts never name the teacher. Use the first person or the brand «Английский по-американски».
- **Facts only:** never invent stories, students, results, testimonials, prices, discounts, free trials or vote counts. If a calendar topic needs a fact about the teacher that STRATEGY.md doesn't give, replace it with another topic from the same series. What the teacher has told about their students is in `strategy/students.json`; only a 🎓 post uses it (see **Students**), and no other post speaks of the teacher's students.
- **English:** it must be correct, natural American English, and each quiz has exactly one defensible answer. If you are not sure an item is correct, choose a different item.
- **No repeats:** don't reuse a topic from the last 30 days of the queue or the log.
- **Graphics:** when the calendar entry has `"graphic": true` and a template fits (`quiz`, `versus`, `mistakes`):
  1. Add the spec to `content/cards/<same name as the queue file>.json`.
  2. Run `python tools/render_cards.py` on it.
  3. Open every PNG it produced and check the text.
  4. Set `image` and `alt_text` on the post.

  If no template fits, write a text post.
- **Calendar:** if it ends within 14 days of today, add the next 30 days to `strategy/calendar-30d.json`, with the same structure, series and mix, with the situation series planned in at the rate above and one 🎓 post a week in a p2 entry.

Never edit or delete a post dated today or earlier, or any post that appears in the log. Posts up to 30 hours ahead may already be scheduled in Zernio: editing one is fine (the publisher pushes the change), but removing it from the queue does not stop it.

## 3b. Instagram

For every date from tomorrow through today + 12 days that has no post in `content/instagram/`, write one Instagram post at 15:00Z (18:00 MSK). Check these dates on their own, not against the Threads queue: Instagram can have empty days where Threads is already filled. Put them in `content/instagram/<first date>_auto.json`, in the same format as the files already there. Adapt the day's best Threads post (usually the morning quiz) rather than copying it, and follow STRATEGY.md §12.

- **Reels (from 2026-11-28):** every post is a Reel, and the answer comes on a later slide of it, never in a next-day post. Write the slides as card specs, as before, inside one spec per post in `content/cards/ig-<first date>.json`: `{"template": "reel", "out": "media/ig/<date>-<slug>.mp4", "slides": [<card spec>, <card spec>]}`, with no `out` on the slides. Run `python tools/render_cards.py` on the file. It writes the video and its cover (`media/ig/<date>-<slug>-cover.jpg`) and prints where it put a preview sheet: the cover, then the end of each slide. See `content/cards/ig-2026-11-29.json`.
  - The first slide of a Reel with more slides counts down to the next on its prompt line (`prompt` on `quiz` and `chat`, `cta` on `list`): Ответ через 7 … 1, and the cover shows Ответ в конце ролика there. The renderer writes that line, so leave it out of the spec. For other words set `countdown` (the words before the number) and `cover_prompt` on the reel spec, as the 🎓 Reels do.
  - A video has no slides to swipe: no Листай, слайд or свайп anywhere. The renderer refuses them on the slides, and `tools/qc.py` in the caption.
  - A quiz: slide 1 uses `quiz`, slide 2 uses `answer`.
  - A phrase or lesson: use `phrase` and/or `list` (1–3 slides), or `versus` / `mistakes` alone.
  - A situation post (💬 ➡️ 🛟 💪): slide 1 uses `chat`: the exchange as `messages` (`{"from": "them" or "me", "text": …}`, or `{"from": "me", "typing": true}` where the reader has to answer) and the `question`. Slide 2 gives the answer with `answer`, `list`, or `versus` with its own `top_tag` and `bottom_tag`. See `content/cards/ig-2026-11-17.json`.
  - A day with a 🎓 post (**Students** in step 3): adapt that post instead of the morning one. Slide 1 uses `list` with the label «МОИ УЧЕНИКИ»: a title and two or three short points that say who the students are and why they study. Slide 2 uses `phrase` with the post's English phrase. On the reel spec set `"countdown": "По-английски через"` and `"cover_prompt": "Как это по-английски, в конце ролика"`. The caption tells the same story in other words. Slides, caption and `alt_text` say about the students only what the Threads post says, and `topic` is exactly the same `students: <group>`, with nothing after it. See `content/instagram/2026-12-02_students.json` and `content/cards/ig-2026-12-02-students.json`; the Reels for 2, 10, 17 and 23 December are already queued.
  - **Photos (from 2026-11-17):** when `brand/photos/index.json` has a photo that fits the carousel's situation (the same kind of place and moment: an invitation in a café, an offer at dinner, small talk at work), put it on every slide of that Reel: add `"photo"` (its `file`) and, when the people sit off-centre, `"focus"` ([x, y], 0 to 1). On a photo a quiz takes `"situation"` (one line: who says what, where), `"bubble"` (the English phrase; a `\n` sets the line break) and `"question"`, and keeps `options` and `prompt`; the other templates keep their fields. One photo goes on at most one post in 7 days. A Reel never takes a photo whose index entry says `"ai_generated": true` (Meta wants AI-made video labelled; the renderer refuses it). A 🎓 Reel takes only a photo whose index entry says `"people": false` (people in a photo would read as the students themselves). When no photo fits, keep the gradient slides and say in the weekly report which scene was missing, so the teacher can add a photo. See the 21–23 Nov carousels in `content/cards/ig-2026-11-21.json`.
  - Open the preview sheet and check every word. The renderer refuses a card whose text doesn't fit: shorten the sentence or the options.
- **Caption:** at most 2,200 characters, in the same Russian rules as Threads, and written the same way (**How the text looks** above; `tools/qc.py` checks captions too).
  - Start with a hook line.
  - Say where the answer is («Ответ в конце ролика 👀»), give one useful sentence of explanation, and ask one question for the comments.
  - End with 4–6 hashtags from STRATEGY.md §12, on a line of their own.
- **Fields:** `video` and `cover` are the paths the renderer wrote. `alt_text` is a list with one Russian description per slide, and the answer slide's description contains the answer: Instagram has no alt text for Reels, but QC reads it. Ids look like `ig-YYYY-MM-DD-slug`. There is no `topic_tag`, `poll` or `reply_to`.

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

Never change `tools/`, `tests/`, `.github/`, `README.md`, `strategy/STRATEGY.md`, `strategy/students.json` or this file, and never touch the Threads or Instagram accounts. Anything that needs the teacher (see STRATEGY.md §9) goes in the weekly report under "For you", not in a post.
