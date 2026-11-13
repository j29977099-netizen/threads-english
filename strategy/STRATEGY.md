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
- Avoid: generic motivation quotes, «В современном мире...», «Давайте разберёмся», «Это не просто X, это Y», piles of hashtags, more than three emoji in a post, any unnatural English.

### How the text looks (decided 2026-11-13)

The teacher asked for writing that reads as typed by a person: fewer quotation marks and other marks, and not a period and a comma everywhere. The rules below come from 248 real Russian posts and replies about learning English, read on Threads on 2026-11-13 (131 posts and 117 replies, found through the topic searches «репетитор английского», «учу английский», «английский язык» and «разговорный английский» and in twelve busy threads), set against what this account had written until then:

| | Real posts | Our posts | Real replies | Our replies |
|---|---|---|---|---|
| Ends with a period | 12% | 43% | 13% | 55% |
| Lines ending with a period | 18% | 51% | 18% | 55% |
| Any quotation marks | 13% | 59% | 8% | 24% |
| A long dash | 14% | 98%, three per post | 6% | 31% |
| A colon | 21% | 89% | 12% | 76% |
| A bullet or checkmark list | 5% | 63% | 3% | 0% |
| Three or more emoji | 12% | 54% | 7% | 0% |
| Median length, characters | 162 | 373 | 117 | 177 |

- **A line break ends the thought.** One thought per line, and most lines end with nothing. A question keeps its question mark. Two sentences on one line keep the period between them. The last line never ends with a period, and at most a quarter of the lines do.
- **Commas** stay where the sentence can't be read without them. A sentence that needs three is two sentences.
- **Quotation marks: usually none, one pair at most.** English needs none, because the alphabet already sets it apart. A Russian phrase being translated stands on its own line or after a colon.
- **Long dashes: usually none, one at most.** Never as a pause: start a new line or a new sentence. Between a word and its translation write a plain hyphen with spaces, «это» or «значит», or put the translation on the next line.
- **Two colons at most, no semicolons.** Brackets only where they save a line.
- **Emoji:** the series marker and two more at most. They are not bullets: no ✔️ or • in front of every example. ❌ marks a wrong sentence, and ✔️ appears only next to it, on the right version.
- **No fixed skeleton.** Posts of one series share the marker and the idea, not the wording. Vary how the literal meaning is introduced, how the examples are set out and how the post ends. Not every post ends with a question and 👇, and «разбор завтра утром» is said now and then, not every time.
- **English stays correct:** capitals, apostrophes and question marks as an American would write them. An English sentence alone on its line may drop its final period like any other line.
- **Shorter where the lesson allows.** Cut the sentence that explains what the example already shows.
- **Replies and direct messages** go further (`strategy/COMMENTS.md`): one short sentence, two at most, usually under 100 characters, no opening formula, no long dash, no period at the end, and now and then a lowercase start, a «)» or one emoji.

`tools/qc.py` counts the marks for every post dated 2026-11-14 or later, and `tools/comments.py` for every reply. Posts published before that stay as they were.

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
| none | Как сказать по-английски | A feeling or everyday situation that Russian names in one colloquial phrase («я загоняюсь», «мне лень»). Opens with «Как сказать по-английски:», the phrase without quotation marks, and one emoji that fits the topic; the series has no fixed marker. Then 4 natural American ways to say it, from mild to strong, each with its Russian translation after a plain hyphen. Then «И ловушка», one trap where a near-identical word, form or preposition changes the meaning, and a short closing line with 👀. No task, so no reveal. Every third day. Added 2026-11-10 at the teacher's request |
| 💬 | Что он имел в виду? | A short exchange (a text, a reply at work) whose tone can be read two or three ways, with lettered readings A–C for readers to argue over. The next-day reply says which reading is most likely, what in the words points to it, what is only a guess, and one phrase to clarify. Pilot from 2026-11-13 |
| ➡️ | А дальше что? | The moment where textbooks stop: every word is understood, and now the reader has to answer. Open task: write your next line in English. The next-day reply gives 2 natural lines that keep the conversation going, and the cultural note behind them. Pilot from 2026-11-13 |
| 🛟 | Спасаем разговор | Something goes wrong mid-conversation: still lost after asking twice, a word forgotten, a «yes» said by accident. Open task. The next-day reply gives one move that fixes it, with 2–3 phrases. Pilot from 2026-11-13 |
| 💪 | Английский с характером | One recognisable situation where you have to say no or hold a line: extra work, unwanted advice, a question that is too personal. Three ways to say it, marked «Мягко», «Твёрдо», «С условием», then an open question. No task, so no reveal. Pilot from 2026-11-13 |
| ✏️ | Было → стало | A flat but correct answer and a livelier one, with what changed and why. A typical answer, never presented as a real student's. At most one a week |
| ✅ | Разбор | Answer reveal the next day, posted as a reply right under its quiz |
| 👋 | О занятиях | Soft promotion of private lessons |

