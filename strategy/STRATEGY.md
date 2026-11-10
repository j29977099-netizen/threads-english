# Threads strategy: «Английский по-американски»

This file is the source of truth for everyone (human or agent) who plans, writes, or publishes posts for this account. Read it before generating any content.

## 1. Positioning

**Brand name (working):** Английский по-американски
**Promise:** Английский, на котором реально говорят в США. Не учебник, а живая речь.
**Who it's for:** Russian-speaking adults. Beginners who are afraid to speak, intermediate learners stuck at "I understand but can't talk", professionals who need English at work, people moving to or travelling in the US.

**What makes the teacher different (facts only, never embellish):**
- Teaching English online since 2016
- Lived in the United States for over 15 years
- Specialises in conversational and American English, pronunciation, grammar, Business English, vocabulary, and the typical mistakes of Russian speakers
- Teaches one-on-one online on ProgressMe

Never invent personal stories, students, results, testimonials, prices, discounts, or free trials. If a post needs one of these, it waits for the teacher to supply it. The same goes for vote counts and poll percentages: quote them only from `reports/`, never from expectation.

## 2. Voice

- A real teacher talking to real students: friendly, confident, practical, sometimes funny.
- Russian explanations, English examples. Increase the share of English slowly over months.
- Short lines, lots of white space. One idea per post.
- Address the reader as «ты». Use gender-neutral forms for the reader: выбрал(а), делал(а).
- The teacher's own first-person past-tense verbs are masculine (confirmed 2026-11-03): «прожил», «преподавал». The reader-facing forms stay neutral (выбрал(а)). Personal facts stay limited to those in §1.
- Posts never name the teacher (decided 2026-11-03). Write in the first person («Преподаю…») or under the brand «Английский по-американски»; the profile name field is enough.
- Avoid: generic motivation quotes, «В современном мире...», «Давайте разберёмся», «Это не просто X, это Y», piles of hashtags, more than 4 emojis in a block of text, any unnatural English.

## 3. Recurring series (rubrics)

| Marker | Series | Format |
|---|---|---|
| 🧩 | Проверь себя | Fill-in-the-blank or grammar quiz with lettered options A–D; answers go in the comments |
| 🔥 | Только одно правильное | Choose the one correct sentence; realistic Russian-speaker mistakes as distractors |
| 📚 vs 🇺🇸 | Учебник vs Америка | Textbook phrase vs what Americans actually say |
| 📌 | Выражение дня | Word or expression: meaning, pronunciation, translation, 2 examples, mini-task |
| 🇷🇺 → 🇺🇸 | Переведи | Translation challenge, natural answer revealed the next day |
| ☕️ | Как говорят в США | Real-life situations: café, airport, office, interview, texting, TV |
| 👀 | Ошибки, которые нас выдают | Common mistakes of Russian speakers, often as a graphic |
| 🗽 | Идиома дня | An everyday American idiom: its literal translation (often funny), what it really means in Russian, 2 natural examples with translations, at most one short note on usage, and an open question for the comments. No task with a right answer, so no reveal. Added 2026-11-10 at the teacher's request |
| «…» | Как сказать по-английски | A feeling or everyday situation that Russian names in one colloquial phrase («я загоняюсь», «мне лень»). Opens with «Как сказать по-английски «…»» and one emoji that fits the topic; the series has no fixed marker. Then 4 natural American ways to say it, from mild to strong, each with its Russian translation. Then «И ловушка:», one trap where a near-identical word, form or preposition changes the meaning, and a short closing line with 👀. No task, so no reveal. Every third day. Added 2026-11-10 at the teacher's request |
| ✅ | Разбор | Answer reveal the next day, posted as a reply right under its quiz |
| 👋 | О занятиях | Soft promotion of private lessons |

## 4. Content mix (of all non-reveal posts)

- 35% interactive quizzes and exercises
- 25% vocabulary and American English
- 20% grammar and common mistakes
- 10% practical learning advice
- 10% personal brand and student acquisition (1–2 posts per week, never two days in a row)

The daily 🗽 idiom and the «Как сказать по-английски» post have their own slots (§5) and don't count toward this mix.

## 5. Daily rhythm

All times Moscow time (UTC+3), the centre of gravity for a Russian-speaking audience spread across Russia, Europe, Israel, Kazakhstan, and the US.

| Slot | Time (MSK) | UTC | Post |
|---|---|---|---|
| Post 1 | 09:00 | 06:00 | Engagement: quiz, challenge, translation, question to the audience |
| Reveal | 09:15 next day | 06:15 | ✅ reveal of yesterday's morning quiz, after a full day of comments |
| Idiom | 12:30 | 09:30 | 🗽 Идиома дня, every day |
| Post 2 | 19:00 | 16:00 | Education: vocabulary, grammar, American English, tip, or promo |
| Reveal | 19:15 next day | 16:15 | ✅ reveal of an evening quiz or mini-task, if there was one |
| Phrases | 21:00 | 18:00 | «Как сказать по-английски «…»», every third day |

**Publishing route.** Posts go out through Zernio, which needs no Meta developer account. Each post is handed to Zernio up to 30 hours ahead with its exact time, so it publishes on the minute. Zernio cannot post polls, so quizzes collect answers in the comments. A reveal is replied under its quiz through Zernio's inbox, which can't schedule, so the "Threads answer reveals" cloud routine posts it at 06:15 and 16:15 UTC; GitHub runs post it only if the routine hasn't within 45 minutes. If a Meta developer app is set up later, setting the repository variable `PUBLISH_BACKEND=threads` brings back native polls and reveals as replies.

