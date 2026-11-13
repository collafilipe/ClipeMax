# Automatic clipping tools (long stream/VOD to vertical shorts) — competitor notes, state as of Nov 2026

Reading notes for the report writer:
- Evidence quality in this market is poor. Most "comparisons" are published by vendors (Eklipse, ClipSpeedAI, AutoClip, Klap, SendShort, Kompozy, BIGVU, ScaleReach). Each finding below is tagged **[vendor]**, **[competitor]**, **[independent]** or **[aggregator]**. "Independent" here mostly means a small blog that itself relies on secondhand reports; I found no rigorous hands-on benchmark of gaming clippers.
- Prices conflict across sources for almost every tool. Ranges are given with the source for each figure; none were verified against a logged-in checkout.
- Research budget was limited; coverage is deep for Eklipse, OpusClip, StreamLadder, Medal, Twitch, YouTube and thin for Crayo, 2short.ai, Munch, Klap, Vizard, Spikes Studio, Framedrop, Kick (see Gaps in each section).

## 1. Which signals do the best tools use to pick moments, and which work best for gaming? In-game event detection? GTA VI?

### Takeaway
Three families of signal exist: (a) game-state detection (reading kill feed/victory screens via vision, or game telemetry/APIs), (b) audience/streamer reaction (chat velocity, voice energy, voice commands), and (c) LLM scoring of the transcript ("virality score"). For gaming, sources consistently say (a)+(b) beat (c); transcript-only tools (OpusClip and its clones) are reported at roughly 60% usable clips on gaming versus 80-85% on podcasts. No tool was found with announced, dedicated GTA VI event detection; GTA-type open-world content has no kill feed, so tools fall back to audio/reaction signals.

### Cited Findings