## 4. Content mix (of all non-reveal posts)

- 35% interactive quizzes and exercises
- 25% vocabulary and American English
- 20% grammar and common mistakes
- 10% practical learning advice
- 10% personal brand and student acquisition (1–2 posts per week, never two days in a row)

The 🗽 idiom and the «Как сказать по-английски» posts share the one evening slot with the lessons (§5) and don't count toward this mix.

**Situation series (pilot, requested by the teacher on 2026-11-11).** 💬, ➡️, 🛟 and 💪 are about what to say in a real conversation, not about grammar. Each week has one post of each. They take the place of grammar quizzes in the existing slots, so the number of posts per day stays the same: 💬, ➡️ and 🛟 count as interactive, 💪 and ✏️ as vocabulary and American English. The weekly report shows their views and replies next to the grammar quizzes', and the teacher decides which series stay.

## 5. Daily rhythm

All times Moscow time (UTC+3), the centre of gravity for a Russian-speaking audience spread across Russia, Europe, Israel, Kazakhstan, and the US.

| Slot | Time (MSK) | UTC | Post |
|---|---|---|---|
| Post 1 | 09:00 | 06:00 | Engagement: quiz, challenge, translation, a situation (§3: 💬 ➡️ 🛟), question to the audience |
| Reveal | 09:15 next day | 06:15 | ✅ reveal of yesterday's morning quiz, after a full day of comments |
| Post 2 | 19:00 | 16:00 | The one evening post. Over a week: about three 🗽 idioms, about two «Как сказать по-английски», and about two of lesson, mistakes card, tip, 💪 or promo |
| Reveal | 19:15 next day | 16:15 | ✅ reveal of an evening quiz or mini-task, if there was one |

**Publishing route.** Posts go out through Zernio, which needs no Meta developer account. Each post is handed to Zernio up to 30 hours ahead with its exact time, so it publishes on the minute. Zernio cannot post polls, so quizzes collect answers in the comments. A reveal is replied under its quiz through Zernio's inbox, which can't schedule, so the "Threads answer reveals" cloud routine posts it at 06:15 and 16:15 UTC; GitHub runs post it only if the routine hasn't within 45 minutes. If a Meta developer app is set up later, setting the repository variable `PUBLISH_BACKEND=threads` brings back native polls and reveals as replies.

From week 3, test 07:30 MSK against 09:00 for Post 1 and keep what wins.

**Two posts a day, no more (decided 2026-11-12).** Threads suspended the account on 2026-11-10 and removed one of its replies as spam on 2026-11-11, and the teacher asked for fewer posts and fewer replies. Until then the idiom (12:30 MSK) and «Как сказать» (21:00 MSK) had slots of their own, which made three or four posts a day. Posts already written were spread over the evening slots, one a day. Don't add a slot back without the teacher's say.

Answer reveals are always replies to their own quiz (`reply_to`), so the explanation stays attached to the question. The original quiz never contains the answer.

## 6. Visual identity

