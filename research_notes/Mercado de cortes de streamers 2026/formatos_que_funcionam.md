# Short-video formats that work for streamer clips (TikTok and YouTube Shorts, state as of Nov 2026)

Reader note on evidence quality. Three tiers are used throughout:
- **[OFFICIAL]** = platform documentation or a named platform employee.
- **[DATA]** = a study with a disclosed sample (still mostly published by vendors; none is streamer-clip specific).
- **[FOLKLORE]** = vendor blog / creator advice with no disclosed data.

Almost no source isolates gaming/streamer clips. Nearly all quantitative data is about short video in general (often brand accounts). This is the single biggest limitation of these notes.

---

## 1. What duration range performs best on TikTok vs YouTube Shorts in 2025-2026, and how did longer formats (1 min+, 3-min Shorts) change this?

### Takeaway
There is no single best length, and the data splits by metric: on TikTok, median views rise with length (best at 2-3 min in the largest 2026 dataset) while engagement rate peaks at 15-30 s; on YouTube Shorts the only disclosed dataset points to 11-30 s for median views. YouTube's own position is that length should match the story; no platform publishes a target length.

### Cited Findings
- [OFFICIAL] Since 15 Oct 2024, square or vertical uploads up to 3 minutes are classified as Shorts — [YouTube Help](https://support.google.com/youtube/answer/15424877?hl=en)
- [OFFICIAL, older: Aug 2023] Todd Sherman (YouTube Shorts lead) on length: "To what length do you need to tell your story?" i.e. no preferred length is built in — [Creator Insider video, 3:03](https://www.youtube.com/watch?v=n3jsYK_-aRU&t=183s), via [OutlierKit transcript summary](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] TikTok lists "video duration" as one of the content-information signals its recommender considers, without saying which direction is favored — [TikTok Transparency Center](https://www.tiktok.com/transparency/recommendation-system/)
- [DATA] Socialinsider, 8,000,795 organic TikTok videos, Jan-Jun 2026, brand accounts (published 10 Jul 2026). Median views / average engagement rate by length: 0-15 s 1,274 / 5.90%; 15-30 s 1,000 / 6.00% (highest ER); 30-60 s 2,200 / 4.20% (lowest ER); 60-90 s 7,200 / 4.80%; 90-120 s 9,620 / 5.15%; 120-180 s 11,136 (highest views) / 5.50%; >180 s 10,150 / 5.90%. Caveats: brands not creators; the article itself is inconsistent about sample size (6M vs 8M) and follower-range filters — [Socialinsider](https://www.socialinsider.io/blog/how-long-are-tiktok-videos/)
- [DATA, older: Mar 2025] Buffer, 1.1M TikToks: median reach 194 (5-10 s), 302 (30-60 s), 432.5 (60 s-10 min); median watch time 3.1 s, 6.9 s, 11.3 s respectively. 86% of videos were under one minute; only 12.3% were 60 s+. Buffer notes length is "unlikely to be a make-or-break factor"; some of the article's stated percentage differences do not match its own medians — [Buffer](https://buffer.com/resources/longer-tiktoks-get-more-views-data/)
- [DATA, small sample] OpusClip scraped 1,449 public TikToks across 10 niches (gaming included but not broken out; published Apr 2026). Median length 50 s overall, 41 s for the "viral" tier (top 10% by views, 5.1M+); viral 90th percentile 179 s. Share of videos 0-30 s: 29.2% viral vs 20.3% overall; 60-90 s: 13.9% viral vs 18.5% overall; 90 s+: 15.9% vs 19.6%. Collection method and dates undisclosed — [OpusClip](https://www.opus.pro/blog/how-long-should-a-tiktok-be-2026)
- [DATA] quso.ai first-party dataset (~508K posts, 1,900+ creators, 12 months, updated 29 Jun 2026): for YouTube Shorts, the 11-20 s bucket has the highest median views; page recommends 11-30 s. No per-bucket numbers published — [quso.ai](https://quso.ai/research/video-retention-benchmarks)
- [DATA, weak/secondhand] An "Inflow Network" study of 5,400 Shorts reportedly found 50-60 s Shorts got ~22x the views of sub-10 s Shorts; only seen via a third-party relay, not verified — [search summary pointing to ytshark.com](https://ytshark.com/?p=499)
- [DATA] Fanpage Karma, 32,000 TikToks (date unclear): highest interaction rates at 30-90 s, about double very short or very long videos — [Fanpage Karma](https://www.fanpagekarma.com/insights/optimal-tiktok-video-length/)
- [OFFICIAL] In a 3-minute Short most songs can only be used up to 90 seconds (relevant if clips use music) — [YouTube Help, quoted in AdaptlyPost](https://adaptlypost.com/pt/blog/how-long-can-youtube-short-be)
- [FOLKLORE] PT-BR tool blogs give 15-45 s or 30-60 s as "ideal" for Shorts with no data — [Captions.ai PT docs](https://captions.ai/help/docs/pt/guides/creators/format-for-platforms)

### Inferences
- The studies conflict (Socialinsider/Buffer: longer gets more views; OpusClip/quso: shorter wins) mainly because they measure different things: median views across all accounts vs. composition of the top tier vs. retention percentage. Longer videos accumulate more absolute watch time per view, which a watch-time-driven ranker rewards; shorter clips have higher completion percentage. Both can be true.
- A longer upload population is also self-selected (accounts that post 2-3 min videos tend to have content that justifies it), so "longer = more views" is correlational.
- For streamer clips specifically, a defensible reading is: single-beat moments (reaction, fail, clutch) in roughly 15-45 s; story-type moments (drama, argument, long bit) can run 60-180 s now that both platforms accept it and data shows no penalty on views. This is an inference, not a measured result for the niche.
- Since Oct 2024, a 1-3 min vertical clip on YouTube is forced into the Shorts feed, so "mid-length cortes" (1-3 min) can no longer be posted as regular vertical videos.

### Gaps
- No duration distribution was found for top-performing streamer/gaming clips specifically (no study breaks out the niche).
- No official YouTube data on how 1-3 min Shorts perform versus sub-60 s Shorts.
- Metricool's 2026 YouTube study (799,718 videos) reportedly says Shorts average view duration has "fallen dramatically" but the summary seen gives no number — [Tubefilter](https://www.tubefilter.com/2026/08/03/youtube-shorts-long-form-study-metricool/)

---

## 2. What hook patterns work in the first 1-3 seconds? Any data on swipe-away rates?

### Takeaway
The first-seconds decision is officially real and measurable (YouTube's "viewed vs swiped away"; TikTok's "skipped" signal), but neither platform publishes thresholds, and no rigorous study comparing hook types for streamer clips was found. Hook-pattern advice (start on the peak, text hook, cold open) is practitioner consensus, not measured.

### Cited Findings
- [OFFICIAL] YouTube Studio reports "Shown in feed" (times the Short appeared in the Shorts feed) and "How many chose to view" ("the percentage of times that viewers viewed your Shorts versus swiped away") — [YouTube Help](https://support.google.com/youtube/answer/12942217?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- [OFFICIAL] YouTube publishes no benchmark for viewed-vs-swiped or for retention; widely repeated thresholds (e.g. "below 50% stops distribution", "70%+ needed") are creator-reported, not from YouTube — [OutlierKit, review of YouTube statements](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] From 24 Aug 2026 a YouTube "view" counts from the first frame for all formats; an "engaged view" is "clicking to watch or watching past the initial seconds". Retention, AVD and most analytics stay anchored on engaged views, and YouTube says there is "no change to recommendations" — [YouTube Blog, 19 Aug 2026](https://blog.youtube/inside-youtube/engaged-views-youtube-explained/)
- [OFFICIAL] TikTok's recommender considers whether a user spent time viewing a video and whether they finished or skipped it — [TikTok Transparency Center](https://www.tiktok.com/transparency/recommendation-system/)
- [DATA] quso.ai: median Short has ~45% average view-through; top 10% reach ~91%; "40-45% is average, 50-60% is doing well". It states most retention loss happens in the first three seconds but gives no figure — [quso.ai](https://quso.ai/research/video-retention-benchmarks)
- [FOLKLORE, conflicting] Vendor benchmarks: ClipIQ via GoFaceless puts 50-64% retention as average, 65-79% strong, 80%+ top; Humble&Brag says hold >80% through first 3 s and >70% average percentage viewed. These disagree with quso's 45% median and none is verified — [GoFaceless](https://www.gofaceless.ai/en/blog/youtube-shorts-retention-rate-benchmarks); [Humble and Brag](https://humbleandbrag.com/blog/youtube-shorts-benchmarks)
- [FOLKLORE] Gameplay-clip guide: start at the peak or just before it (e.g. start at 5 s if the peak is at 8 s); a segment needs a clear emotional turn within the first three seconds; ~15 s of setup before the action is "fatal". No data cited — [Cut.pro](https://cut.pro/en/blog/cut-gameplay-into-vertical-clips-2026)
- [FOLKLORE/anecdote] OpusClip: one clip that "failed at 52 seconds" did "3x" better recut to 38 s; a single example — [OpusClip](https://www.opus.pro/blog/how-long-should-a-tiktok-be-2026)
- [REPORTING] NPR on clippers' method: they pair a provocative moment with engaging music and sometimes a timely news cycle — [NPR via KUNC, 12 May 2026](https://www.kunc.org/npr-news/2026-05-12/the-clipping-economy-how-short-form-video-clippers-are-overrunning-the-internet)

### Inferences
- Because a Shorts view now registers at first frame while analytics stay on engaged views, the gap between "views" and "engaged views" in Studio is effectively a per-clip swipe-away measure; it is the most reliable hook metric a clip channel has, and should be compared across its own clips rather than against vendor thresholds.
- The practical hook hierarchy implied by the sources: (1) cut the setup so the reaction/peak is inside the first 3 s, (2) add a text hook that supplies the missing context ("he didn't know the mic was on"), (3) if context is essential, cold-open on 1-2 s of the punchline and then rewind. Only (1) has even anecdotal support; none is measured.

### Gaps
- No public dataset of swipe-away rates by hook type (text hook vs reaction-first vs question) was found, for any niche.
- No official TikTok figure for the share of viewers lost in the first 3 seconds.
- Vendor retention benchmarks conflict by 20-30 percentage points; treat all as unreliable.

---

## 3. Which caption styles perform best? Any evidence captions raise retention?

### Takeaway
Captions helping completion is directionally supported, but the only named-research evidence is old (2019) and not about short-form; all 2025-2026 claims about animated/karaoke styles outperforming static ones come from caption-tool vendors with undisclosed methods.

### Cited Findings
- [DATA, old: 2019] Verizon Media/Publicis survey of 5,616 US adults: 80% said they are more likely to watch a video to completion when captions are available (self-reported, not short-form specific) — relayed in [ClipSpeed](https://clipspeed.ai/blog/ai-captions-increase-views.html)
- [FOLKLORE, vendor] Claimed lifts vary enormously: +12% views (Facebook study via 3Play Media), completion 28% to 46% (Sonix compilation), animated ~2x static on retention (BlitzCut), animated adds 5-15% retention over static (another vendor), +34% watch time for word-by-word color captions in an 80-video test (FluxNote). None publishes methodology — [BlitzCut](https://blitzcutai.com/blog/animated-captions-vs-static-captions); [FluxNote](https://fluxnote.io/blog/ai-captions-that-improve-watch-time); [OpusClip](https://www.opus.pro/blog/caption-styles-drive-views)
- [FOLKLORE] Sound-off viewing figures of 70-85% circulate with no shared verified source — [ClipSpeed](https://clipspeed.ai/blog/ai-captions-increase-views.html)
- [FOLKLORE] Platform-style claim: TikTok audiences expect high-contrast animated captions; on Shorts, medium-weight readable captions tend to beat flashy styles; same cut can be exported once with only captions/text changed per platform — [Captions.ai PT docs](https://captions.ai/help/docs/pt/guides/creators/format-for-platforms)
- [FOLKLORE] For gameplay clips: place captions between facecam and gameplay or low on screen away from the HUD, in a fixed position; color-highlight keywords rather than whole sentences; sync each word to speech; a big caption over busy HUD is "visual noise" — [Cut.pro](https://cut.pro/en/blog/cut-gameplay-into-vertical-clips-2026)
- [OFFICIAL, indirect] TikTok search uses captions, spoken audio and on-screen text as signals according to SEO guides (not confirmed on a TikTok page in this research) — [Metricool TikTok SEO guide](https://metricool.com/tiktok-seo/)

### Inferences
- Burned-in captions likely matter more for streamer clips than for scripted content because stream audio is noisy (game sound, alerts, shouting) and many clips are in Portuguese/English slang; but this is reasoning, not data.
- With no credible evidence separating karaoke word-highlight from 2-3-word chunks, style choice is a branding/legibility decision; the safest evidence-neutral default is 2-4 words per card, high contrast, one highlight color, fixed position in the seam between facecam and gameplay.

### Gaps
- No independent 2025-2026 A/B study of caption style (karaoke vs static, font, color, emoji) on retention was found.
- No data on caption position or emoji usage effects.
- No evidence specific to Portuguese-language clips.

---

## 4. Which layouts do the most successful clip channels use (stacked facecam/gameplay, zoomed crop, blurred bars)? What do Kai Cenat, xQc, IShowSpeed, Casimiro, Gaules clip channels use?

### Takeaway
No source documenting the layouts actually used by named top clip channels was found; this question is essentially unanswered by web sources and needs direct observation of the channels. Tool-vendor guides agree on a stacked layout (facecam top third, gameplay below) for gaming and a full-frame face crop for IRL/reaction content, but offer no performance data.

### Cited Findings
- [FOLKLORE] "The layout that delivers the most is the stacked one": facecam in the top third, gameplay below; crop the gameplay to the action (crosshair, enemy, key event) rather than shrinking the full 16:9 frame; zoom in on the one HUD number that matters — [Cut.pro](https://cut.pro/en/blog/cut-gameplay-into-vertical-clips-2026)
- [FOLKLORE] Template guide lists split-screen for reaction-heavy content, gameplay-only, and facecam-focused layouts for IRL streamers; says most gaming streamers default to blurred-background gameplay fill or split screen — [Eklipse](https://blog.eklipse.gg/beginner-guide-2/twitch-clip-templates.html)
- [FOLKLORE] Keep key text inside the central safe zone of a 1080x1920 9:16 frame — [Captions.ai PT docs](https://captions.ai/help/docs/pt/guides/creators/format-for-platforms)
- [OFFICIAL] On YouTube, "minor technical edits, or template-based bulk changes" do not count as adding value under the Oct 2026 originality change (see Q6); a layout template alone does not make a re-uploaded clip "original" — Rene Ritchie, quoted in [Search Engine Journal](https://www.searchenginejournal.com/youtube-original-shorts-reposted-clips-reach/591774/)
- [REPORTING] Scale context: Hasan Piker's average livestream draws ~33,000 views while his average clip gets 700,000+; clippers often post dozens of copies of the same clip across platforms — [NPR via KUNC, 12 May 2026](https://www.kunc.org/npr-news/2026-05-12/the-clipping-economy-how-short-form-video-clippers-are-overrunning-the-internet)

### Inferences
- Layout should follow where the content is: gameplay-driven moment = stacked cam + cropped gameplay; talk/reaction/IRL moment = full-height face crop; blurred bars are the low-effort fallback that wastes screen area and is the most "template-like".
- Given YouTube's Oct 2026 change, layout work is not a reach differentiator by itself; what matters is added context/commentary.

### Gaps
- **No evidence found on the actual layouts used by clip channels of Kai Cenat, xQc, IShowSpeed, Casimiro (Cortes do Casimito) or Gaules.** Searches returned only tool-vendor pages and unrelated news. A manual sample (e.g. top 20 Shorts by views on each channel, coding layout, caption style, duration, hook) is the only way to answer this.
- No Portuguese-language reporting or interviews with operators of Brazilian "canais de cortes" on format decisions was found; PT-BR results were vendor blogs (mostly Cut.pro).
- No study comparing layout types on retention.

---

## 5. How often do successful clip channels post; does volume vs quality matter; best posting times?

### Takeaway
YouTube officially says neither posting time nor a posting-frequency threshold is built into Shorts ranking; the clipping industry nonetheless runs on very high volume (dozens of uploads per day across many accounts), and the Oct 2026 YouTube originality change plus platform spam crackdowns now cut against pure-volume reposting.

### Cited Findings
- [OFFICIAL, older: Aug 2023] Todd Sherman on posting time: "It's not something that we think about optimizing for." On frequency: "There is nothing in our systems that's like when you hit the five video or 10 short threshold". On deleting and re-posting: "There is a risk there that that gets seen as spam in our systems." — [Creator Insider video](https://www.youtube.com/watch?v=n3jsYK_-aRU&t=327s), via [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] TikTok lists publish time and publishing region among content signals, without describing a best time — [TikTok Transparency Center](https://www.tiktok.com/transparency/recommendation-system/)
- [FOLKLORE, vendor with commercial interest] A scheduler vendor claims ~60 uploads/day are needed for a clipping page to reach $10K-$100K/month and that some operators average 120/day — [Postiz](https://postiz.com/blog/ai-video-clipping-agent-postiz-stack)
- [REPORTING] Clipping networks: one operator runs 40,000 freelance clippers; Cluely's co-founder said he hired 700+ clippers generating tens of millions of views; campaign rates cited range from $0.50 to $25 per 1,000 views; platforms "boost clips algorithmically but also crack down on pages dedicated to clips, which can look spammy or bot-like" — [NPR via KUNC, 12 May 2026](https://www.kunc.org/npr-news/2026-05-12/the-clipping-economy-how-short-form-video-clippers-are-overrunning-the-internet)
- [SELF-REPORTED] Whop said to average 100M+ clipping views/day; agencies claim 10B+ views with 100,000+ clippers. Unverified — [ListenFirst](https://www.listenfirstmedia.com/what-marketers-need-to-know-about-the-clipping-economy/)
- [REPORTING] A marketplace operator called bot fraud "the single biggest threat" to the clipping model — [Business of TV](https://businessoftv.substack.com/p/clippers-and-view-botting-big-social)
- [FOLKLORE, PT-BR] Clipper pay is per view, so output = number of clips x retention per clip; structured programs on bigger channels work as teams with volume targets and revenue split; consolidated streamers already have 5-10 clip channels fighting over the same moments, while many Kick streamers lack a dedicated clip channel — [Cut.pro PT-BR](https://cut.pro/pt-BR/blog/clipar-kick-oportunidad-2026); [Cut.pro PT-BR](https://cut.pro/pt-BR/blog/join-streamer-clipper-army-2026)
- [FOLKLORE, PT-BR] One source says creators are moving to one or two highly edited cuts per week — [StreamHub PT](https://streamhub.world/pt/streamer-blog/youtube/2839-how-to-repurpose-youtube-vods-into-high-performing-short-form-content/)
- [DATA, long-form only] Metricool 2026: 2-4 videos/week is the sweet spot for long-form views; no Shorts frequency figure in the summary seen — [Tubefilter](https://www.tubefilter.com/2026/08/03/youtube-shorts-long-form-study-metricool/)

### Inferences
- Volume works as a lottery-ticket strategy because each Short is tested on its own seed audience and outcomes are heavy-tailed; more attempts = more chances at an outlier. That is consistent with Sherman's statements (no frequency bonus, but no penalty either) without implying the algorithm rewards frequency itself.
- For streamer clips, speed (posting a moment within hours of the live) is plausibly more important than time-of-day, since several channels compete for the same moment; no data confirms this.
- "Best time to post" tables from analytics vendors are averages of brand accounts and are contradicted by YouTube's statement for Shorts; safest guidance is to post when the target audience (e.g. Brazil evening) is active and not over-optimize.

### Gaps
- No verified posting-cadence data for named successful streamer clip channels (would require scraping upload histories).
- The official YouTube statements on timing/frequency date from 2023; no 2025-2026 restatement was located.
- No independent test of volume vs. quality for clip channels.

---

## 6. What do TikTok and YouTube officially say about ranking in 2025-2026?

### Takeaway
Both platforms officially describe viewer-behavior prediction (watch, finish, skip/swipe, like, share) without weights or thresholds. The most consequential 2026 official change for clip channels is YouTube's 1 Oct 2026 announcement that Shorts recommendations will reduce reach for content re-uploaded from other creators without added value.

### Cited Findings
- [OFFICIAL, 1 Oct 2026] YouTube is updating Shorts systems "to further prioritize original content and reduce the reach of content re-uploaded from other creators" without adding anything of your own — [YouTube Help Community post](https://support.google.com/youtube/blog/470890423/prioritizing-original-content-on-shorts?hl=en) (primary page could not be read in full; quote via [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/) and [Search Engine Journal](https://www.searchenginejournal.com/youtube-original-shorts-reposted-clips-reach/591774/))
- [OFFICIAL, 1 Oct 2026] Rene Ritchie (YouTube Creator Liaison): added value must be your own, "not just VO descriptions of what's happening on screen, minor technical edits, or template-based bulk changes"; creators should add commentary, analysis, storytelling. If a channel "was previously aggregating or re-uploading" and shifts toward original content, the system "will re-evaluate reach". No start date, timeline, detection method, or way to check status was given; the video did not address Shorts cut from a creator's own long-form/streams — [Search Engine Journal](https://www.searchenginejournal.com/youtube-original-shorts-reposted-clips-reach/591774/)
- [OFFICIAL] The Oct 2026 change is about recommendations; monetization continues under the reused-content policy ("If you borrow content from someone else, you need to change it significantly to make it your own"); Ritchie said in July 2025 the reused-content rules for clips/compilations/reactions were unchanged — [Search Engine Journal](https://www.searchenginejournal.com/youtube-original-shorts-reposted-clips-reach/591774/)
- [OFFICIAL, 19 Aug 2026] View = first frame; engaged view = watching past the initial seconds; YPP still uses qualified/engaged views; "no change to recommendations" — [YouTube Blog](https://blog.youtube/inside-youtube/engaged-views-youtube-explained/)
- [REPORTING] Shorts view counting first changed on 31 Mar 2025 to count plays/replays with no minimum watch time — [TechCrunch](https://techcrunch.com/2025/03/26/youtube-is-changing-how-youtube-shorts-views-are-counted/)
- [OFFICIAL, older: Aug 2023] Sherman: the system tries to "find a set of people that may enjoy your video" (seed audience, then expand); "The audience is the algorithm."; hashtags are not required; most Shorts thumbnails are never seen because viewing is in-feed — [Creator Insider video](https://www.youtube.com/watch?v=n3jsYK_-aRU), via [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] YouTube has not said that "viewed vs swiped away" is the ranking signal or published any threshold — [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] TikTok: signals are combined into a prediction score per video; inputs include user interactions (time spent viewing a video; finishing, skipping, favoriting; likes, shares, comments, "not interested"), content information (publish time, region, creator language setting, sound, video duration, hashtags) and user information (region, device language, OS, follow graph). No weights disclosed. A similarity check swaps out videos with the same audio to keep the feed varied — [TikTok Transparency Center](https://www.tiktok.com/transparency/recommendation-system/)
- [OFFICIAL, old: Jun 2020] TikTok said finishing a video is a strong signal while device/language/country are weaker, and that follower count and prior high-performing videos are not direct factors — [TechCrunch](https://techcrunch.com/2020/06/18/tiktok-explains-how-the-recommendation-system-behind-its-for-you-feed-works)
- [DATA] Metricool 2026 (799,718 videos, 71,177 accounts): 61% of all measured YouTube views now come from the Shorts feed; Shorts traffic more than doubled year over year — [Tubefilter](https://www.tubefilter.com/2026/08/03/youtube-shorts-long-form-study-metricool/)

### Inferences
- For a third-party clip channel on YouTube, the Oct 2026 change is the dominant ranking fact: raw re-uploads with a layout template and auto-captions fall squarely within "minor technical edits, or template-based bulk changes". Formats likely to qualify add something authored: context text, narration/commentary, multi-moment storytelling, analysis.
- An official/authorized clip channel run by or for the streamer is in a gray zone: YouTube has not said whether "own content cut from own streams" on a separate channel is treated as original.
- TikTok's same-audio similarity check suggests duplicate clips of the same viral moment compete with each other in a single user's feed; being first or having a distinct edit matters.
- "Rewatches" as a signal: neither platform's official text names loops/rewatches explicitly; it is plausible they count toward watch time, but claims about loop bonuses are folklore.

### Gaps
- The primary YouTube Help Community post of 1 Oct 2026 could not be read directly (page truncated); wording here relies on secondary coverage that agrees across outlets.
- No official statement on rewatch/loop weighting on either platform.
- No TikTok official 2025-2026 statement specifically on re-uploaded/clipped content was retrieved in this research (TikTok's originality rules for For You eligibility were not verified here).
- TikTok Creator Academy material was not directly retrieved.

---

## 7. What title/description/hashtag practices are supported by evidence for Shorts search and TikTok search?

### Takeaway
Evidence is thin: officially, hashtags are optional on Shorts and are merely one listed signal on TikTok; keyword-in-caption and "3-5 hashtags" advice comes from marketing blogs. TikTok's own Creator Search Insights tool is the only first-party resource for choosing search terms.

### Cited Findings
- [OFFICIAL, older: Aug 2023] Sherman on Shorts hashtags: "Are they required? No, of course not." — [Creator Insider video, 4:53](https://www.youtube.com/watch?v=n3jsYK_-aRU&t=293s), via [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [OFFICIAL] TikTok lists hashtags and sound among content signals for recommendation — [TikTok Transparency Center](https://www.tiktok.com/transparency/recommendation-system/)
- [OFFICIAL tool] TikTok Creator Search Insights (launched Mar 2024) shows what users search for and "content gap" topics with high demand and few videos; reachable by searching "Creator Search Insights" in-app — [Buffer explainer](https://buffer.com/resources/creator-search-insights/)
- [FOLKLORE] TikTok SEO guides: captions, spoken audio and on-screen text are all search signals; put the keyword early in the caption; no supported numeric keyword limit; caption+hashtags share a 4,000-character limit; hashtag counts recommended vary (2-3 vs 3-5), all stressing relevance — [Metricool](https://metricool.com/tiktok-seo/); [CapCut](https://www.capcut.com/create/tiktok-caption-keywords-search-seo)
- [OFFICIAL] Most Shorts thumbnails are never seen because viewing is in-feed, so title/thumbnail carry less weight for Shorts than for long-form — Sherman via [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)

### Inferences
- For streamer clips, search demand is entity-driven (streamer name + game + event, e.g. "Casimiro reage ..."), so the evidence-neutral practice is: streamer name and the concrete event in the title/caption and spoken/on-screen text, 2-4 specific hashtags (streamer, game, #shorts unnecessary), and no generic tag walls.
- Because on-screen text and speech are reportedly indexed by TikTok search, the text hook and captions double as search metadata.

### Gaps
- No quantitative study on Shorts title length/keywords or hashtag count vs. views for 2025-2026 was found.
- No official YouTube 2025-2026 documentation on Shorts search ranking was retrieved.
- TikTok's official help page on search/keywords was not retrieved directly; guidance above is secondhand.