**Eklipse (gaming-specialist, cloud, VOD-based)**
- [vendor] "Gameplay Intelligence" engine runs on every Premium VOD since June 1, 2026, with three layers: (1) candidate scoring on several signals at once — game-state events (kill feed entries, objective captures, eliminations, defeats, round transitions), audio separated into voice / chat-relevant sound / in-game audio, on-screen action density, and whether the moment starts a larger sequence; (2) scene-aware clip boundaries (reads UI, character state, map position, who is on screen; variable clip length, tries to include setup); (3) per-genre model routing chosen automatically from game metadata (FPS, battle royale, MOBA, tactical shooter, strategy/non-action) — [Eklipse blog](https://blog.eklipse.gg/streaming-tips/how-gameplay-intelligence-works-2.html)
- [vendor] Games named: Valorant, CS2, Apex, Warzone, Fortnite, Arc Raiders, League of Legends, Dota 2. Unsupported titles "fall back to general action-detection logic" with lower quality. Admitted limits: talk-heavy content yields fewer clips, non-English voice may be misclassified, loud music level with voice hurts separation — [Eklipse blog](https://blog.eklipse.gg/streaming-tips/how-gameplay-intelligence-works-2.html)
- [vendor] Claims "1,000+ supported games" and use of game events, reactions and Voice Command — [Eklipse compare page](https://eklipse.gg/compare/best-ai-gaming-video-editor/)
- [independent, secondhand] Described as visual detection (OCR/object detection of kill feeds, victory screens, scoreboard changes) plus a "Clip it!" voice command; accuracy "about 80%" from community reports (about 1 in 5 clips mistimed or false positive); misses moments without a scoreboard event (taunts, movement plays) — [Two Average Gamers, Apr 2026](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- [independent, secondhand] Community estimate of about 90% on well-supported titles; a Trustpilot reviewer reported "personal deaths were tagged as downed raiders" and multi-kills captured only at the final kill — [Two Average Gamers head-to-head](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [vendor] Users can flag missed moments/false positives in the dashboard; Eklipse says its model learns from this feedback; detection is weaker for strategy, JRPG, Just Chatting — [Eklipse blog](https://blog.eklipse.gg/tools/ai-twitch-clip-generator-2.html)

**Medal.tv (local recorder, event-triggered)**
- [vendor] Auto-clipping is a game event triggering the instant-replay recorder instead of a hotkey; clips are auto-named after the event (e.g., "Ace", "3K"). Windows app only. Event list as of May 5, 2026: CS2 (kill, 2K-4K, ace, headshot, death, assist), Dota 2, EA Sports FC Online, Fortnite (eliminations, multi-kills, Victory Royale), League of Legends (kills, objectives, turrets), PUBG, Rematch, R.E.P.O., Rocket League, RuneScape: Dragonwilds, Valorant, War Thunder, YAPYAP, Minecraft (server-defined) — [Medal auto-clipping page](https://medal.tv/auto-clipping)
- [vendor] **GTA V is supported only through FiveM servers, which define their own events** — there is no native GTA single-player/GTA Online event detection — [Medal auto-clipping page](https://medal.tv/auto-clipping)
- [competitor/aggregator] A roundup puts Medal at "100+ games" for event auto-clipping and says vertical polishing is lighter than dedicated editors — [Kompozy roundup, Jul 2026](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026) (conflicts with the roughly 15 titles on Medal's own page; the larger number likely counts all recordable games)

**Powder**
- [competitor/aggregator] Detects in-game events from telemetry in "40+ titles", clips "the instant they happen" — [Kompozy roundup](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026); an Eklipse blog claims Powder announced closure in late 2024 — [Eklipse blog](https://blog.eklipse.gg/reviews/eklipse-vs-powder-gg.html). Status is unresolved (see Gaps).

**Sizzle.gg**
- [independent, secondhand] Multi-signal: video, audio and live chat spikes; about 40 games natively with quality dropping outside them — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)

**StreamLadder ClipGPT**
- [vendor] AI "goes through your entire stream and finds the best moments" (funny reactions, big wins, fails); each clip gets a Virality Score based on "viewer engagement potential and action-packed scenes". Signals not disclosed — [StreamLadder blog](https://streamladder.com/blog/introducing-clipgpt-quickly-create-clips-from-your-streams)
- [independent, secondhand] Characterised as audio + chat engagement, not game-specific — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)

**OpusClip (transcript/LLM family; representative of Vizard, Klap, Munch, 2short, Spikes)**
- [aggregator] Virality Score 1-100, reportedly broken into Hook, Flow, Value and Trend grades; "ClipAnything" lets the user describe a moment in natural language and the model searches for it — [Ssemble review](https://ssemble.com/blog/opus-clip-review-2026)
- [independent, secondhand] Audio/transcript-driven and not game-aware; "waits for speech pauses and cuts late, skipping the action" (creator Dustin Miller, an OpusClip brand partner); about 80-85% usable on podcasts versus about 60% on gaming — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [vendor] OpusClip publishes a chat-velocity recipe (via its MCP server, Pro plan): build a messages-per-10-seconds timeline, compute a per-stream baseline, flag windows several times above baseline, **start the clip about 30 seconds before the spike because chat reacts late**, rank by spike size, count emote-only spam as signal. Names Twitch and YouTube, not Kick — [OpusClip MCP inspiration page](https://www.opus.pro/mcp/inspiration/clip-the-moments-your-live-chat-exploded)

**Twitch native Auto Clips**
- [vendor/platform] Uses "chat activity, vocal inflection, and on-screen events", plus the voice trigger "Twitch Clip That" — [Twitch blog, May 30, 2026](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)

**Others**
- [competitor/aggregator] WayinVideo is listed as optimised for LoL, Valorant, CS2, Fortnite and GTA V via general video understanding (upload-based, credit-priced) — [Kompozy roundup](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026)
- [vendor] Framedrop: paste a VOD URL and AI clips it; has per-game landing pages (e.g., League of Legends) — [Framedrop Twitch page](https://framedrop.ai/twitch)

**GTA / GTA VI**
- [vendor] Eklipse has a GTA V page promoting voice-activated clipping — [Eklipse GTA V page](https://eklipse.gg/use-case/grand-theft-auto-v-highlights); Eklipse GTA 6 blog content (surfaced via search snippet) says its AI reads "audio peaks and reactions" for GTA and that GTA "has no kill feed for a detector to read" — [Eklipse GTA 6 blog](https://blog.eklipse.gg/streaming-tips/gta-6-content-ideas.html) (snippet-level; the exact post among several Eklipse GTA 6 articles was not opened)
- [competitor] ClipSpeedAI publishes a cluster of "best AI clipping software for GTA 6" SEO pages ranking itself first; these are marketing, not announcements of GTA-specific detection — [ClipSpeedAI](https://clipspeed.ai/gta6/best-ai-clipping-software-gta-6.html)

### Inferences
- The gaming market leader's own architecture (Eklipse) is a fusion: game-state vision + separated audio stems + action density + scene-aware boundaries. Twitch's native tool uses the same triad (chat, voice, on-screen events). That convergence is the best available evidence of what works.
- For GTA-style sandbox/RP content there is no kill feed, so the usable signals are streamer voice energy, chat velocity (with a backdated window), voice commands, and LLM reading of the transcript for narrative/funny moments. Vision would have to target GTA-specific HUD cues (wanted stars, "WASTED"/"BUSTED", mission passed) — nobody appears to ship that. This is an open niche.
- Recurring failure mode of event-driven clipping: it catches the kill but not the buildup or non-scoring moments; recurring failure of transcript-driven clipping: boundaries snap to speech pauses, missing the action.

### Gaps
- No vendor announcement of GTA VI event detection was found from Eklipse, Medal, Powder, Sizzle, StreamLadder or OpusClip. Absence of evidence only; pages may appear around launch.
- Powder's operating status (closed in late 2024 per a competitor versus listed as active in 2026 roundups) could not be resolved.
- Detection internals for Sizzle, Framedrop, Crayo, Spikes Studio, 2short.ai, Munch, Vizard and Klap were not obtained from primary sources.
- The 80%/90%/60% accuracy figures are community estimates, not measured benchmarks.

## 2. Which tools monitor a live stream and clip in near real time, and how fast?

### Takeaway
Most mainstream tools are post-stream VOD processors with latency from minutes to many hours. True during-stream clipping exists as Eklipse "Live Clipping" (top tier), local event recorders (Medal, Powder), Twitch's upcoming Auto Clips, and several small/new entrants (ClipSpeedAI, Klypra, Clipray, Reka, TL;DR) whose speed claims (30-90 seconds) are unverified vendor marketing.

### Cited Findings
- [vendor] Eklipse lists "Live Clipping (Premium Pro) — makes clips while you're still live", and "Auto Clipper" that processes VODs in the background — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- [vendor] Eklipse voice command: say "clip it!"/"clip that!" during the stream to mark a moment — [Eklipse Voice Command](https://eklipse.gg/features/voice-command/)
- [independent, secondhand] Eklipse real-world latency: support says to contact them if processing exceeds 24 h (free) or 4 h (Premium); users report from minutes to 18-hour queues — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [independent, secondhand] Sizzle.gg: up to 4 hours per stream, "rules out same-night posting" — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- [independent, secondhand] OpusClip claims under 5 minutes for a 30-minute video but help docs say "typically 20-40 minutes" for longer content; a Feb 2026 Trustpilot review describes videos that "hang for hours and often never finish" — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [vendor] Medal: local instant replay, event saves the surrounding seconds immediately; F8 saves the last 15 s to 10 min — [Medal](https://medal.tv/auto-clipping)
- [platform] Twitch Auto Clips generates captioned clips from the stream's best moments and the "Twitch Clip That" voice trigger; beta "in the coming months" after May 30, 2026; Twitch says share of streamers with a clip after a stream rises from 50% to 85% with Auto Clips — [Twitch blog](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)
- [vendor] ClipSpeedAI "AI clipping agent" claims it watches the stream live and delivers captioned 9:16 clips in 30-90 seconds — [ClipSpeedAI](https://www.clipspeed.ai/ai-clipping-agent.html)
- [aggregator] Klypra says it watches streams live, reads chat reactions in real time and clips as they happen — [SimilarLabs listing](https://similarlabs.com/p/klypra-twitch-vod-highlights-clipper)
- [aggregator] TL;DR analyses live video and chat for hype moments and shows highlights to viewers via a Twitch extension — [ChatGate listing](https://chatgate.ai/post/tldr)
- [vendor] Reka: paste a YouTube/Twitch live URL and receive clips "delivered live" — [Reka creator](https://creator.reka.ai/livestreamclip)
- [vendor] StreamYard: say "clip that" live to mark, AI clips generated after the stream ends (not real-time) — [StreamYard blog](https://streamyard.com/blog/twitch-clip-maker-ai-streamyard-guide)
- [vendor] StreamLadder ClipGPT works from a pasted Twitch stream URL or recent streams (VOD) — [StreamLadder blog](https://streamladder.com/blog/introducing-clipgpt-quickly-create-clips-from-your-streams)

### Inferences
- "Same-night posting" is a stated user need that slow queues break; a pipeline that emits clips within minutes of a moment is a real differentiator against Eklipse/Sizzle/OpusClip queues.
- Voice-command marking ("clip that") is now table stakes (Eklipse, StreamYard, Twitch) because it is a cheap, high-precision signal that complements automatic detection.

### Gaps
- No independent latency measurements for any live clipper. Crayo was specifically searched for live Twitch monitoring and nothing was found; one guide (via search snippet) recommends Crayo for "live-stream-heavy sources" but no primary detail was obtained.
- Whether Twitch Auto Clips has reached open beta/GA by Nov 2026 was not confirmed.

## 3. What layout automation exists (facecam detection, speaker tracking, auto reframing, HUD-safe crops)?

### Takeaway
Layout automation for gaming is the weakest-documented area. Talking-head tools do face/speaker tracking; gaming tools offer split layouts (facecam on top, gameplay below) but often rely on manual crop per clip. No tool was found advertising HUD/minimap-aware "gameplay-safe" cropping.

### Cited Findings
- [vendor] Eklipse: cropping is "AI-framed, with manual control available"; StreamLadder cropping is described (by Eklipse) as "manual, one clip at a time" — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- [independent, secondhand] Eklipse's editor "can crop out the facecam" (listed as a weakness) — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- [competitor/aggregator] Choppity is described as having "facecam-aware tracking" for uploaded recordings, but "less precise for fast competitive titles" — [Kompozy roundup](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026)
- [vendor] StreamLadder's product set: ClipEditor (templates), MontageMaker, EmoteMaker, downloader, ClipGPT, Content Publisher; mobile editor — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/) and [StreamLadder blog](https://streamladder.com/blog/introducing-clipgpt-quickly-create-clips-from-your-streams)
- [platform] Twitch says it is "exploring" auto-cropping and trimming for clips; Dual Format streaming (simultaneous horizontal + vertical, with full-screen vertical or split view on mobile) rolled out from June 2026 — [Twitch blog](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/); [Tubefilter](https://www.tubefilter.com/2026/06/01/twitch-twitchcon-europe-rotterdamn-vertical-horizontal-dual-format-stream/)
- [platform] YouTube also announced simultaneous horizontal + vertical live broadcasting (Sept 2025) — [TechCrunch](https://techcrunch.com/2025/09/20/updates-to-studio-youtube-live-new-gen-ai-tools-and-everything-else-announced-at-made-on-youtube/)
- [open source] clipsmith detects the webcam rectangle with an OpenCV Haar face cascade, caches it, and renders 1080x1920 with modes center / webcam / stacked (webcam on top 40% = 768 px, gameplay 1152 px) / none; falls back to center crop — [clipsmith on GitHub](https://github.com/ricardogr07/clipsmith)

### Inferences
- The de facto gaming template is a stacked split (facecam top, gameplay bottom) with captions near the seam; the facecam rect is usually static per stream, so detecting it once per VOD (as clipsmith does) is sufficient.
- Because platforms now let streamers broadcast a native vertical feed (Twitch Dual Format, YouTube), streamer-authored vertical layouts will increasingly be available as a source, reducing the need for reframing for those channels.
- HUD-aware cropping (keeping minimap/wanted level/kill feed) appears unaddressed — a possible differentiator.

### Gaps
- No primary documentation was retrieved on OpusClip ReframeAnything/speaker tracking, Vizard/Klap reframing, or StreamLadder's automatic facecam detection; reviews consulted did not cover reframing quality on gameplay.
- No source found on any tool preserving HUD elements deliberately.

## 4. What caption styles and "viral templates" ship as defaults?

### Takeaway
The market standard is animated word-by-word ("karaoke") captions in a bold uppercase font with active-word colour highlight, optional auto-emoji and keyword emphasis — the "Hormozi" and "Beast" looks. Submagic is regarded as the deepest caption library; clipping tools ship roughly 10-15 presets.

### Cited Findings
- [vendor] Submagic organises themes into categories including Speakers, Emoji and Trend themes — [Submagic help center](https://care.submagic.co/en/article/what-are-themes-and-themes-categories-1pv8wvz/); it markets multiple "Hormozi" styles — [Submagic blog](https://www.submagic.co/blog/how-to-make-alex-hormozi-captions)
- [aggregator] The generic "Hormozi" recipe: bold uppercase font such as Montserrat Black, word-by-word animation, active word highlighted in yellow or green — [Fluxnote guide](https://fluxnote.io/guides/how-to-make-alex-hormozi-captions)
- [vendor] OpusClip describes animated caption templates, emoji and keyword highlighting, caption editor and custom fonts — [OpusClip blog](https://www.opus.pro/blog/best-caption-presets-styles-boost-retention); its Karaoke preset highlights words as spoken — [BIGVU review](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/) [competitor]
- [independent, secondhand] OpusClip captions: about 95-97% accuracy on clean audio, 20+ languages, 10+ animated styles; Eklipse captions draw Trustpilot complaints for inconsistency, especially non-English — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [aggregator] Vizard and Klap each ship roughly 12-15 caption presets, about tied on quality; Vizard transcription described as acceptable mainly in English and Spanish, Klap better across languages — [Klap vs Vizard comparison](https://bilt-kontent-engine.vercel.app/compare/klap-vs-vizard)
- [vendor, different product] OpenClip (not OpusClip) documents 40 presets with names such as Default, Mozi, Beast (comic-style, heavy stroke, pop animation), Karaoke (words light up as spoken) — each preset bundles font, colours, stroke, shadow, position, animation — [OpenClip docs](https://openclip.app/docs/clipping/captions/)
- [platform] Twitch began rolling out automatic captions on community clips (June 2026) with streamer-editable text, timing and style "for sound-off viewing" — [Twitch blog](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)
- [vendor] Eklipse "AI-Edit" adds memes/sound effects to gaming clips; "Pro Edits" sold as an add-on — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- [open source] clipsmith burns karaoke-style ASS subtitles via ffmpeg/libass (font, size, outline, position configurable), off by default — [clipsmith](https://github.com/ricardogr07/clipsmith)

### Inferences
- Best-practice default: 1-3 words on screen, uppercase heavy sans (Montserrat Black/Komika-like), thick stroke, active-word colour pop, light emoji, positioned centre or at the split seam. Gaming-specific additions are meme/SFX inserts (Eklipse AI-Edit).
- Non-English transcription quality is a repeated weak point (Eklipse, Vizard) — relevant for Portuguese-language streams.

### Gaps
- Exact default preset names/default selection in OpusClip, Submagic, Vizard, Klap, StreamLadder were not confirmed. Caption translation features per tool were not verified beyond OpusClip's dubbing (Pro) noted by BIGVU.
- Retention-lift numbers quoted for caption styles (e.g., "30-40%") are unsourced marketing and were excluded.

## 5. What do they generate with AI (titles, descriptions, hashtags, hooks, virality scores), and how reliable are scores?

### Takeaway
Virality scores are universal marketing features (OpusClip 1-100, StreamLadder ClipGPT, others) but the available evidence says they do not predict performance; reviewers recommend using them only as a triage order. Title/description generation exists but is thinly documented for gaming tools.

### Cited Findings
- [aggregator] OpusClip scores each clip 1-100 with sub-grades (Hook, Flow, Value, Trend); reviewers say the explanation is often generic — [Ssemble review](https://ssemble.com/blog/opus-clip-review-2026)
- [competitor test] In a 30-day paid test by ScaleReach (a competitor) over six videos / 76 clips: 47 publishable as-is (about 62%), 19 needed light edits (about 25%), 10 unusable (about 13%); **the best-performing clip had a score of 64 and the worst performer 87**; 4 of 11 AI B-roll inserts were contextually wrong — reported in [BIGVU review, Nov 2026](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/) (BIGVU is also a competitor)
- [independent, secondhand] "Creator reports say low-scoring clips often beat its 'winners'" — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- [vendor] StreamLadder ClipGPT returns up to 10 key moments per stream, each with a Virality Score — [StreamLadder blog](https://streamladder.com/blog/introducing-clipgpt-quickly-create-clips-from-your-streams)
- [vendor] Eklipse "Content Agent" makes "clips, captions and posts to TikTok for you"; "Posting Companion" (Premium Pro) picks, schedules and preps posts — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- [competitor] OpusClip feature set includes a "Viral Hook" template library, "Recipes" (saved edit setups), AI B-roll, Auto edit 4.0, dubbing — [BIGVU review](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/)
- [open source] clipsmith's LLM step takes up to 20 ranked candidates and returns picks with titles and reasons — [clipsmith](https://github.com/ricardogr07/clipsmith)

### Inferences
- A score that is not calibrated against real post-performance is a known credibility problem; a feedback loop using actual TikTok/Shorts metrics would be differentiating (only Eklipse claims a learning loop, and only from user flags).

### Gaps
- No documentation retrieved on hashtag/description generation specifics per tool, or on any tool feeding real post analytics back into scoring.
- No independent evaluation of StreamLadder's or Eklipse's scoring.

## 6. Auto-posting, scheduling and analytics

### Takeaway
Direct publishing to TikTok/Shorts/Reels is standard on paid tiers (OpusClip, Eklipse, StreamLadder, Klap), but reliability complaints are common, especially TikTok connection drops.

### Cited Findings
- [competitor] OpusClip posts directly to TikTok, YouTube Shorts and Instagram Reels; scheduler on Pro — [BIGVU review](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/)
- [independent, secondhand] OpusClip users report frequent TikTok connection drops and silent posting failures, with many downloading and posting manually; Eklipse's publisher draws fewer complaints but is "more basic" — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- [vendor] StreamLadder Content Publisher is a paid feature — [Eklipse vs StreamLadder](https://eklipse.gg/compare/eklipse-vs-streamladder/)
- [aggregator, conflicting] Klap: one source says direct publish/schedule to TikTok, YouTube, Instagram, LinkedIn — [Toolradar](https://toolradar.com/compare/submagic-vs-klap-ai); another groups Klap with export-only tools — [Faceless](https://faceless.so/alternatives/vizard)
- [competitor] Kompozy positions as post-clip repurposing/publishing to 9 platforms at $199/mo Starter — [Kompozy](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026)
- [platform] Twitch: from June 2026 a prioritised list of best clips per stream with one-click sharing to Stories; clips shareable "on and off Twitch" — [Twitch blog](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/)

### Gaps
- Analytics dashboards/feedback loops per tool were not documented in the sources retrieved.

## 7. Pricing and usage limits

### Takeaway
Gaming tools use flat subscriptions (roughly $5-27/mo); transcript tools use per-source-minute credits, which makes long streams expensive (a 3-hour VOD = 180 OpusClip credits, more than the Free or Starter monthly allowance). Free tiers are shrinking (Eklipse ended free clipping in June 2026).

### Cited Findings
| Tool | Reported pricing / limits | Source |
|---|---|---|
| Eklipse | "Free to sign up, paid to clip"; about $14.99/mo annual or $24.99/mo monthly; Premium Pro tier holds Live Clipping, Custom Highlights, Quality Max [vendor, Jul 2026] | [Eklipse](https://eklipse.gg/compare/eklipse-vs-streamladder/) |
| Eklipse (older/conflicting) | Free: 15 clips per stream, 720p, watermark, 14-day storage; Premium $19.99/mo, about $12.50/mo annual, 1080p60, 90-day storage [independent, Apr 2026 — predates free-tier removal]; free accounts get 3 Gameplay Intelligence clips [vendor] | [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/); [Eklipse blog](https://blog.eklipse.gg/streaming-tips/how-gameplay-intelligence-works-2.html) |
| OpusClip | Free 60 credits (watermark, exports expire after 3 days); Starter $15/mo 150 credits; Pro $29/mo or $14.50/mo billed $174/yr, 300 credits, 2 seats, scheduler, B-roll; Business custom with API; about 1 credit per source minute (checked Nov 5, 2026) [competitor] | [BIGVU](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/) |
| StreamLadder | Free manual editor (720p, no watermark, 200 MB upload); Silver $9/mo (editor); Gold $27/mo adds ClipGPT with credit quota; ClipGPT cap reported inconsistently as 10 or 30 clips per stream [independent]. Vendor blog describes ClipGPT tiers Casual/Consistent/Unlimited, up to 10 moments per stream, up to 3 streams/day. Annual about $6.90 / $13.25 per month [aggregator, via search snippet] | [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/); [StreamLadder](https://streamladder.com/blog/introducing-clipgpt-quickly-create-clips-from-your-streams); [Vidpros](https://vidpros.com/streamladder-review-2026/) |
| Sizzle.gg | Free unlimited streams 1080p with watermark; Starter $4.99/mo | [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/); [Eklipse vs Sizzle](https://eklipse.gg/compare/eklipse-vs-sizzle) |
| Medal.tv | Free; Premium $9.99/mo ($7.99 annual) [competitor] | [Kompozy](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026) |
| Powder | Free for individuals, capped exports; pro quote-only [competitor; status disputed] | [Kompozy](https://kompozy.io/roundups/best-ai-gaming-clip-generators-2026) |
| Framedrop | Conflicting: free 60 talking min + 240 gaming min, Starter $15, Pro $29; or Creator from $12 with 2 free exports/mo [aggregators] | [FutureTools](https://www.futuretools.io/tools/framedrop); [Eklipse vs Framedrop](https://blog.eklipse.gg/tools/eklipse-vs-framedrop.html) |
| Vizard | $20-30/mo depending on source [aggregators/competitors] | [Revid](https://www.revid.ai/blog/submagic-alternatives); [Faceless](https://faceless.so/alternatives/vizard) |
| Klap | Starter $23, Pro $63, Pro+ $151 per month [aggregator]; $29 Creator per another | [Toolradar](https://toolradar.com/compare/submagic-vs-klap-ai); [AI Prompts Hub](https://aipromptshub.co/creator/ai-shorts-tiktok-tools-2026) |
| Submagic | Starter $19/member/mo, or $12/mo billed yearly with 15 videos/mo | [Toolradar](https://toolradar.com/compare/submagic-vs-vizard); [Revid](https://www.revid.ai/blog/submagic-alternatives) |
| Munch (now "Munch Studio") | From $38/mo; or Pro $49 / Elite $79 / Max $99 | [Vidpros](https://vidpros.com/munch-ai-review/); [SendShort](https://sendshort.ai/compare/munch-vs-sendshort/) |
| 2short.ai | Lite $9.90 / Pro $19.90 / Premium $49.90 (2025) or Starter $13 / Pro $23 / Business $39 (2026) | [Toolkitly](https://toolkitly.com/compare-ai-tools/353-315/347/crayo-ai-vs-2short-ai); [Toolmage](https://www.toolmage.com/en/compare/2shortai-vs-crayo/) |
| Crayo | Essential $19 / Clipper $39 / Pro $79 per month (2025 listing) | [Toolkitly](https://toolkitly.com/compare-ai-tools/353-315/347/crayo-ai-vs-2short-ai) |
| Spikes Studio | From $33/mo; has Twitch integration and multi-language support [competitor] | [SendShort](https://sendshort.ai/compare/spikes-studio-vs-sendshort/) |
| NexusClips | About $15-20/mo, pricing "not stabilised" | [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/) |

### Inferences
- Credit-per-minute pricing structurally disadvantages 3-8 hour streams; flat or per-stream pricing is what gaming streamers expect.
- ClipGPT and Eklipse both cap output at about 10-15 clips per stream — the market treats roughly 10 as the useful number.

### Gaps
- Official pricing pages were not directly verified for any tool; StreamLadder and Eklipse reportedly hide pricing behind login/region detection.

## 8. What do independent reviews and user complaints say?

### Takeaway
Recurring complaints: missed buildup and non-kill moments (event tools), late/mistimed cuts on gameplay (transcript tools), slow or stuck processing, unreliable auto-posting, clunky UI, facecam cropped out, weak non-English captions, and billing/credit opacity. Primary Reddit threads were not retrievable; evidence is Trustpilot/G2 summaries relayed by small review blogs.

### Cited Findings
- Eklipse: Trustpilot about 4.3/5 over 800+ reviews, flagged by Trustpilot for possibly non-compliant review solicitation; complaints of "genuinely clunky" interface, slow processing, AI missing buildup, misclassified events — [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- Eklipse "will sometimes miss hype moments that don't involve a kill" (point attributed to StreamLadder's comparison page and conceded by Eklipse) — [Eklipse blog](https://blog.eklipse.gg/tools/ai-twitch-clip-generator-2.html)
- OpusClip: Trustpilot about 4.0-4.1/5 over about 300 reviews with about 22% one-star (processing failures, hidden credit mechanics, cancellation difficulty); G2 about 4.6/5; "gaming feedback is consistently negative"; Unkoa Marketing (Feb 2026) marks gaming/streaming as unsupported — [Ssemble review](https://ssemble.com/blog/opus-clip-review-2026); [Two Average Gamers](https://www.twoaveragegamers.com/eklipse-vs-opusclip-head-to-head-for-gaming-streamers-2026/)
- OpusClip: failed tasks do not always refund credits; non-enterprise user data may be used to improve models; captions slip with accents and have spelling errors; clip endings awkward — [Ssemble](https://ssemble.com/blog/opus-clip-review-2026); [BIGVU](https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/)
- StreamLadder: a Reddit thread titled "StreamLadder Just Priced Out Normal Streamers" is cited as reflecting anger at ClipGPT being locked to the $27 Gold tier with quotas; 200 MB free upload limit too small for full streams — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- Sizzle: slow (up to 4 h), basic editing — [Two Average Gamers](https://www.twoaveragegamers.com/best-ai-clip-detection-tools-for-streamers-2026/)
- Vizard: transcription weak outside English/Spanish — [Klap vs Vizard](https://bilt-kontent-engine.vercel.app/compare/klap-vs-vizard)

### Inferences
- User tolerance: roughly 60-80% usable clips is the current norm; users still expect to review a queue rather than trust full autopilot.

### Gaps
- No first-person Reddit (r/Twitch, r/NewTubers) threads or YouTube review transcripts were retrieved; search did not surface them. G2 pages were not opened.
- No user-review evidence found for Crayo, 2short.ai, Munch, Spikes Studio, Framedrop, Klap on gaming content.

## 9. Native platform tools (Twitch, Kick, YouTube)

### Takeaway
Twitch and YouTube are both moving into automatic highlight generation, which threatens basic third-party clippers; Kick has no announced native auto/vertical clipping found, and is served by third parties.

### Cited Findings
- Twitch (May 30, 2026): Auto Clips (chat activity, vocal inflection, on-screen events; captioned; "Twitch Clip That" voice trigger; beta waitlist), automatic captions on clips, best-clips list in stream summary, auto-cropping/trimming "being explored", Dual Format streaming — [Twitch blog](https://blog.twitch.com/en/2026/05/30/everything-we-announced-at-twitchcon-rotterdam-2026/); [Engadget](https://engadget.com/2184452/twitch-creators-will-soon-be-able-to-stream-in-horizontal-and-vertical-formats-simultaneously)
- YouTube (announced Sept 2025 at Made on YouTube): "AI highlights" automatically pick the best moments from a livestream and turn them into Shorts — [TechCrunch](https://techcrunch.com/2025/09/20/updates-to-studio-youtube-live-new-gen-ai-tools-and-everything-else-announced-at-made-on-youtube/); drafts appear in YouTube Studio after the stream for creator review, rollout gradual and not available to all creators — [LiveReacting guide](https://blog.livereacting.com/youtube-live-features-everything-creators-need-to-know/)
- Kick: Eklipse claims Kick's native clips are horizontal and that it processes Kick VODs with the same engine as Twitch — [Eklipse Kick page](https://eklipse.gg/features/kick-clips); [Eklipse blog](https://blog.eklipse.gg/streaming-tips/how-gameplay-intelligence-works-2.html); Streamlabs Cross Clip added Kick clip support for vertical conversion — [Streamlabs](https://streamlabs.com/ar-sa/content-hub/post/streamlabs-cross-clip-kick-integration); a vendor blog argues Kick is underserved by major clippers — [AutoClip](https://autoclip.dev/blog/kick-streamers-underserved-clip-niche-2026)

### Gaps
- No official Kick source on native clip features was found. No official YouTube Help page confirming AI highlights availability in late 2026. Twitch Auto Clips current rollout status unverified.

## 10. Open-source projects and techniques

### Takeaway
Open-source auto-clippers exist but are small hobby projects (single-digit stars). They converge on the same pipeline: download VOD + chat replay, Whisper transcription, chat-density candidate ranking, LLM selection/titling, ffmpeg vertical render with ASS karaoke captions.

### Cited Findings
- clipsmith (MIT, 1 star, 95 commits): twitch-dl download; OpenCV Haar cascade webcam detection; faster-whisper with word timestamps (Spanish); chat-downloader for chat replay; candidates from chat "density + clips + !clip" (existing community clips and !clip commands as signals); up to 20 candidates sent to an LLM (Anthropic/OpenAI/Ollama) returning picks with titles and reasons; 15-30 s clips; ffmpeg + libass; stacked layout; FastAPI + Next.js review dashboard — [GitHub](https://github.com/ricardogr07/clipsmith)
- VodAutoClipper (GPL-3.0, 5 stars): audio transcription (openai-whisper, optional faster-whisper) + chat activity + OpenAI LLM (supports fine-tuned model); speaker labelling by average pitch threshold; about 1 hour processing on an RTX 2060 — [GitHub mirror](https://gh.r-mj.com/wAIfu-DEV/VodAutoClipper)
- Auto-clipper (bendawg2010): local, game-specific detection plus Whisper trigger-phrase detection (snippet-level, not opened) — [GitHub](https://github.com/bendawg2010/Auto-clipper)
- HotClip (AGPL-3.0): vertical clips, dynamic captions and covers from long videos and livestream VODs, transcript-based selection (snippet-level) — [Gitee mirror](https://gitee.com/xiaohaohu/hotclip)
- Other repos surfaced but not inspected: [nirvagold/stream-clipper](https://github.com/nirvagold/stream-clipper), [mipacd/auto-clip-tool](https://github.com/mipacd/auto-clip-tool)
- OpusClip's published chat-spike method (10 s buckets, per-stream baseline, multiple-of-baseline threshold, 30 s backdating, emote spam counts) is the most explicit public description of chat-velocity scoring — [OpusClip](https://www.opus.pro/mcp/inspiration/clip-the-moments-your-live-chat-exploded)

### Inferences
- A notable cheap signal used by clipsmith and absent from commercial marketing: viewer-created clips and "!clip" chat commands as ground-truth-like markers of interesting moments.
- No open-source project found does game-state vision (kill feed OCR) or real-time processing; those remain commercial-only.

### Gaps
- Star counts, activity and licences for the uninspected repos are unknown; no widely adopted (hundreds+ stars) streamer-specific open-source clipper was identified in this search, though one may exist.