- **Palette:** vibrant gradients, one colour theme per template in `brand/brand.json` (quiz: violet to pink, answer: green to blue, phrase: pink to orange, list: blue to teal, mistakes: red to violet), each with soft glows and a fine grain. Text sits on white panels. Accents: Sun `#FFD43B` (labels, blanks, the answer) · Pink `#FF4F9A`, Orange `#FF8A3D`, Mint `#12B886`, Blue `#3D7BFF` (badges) · Red `#F03E5C` (wrong answers) · Teal `#0B9E7A` (correct answers) · Ink `#16112F` (text).
- **Type:** Unbounded ExtraBold for headlines and labels, Onest for text (SemiBold for English examples, Medium for Russian explanations), Caveat for handwritten prompts. All SIL OFL, bundled in `brand/fonts/`. Inter stays as the fallback for arrows and IPA.
- **Format:** 1080×1350 (4:5 portrait), 72 px margins, no more than ~40 words per card.
- **Card frame:** a tilted yellow series label at the top left, sparkles at the top right, and the wordmark «Английский по-американски» and the handle in pills at the bottom. Cards must look designed, never plain: colour, depth and a handwritten touch on every one.
- **Templates:** quiz card, answer card, textbook-vs-America card, mistakes list, phrase card, numbered list, chat card (a message exchange as bubbles).
- **Rules:** no stock photos, no copyrighted images, no emoji inside graphics (they render inconsistently), every English and Russian word on a card is checked before publishing.

## 7. Growth and conversion

- Bio and the pinned intro post (`2026-11-09-intro`) tell a new visitor in 5 seconds who this is and how to book.
- Every quiz invites a comment ("почему именно этот вариант?"), because replies drive Threads distribution more than likes.
- Reply to genuine comments within the day: thank, encourage, explain. Never spoil a quiz before its reveal.
- One soft promotional post a week at most (it was 1–2 until 2026-11-13, when the teacher asked not to overdo sending people to direct messages). It is the only post that mentions writing to the teacher, and it says so once, in passing: «Если думаешь про занятия, напиши мне». No other post, and no reply to a stranger, invites anyone to direct messages.
- No follow-for-follow, no bought engagement, no unsolicited DMs, no mass commenting on other accounts.
- **What gets an answer** (from the 2026-11-13 reading, §2). In twelve threads where people asked for a tutor or for advice, 48 of the replies were pitches: a greeting, credentials, a price, an invitation to write. The person who asked answered one of them. Of the 61 replies that simply talked to the person (a tip, their own experience, a real question), five got an answer. A post asking for a tutor collects 30 to 130 near-identical pitches, so one more is noise at best and spam at worst, and many of those posts ask for a price up front, which this account does not state in public. People come from the posts and the profile, not from being asked to.
- Lesson inquiries arrive as DMs, which the Threads API cannot read. The teacher handles DMs personally.

## 8. Quality control (every post, before it enters the queue)

1. Grammar and vocabulary are correct, and the English is natural American English.
2. A quiz has exactly one defensible correct answer. Avoid items where context could make a distractor correct.
3. Distractors are plausible mistakes a Russian speaker would actually make.
4. Russian text is correct in spelling and grammar, with «ё» where it matters, and it looks typed by a person (§2, How the text looks): few marks, and no period on every line.
5. The explanation is understandable to a B1 learner.
6. Card text is readable at phone size and identical to what was checked.
7. The topic hasn't been used in the last 30 days (check `log/publications.jsonl` and the queue).
8. Text ≤ 500 characters, at most 5 links, one topic tag (and poll options ≤ 25 characters on the threads route).
9. There is a clear engagement prompt where appropriate.
10. The reveal answers the same question, with the same options and letters, as its quiz.

`tools/qc.py` checks 6–8 and 10 mechanically, and the countable part of 4 (quotation marks, long dashes, colons, periods). Items 1–5 and 9 need judgement.

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
- **Content:** adapted from that day's Threads posts, never a copy of the Threads text. A situation post (§3: 💬 ➡️ 🛟 💪) opens with the exchange as chat bubbles and the question on slide 1, and gives the answer on slide 2. The caption is a hook, then where the answer is, then one useful sentence, then one question for the comments, written the way a Threads post is (§2, How the text looks), with the hashtags on the last line.
- **Hashtags:** 4–6 per post, drawn from #английскийязык #американскийанглийский #английскийонлайн #учиманглийский #грамматикаанглийского #разговорныйанглийский #произношение #английскийдляпутешествий #ошибкиванглийском.
- **Comments:** answered by the same routine and rules as Threads. The answer is always public on Instagram, because it is on slide 2.