From week 3, test 07:30 MSK against 09:00 for Post 1 and keep what wins. 12:30 MSK is the idiom slot and 21:00 MSK is the «Как сказать» slot.

Answer reveals are always replies to their own quiz (`reply_to`), so the explanation stays attached to the question. The original quiz never contains the answer.

## 6. Visual identity

- **Palette:** Ink navy `#13213C` · Paper `#FBF8F1` · Liberty red `#E4483F` (accent, wrong answers) · Teal `#1F8A70` (correct answers) · Sun `#FFC857` (highlight) · Mist `#E9EEF5` (panels)
- **Type:** Inter (SIL OFL), bundled in `brand/fonts/`. ExtraBold for headlines, SemiBold for English examples, Medium for Russian explanations.
- **Format:** 1080×1350 (4:5 portrait), 72 px margins, no more than ~40 words per card.
- **Card frame:** series label at the top left, wordmark «Английский по-американски» at the bottom, a thin red–navy stripe across the bottom edge.
- **Templates:** quiz card, textbook-vs-America card, mistakes list, vocabulary flashcard, comparison chart, mini-dialogue.
- **Rules:** no stock photos, no copyrighted images, no emoji inside graphics (they render inconsistently), every English and Russian word on a card is checked before publishing.

## 7. Growth and conversion

- Bio and the pinned intro post (`2026-11-09-intro`) tell a new visitor in 5 seconds who this is and how to book.
- Every quiz invites a comment ("почему именно этот вариант?"), because replies drive Threads distribution more than likes.
- Reply to genuine comments within the day: thank, encourage, explain. Never spoil a quiz before its reveal.
- 1–2 soft promotional posts per week. The call to action is a DM: «Напиши мне в личные сообщения — расскажу про занятия».
- No follow-for-follow, no bought engagement, no unsolicited DMs, no mass commenting on other accounts.
- Lesson inquiries arrive as DMs, which the Threads API cannot read. The teacher handles DMs personally.

## 8. Quality control (every post, before it enters the queue)

1. Grammar and vocabulary are correct, and the English is natural American English.
2. A quiz has exactly one defensible correct answer. Avoid items where context could make a distractor correct.
3. Distractors are plausible mistakes a Russian speaker would actually make.
4. Russian text is correct: spelling, «ё» where it matters, punctuation, «» quotes, тире.
5. The explanation is understandable to a B1 learner.
6. Card text is readable at phone size and identical to what was checked.
7. The topic hasn't been used in the last 30 days (check `log/publications.jsonl` and the queue).
8. Text ≤ 500 characters, at most 5 links, one topic tag (and poll options ≤ 25 characters on the threads route).
9. There is a clear engagement prompt where appropriate.
10. The reveal answers the same question, with the same options and letters, as its quiz.

`tools/qc.py` checks 6–8 and 10 mechanically. Items 1–5 and 9 need judgement.

## 9. Escalate to the teacher (do not answer)

Questions about prices, schedules, refunds, or personal details; complaints; anything political, religious, or about sanctions and payments; harassment; press or partnership offers; anything the teacher would want to see personally.

## 10. Weekly metrics

Posts published, views, likes, replies, reposts, quotes, shares, follower growth, best topics, best quiz formats, best time slot, lesson inquiries (reported by the teacher), and three concrete changes for next week.

## 11. Account baseline (2026-11-03)

| Item | State |
|---|---|
| Handle | `@esl_teacher_bro`, shared with Instagram (renaming it renames Instagram too). On every card footer via `brand/brand.json` |
| Threads profile | Name «Johnathan», bio option A, public |
| Instagram | Creator account, category «Tutor/Teacher», tutor bio, Threads badge on |
| Profile picture | `brand/avatar.png` (EN speech bubble); a real photo can replace it any time |
| Starting point | 0 followers, no posts: no history to learn from |

**Cold-start rules (first 4 weeks):**
- Launch day opens with the intro post `2026-11-09-intro`, pinned once it is live.
- Expect few answers at first. Reveals explain the answer; they never claim how people answered.
- Every post keeps the topic tag «Английский язык», the main way a 0-follower account is found.
- Growth comes from the content and from the teacher's own genuine replies in English-learning conversations. No automated replies on other people's posts.
- Judge formats on views and replies per post, not on follower count, until the account has about 100 followers.

## 12. Instagram (@esl_teacher_bro)

- **One post a day at 18:00 MSK (15:00 UTC).** Publishing goes through Zernio like Threads, scheduled ahead, with its own queue (`content/instagram/`) and log (`log/instagram.jsonl`).
- **Format:** carousels of 1080×1350 JPEG slides in the brand style. A quiz shows the question on slide 1 («Листай → ответ на следующем слайде») and the answer with a short why on slide 2. A phrase or lesson takes 2–3 slides. `versus` and `mistakes` cards work as single images. No emoji in the images.
- **Content:** adapted from that day's Threads posts, never a copy of the Threads text. The caption is a hook, then where the answer is, then one useful sentence, then one question for the comments.
- **Hashtags:** 4–6 per post, drawn from #английскийязык #американскийанглийский #английскийонлайн #учиманглийский #грамматикаанглийского #разговорныйанглийский #произношение #английскийдляпутешествий #ошибкиванглийском.
- **Comments:** answered by the same routine and rules as Threads. The answer is always public on Instagram, because it is on slide 2.
