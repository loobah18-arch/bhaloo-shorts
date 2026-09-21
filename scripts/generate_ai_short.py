#!/usr/bin/env python3
"""
🎬 Automated Viral Shorts Engine for Bhaloo Shorts
Generates high-CTR 15-30 second YouTube Shorts, Instagram Reels, and Facebook videos.

Features:
1. AI Model Script & Scene Director (calls Groq/Gemini/OpenRouter via llm_call.py with procedural fallback).
2. AI Video Generator (ai_video_generator.py) synthesizes 9:16 vertical video scenes matching AI directions.
3. Neural voiceover narration (edge-tts) with precise audio boundary alignment.
4. Dynamic high-contrast animated subtitles (neon yellow active highlights).
5. Automatic catalog rotation & history tracking (tracker/ai_shorts_history.json).
"""

import os
import re
import sys
import json
import time
import random
import shutil
import asyncio
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add scripts directory to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    import edge_tts
except ImportError:
    edge_tts = None

import llm_call
from ai_video_generator import generate_ai_video_track

OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TRACKER_DIR = REPO_ROOT / "tracker"
TRACKER_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = TRACKER_DIR / "ai_shorts_history.json"

VIRAL_CATALOG = [
    # Category 1: Mega-Construction & Machines (High Watch-Time & Oddly Satisfying)
    {
        "id": "construction_bridge_crusher",
        "niche": "construction",
        "title": "This Machine Demolishes Bridges in 60 Seconds",
        "badge": "MEGA MACHINES 🏗️",
        "hook": "Watch what happens when an 80-ton hydraulic crusher attacks a concrete bridge.",
        "script": "Watch how this 80-ton hydraulic monster destroys a reinforced concrete bridge in under a minute. One bite delivers over 400 tons of crushing force, chewing through thick rebar like toothpicks. The precision engineering allows it to dismantle structures without damaging surrounding roads. Would you trust this machine near your house?",
        "tags": ["construction", "megamachines", "satisfying", "engineering", "shorts", "heavyequipment"],
        "visual_prompts": [
            "Massive 80-ton hydraulic excavator crusher jaws snapping concrete bridge pillar, dust billowing, 8k vertical 9:16",
            "Macro close-up of titanium jaws slicing through thick steel rebar with sparks flying, 8k vertical 9:16",
            "Wide drone shot of the entire demolition site with dust clouds, 8k vertical 9:16",
            "Satisfying slow-motion shot of clean crumbled concrete piles, 8k vertical 9:16"
        ]
    },
    {
        "id": "construction_spider_excavator",
        "niche": "construction",
        "title": "The Walking Excavator That Climbs Mountain Cliffs",
        "badge": "EXTREME ENGINEERING 🧗",
        "hook": "This spider excavator can walk up 75-degree sheer cliffs where regular machines would plunge to death.",
        "script": "This isn't sci-fi. It's an all-terrain spider walking excavator designed to scale sheer 75-degree mountain cliffs. With four independent hydraulic claw legs, it anchors into solid rock and digs where no normal machine could ever reach. Operators risk their lives perched thousands of feet above the valley floor!",
        "tags": ["engineering", "spiderexcavator", "extreme", "mountains", "satisfying", "shorts"],
        "visual_prompts": [
            "Futuristic spider walking excavator with 4 hydraulic legs perched on sheer 75-degree alpine cliff, 8k vertical 9:16",
            "Extreme close-up of hydraulic claw anchoring into solid mountain rock, 8k vertical 9:16",
            "Dizzying drone camera circling the excavator perched high above clouds, 8k vertical 9:16",
            "Excavator bucket clearing rock on cliff edge with dust falling down the abyss, 8k vertical 9:16"
        ]
    },
    {
        "id": "construction_3d_house_printing",
        "niche": "construction",
        "title": "Satisfying 3D Robot That Prints a House in 24 Hours",
        "badge": "FUTURE TECH 🤖",
        "hook": "This robotic arm is 3D printing a complete concrete house in less than 24 hours.",
        "script": "Watch how this giant robotic arm lays down perfect, smooth ribbons of self-curing concrete layer by layer. It operates non-stop without human fatigue, building walls with millimeter precision and zero material waste. In just 24 hours, an entire hurricane-proof home is ready. Would you live in a 3D-printed house?",
        "tags": ["3dprinting", "robotics", "architecture", "satisfying", "shorts", "future"],
        "visual_prompts": [
            "Robotic 3D printer nozzle extruding ultra-smooth ribbons of quick-curing concrete, curved modern architectural wall, 8k vertical 9:16",
            "Satisfying macro shot of perfectly layered concrete texture in warm daylight, 8k vertical 9:16",
            "Wide architectural shot of completed modern 3D printed concrete villa, 8k vertical 9:16",
            "Night view of illuminated 3D printed luxury house with minimalist lighting, 8k vertical 9:16"
        ]
    },
    # Category 2: Emotional & Cute Children Playing with Dogs (Viral Shares & Likes)
    {
        "id": "dog_golden_retriever_bodyguard",
        "niche": "dogs",
        "title": "A Golden Retriever's Secret Job Around Babies",
        "badge": "PURE LOYALTY 🐕",
        "hook": "Watch this Golden Retriever step in the exact second the toddler crawls toward the stairs.",
        "script": "Watch this Golden Retriever step in the moment the toddler crawls toward the step. He refuses to move, acting like a soft furry barrier until mom arrives. He gently nudges the baby back with his nose, and the baby giggles and hugs his neck. Dogs truly are our greatest guardians!",
        "tags": ["goldenretriever", "cute", "dogs", "babyanddog", "wholesome", "shorts"],
        "visual_prompts": [
            "Fluffy golden retriever gently lying down to block crawling toddler from stairs in sunlit living room, 8k vertical 9:16",
            "Toddler with giggling smile hugging the golden retriever around the neck, warm lighting, 8k vertical 9:16",
            "Close-up of golden retriever softly nudging toddler back to play mat, 8k vertical 9:16",
            "Golden retriever and baby sleeping side-by-side peacefully on cozy rug, 8k vertical 9:16"
        ]
    },
    {
        "id": "dog_husky_teaches_baby_talk",
        "niche": "dogs",
        "title": "When a Husky Teaches a Baby How to Talk",
        "badge": "FUNNY DUET 🐺",
        "hook": "The baby tried to say his first word, but the family Husky had other plans.",
        "script": "The baby was about to say his first word, but the family Husky had other plans. Instead of mama or dada, the dog let out a gentle howling sound, and the baby copied it instantly! Now the two best friends only communicate in gentle howling duets. Have you ever heard anything this adorable?",
        "tags": ["husky", "cutedogs", "funny", "babies", "duet", "shorts", "viral"],
        "visual_prompts": [
            "Fluffy Siberian husky sitting face-to-face on carpet with laughing baby in overalls, 8k vertical 9:16",
            "Husky softly howling with head tilted back playfully, 8k vertical 9:16",
            "Baby with toothless smile attempting to howl back at the husky, 8k vertical 9:16",
            "Husky gently resting head on baby lap while baby pats dog ears, 8k vertical 9:16"
        ]
    },
    {
        "id": "dog_newfoundland_gentle_giant",
        "niche": "dogs",
        "title": "The World's Most Patient 150lb Babysitter",
        "badge": "GENTLE GIANT 🐾",
        "hook": "This dog weighs 150 pounds, but around this little girl he turns into a teddy bear.",
        "script": "This gentle giant weighs over 150 pounds, but around this tiny two-year-old girl, he turns into the softest teddy bear in the world. Look at how patiently he sits while she places a crown of yellow daisies onto his giant head. He blinks slowly and wags his tail with pure love. We don't deserve dogs!",
        "tags": ["newfoundland", "giantdog", "gentlegiant", "wholesome", "shorts"],
        "visual_prompts": [
            "Massive 150lb black Newfoundland dog lying calmly on lush green lawn, 8k vertical 9:16",
            "Tiny 2-year-old toddler girl placing a flower crown of daisies onto the giant dog head, 8k vertical 9:16",
            "Close-up of giant dog soft brown eyes blinking patiently with love, 8k vertical 9:16",
            "Toddler leaning entire body against the fluffy dog side like a living pillow, 8k vertical 9:16"
        ]
    }
]


def log(msg: str):
    print(f"[bhaloo_shorts] {msg}", flush=True)


def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"generated_shorts": []}


def save_history(data: dict):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log(f"⚠️ Failed to save history: {e}")


def select_topic(requested_topic: str = None, niche: str = None) -> dict:
    """Selects from requested topic, or rotates through un-generated catalog items."""
    if requested_topic:
        log(f"🎯 Custom topic requested: '{requested_topic}'")
        return generate_ai_script_from_topic(requested_topic, niche=niche)

    history = load_history()
    done_ids = {item.get("id") for item in history.get("generated_shorts", [])}

    candidates = VIRAL_CATALOG
    if niche:
        candidates = [c for c in VIRAL_CATALOG if c.get("niche") == niche] or VIRAL_CATALOG

    unseen = [c for c in candidates if c.get("id") not in done_ids]
    if unseen:
        chosen = unseen[0]
        log(f"🎬 Selected ungenerated catalog topic: '{chosen.get('title')}' [{chosen.get('niche')}]")
        return chosen

    # If all catalog items were completed, pick random or generate fresh
    chosen = random.choice(candidates)
    log(f"🔄 Rotating catalog topic: '{chosen.get('title')}'")
    return chosen


def generate_ai_script_from_topic(topic: str, niche: str = None) -> dict:
    """Uses llm_call to have the AI model write a viral script and visual prompts."""
    system_prompt = (
        "You are an elite YouTube Shorts and Instagram Reels creator specializing in high-CTR viral videos. "
        "Write a 15-25 second explosive Short (EXACTLY 50-75 words) and 4-5 photorealistic 9:16 visual scene prompts. "
        "Respond ONLY with a JSON object: "
        "{\"title\":\"...\", \"badge\":\"...\", \"hook\":\"...\", \"script\":\"...\", \"tags\":[\"...\"], \"visual_prompts\":[\"Scene 1: ...\", \"Scene 2: ...\", \"Scene 3: ...\", \"Scene 4: ...\"]}"
    )
    user_prompt = f"Topic: '{topic}'. Niche: '{niche or 'viral'}'. Make it high-retention, emotionally compelling or oddly satisfying."

    try:
        raw_json = llm_call.call_llm(system=system_prompt, user=user_prompt, json_mode=True, max_tokens=600)
        data = json.loads(raw_json)
        if "visual_prompts" not in data or not data["visual_prompts"]:
            data["visual_prompts"] = [
                f"Cinematic dramatic establishing shot of {topic}, 8k photorealistic, 9:16 vertical",
                f"Intense dynamic action shot of {topic}, cinematic lighting, 8k vertical",
                f"Macro detailed close-up shot of {topic}, photorealistic texture, 9:16 vertical",
                f"Satisfying concluding visual of {topic}, golden hour atmosphere, 9:16 vertical"
            ]
        data["id"] = re.sub(r"[^\w]", "_", topic).lower()[:30]
        return data
    except Exception as e:
        log(f"⚠️ LLM call failed or unavailable ({e}), using procedural synthesis...")
        return {
            "id": re.sub(r"[^\w]", "_", topic).lower()[:30],
            "title": topic.title(),
            "badge": "VIRAL SHORTS 🔥",
            "hook": f"You won't believe what happens when {topic}.",
            "script": (
                f"Have you ever seen anything like this? Watch closely as {topic} unfolds in ways you never expected. "
                f"Every single detail reveals an incredible level of precision and wonder. "
                f"Drop a like if this amazed you and subscribe for more daily mind-blowing shorts!"
            ),
            "tags": ["viral", "shorts", "satisfying", "trending", "reels"],
            "visual_prompts": [
                f"High-impact opening shot of {topic}, 8k photorealistic, 9:16 vertical",
                f"Close-up action detail of {topic}, cinematic lighting, 9:16 vertical",
                f"Dramatic angle showing scale of {topic}, 8k vertical",
                f"Satisfying concluding shot of {topic}, warm cinematic glow, 9:16 vertical"
            ]
        }


async def generate_speech(script_text: str, audio_path: Path, voice: str = "en-US-ChristopherNeural") -> list:
    """Generates Edge-TTS neural narration and extracts sentence timings."""
    if not edge_tts:
        raise RuntimeError("edge-tts library is required for speech synthesis.")

    log(f"🎙️ Generating voiceover with voice: '{voice}'...")
    communicate = edge_tts.Communicate(script_text, voice)
    sentences = []
    audio_data = bytearray()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "SentenceBoundary":
            start_s = chunk["offset"] / 10_000_000.0
            dur_s = chunk["duration"] / 10_000_000.0
            sentences.append({"text": chunk["text"], "start": start_s, "end": start_s + dur_s})

    with open(audio_path, "wb") as f:
        f.write(audio_data)

    return sentences


def get_media_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 20.0


def create_word_timestamps(sentences: list) -> list:
    words = []
    for s in sentences:
        s_text = s["text"].strip()
        s_start = s["start"]
        s_end = s["end"]
        raw_words = [w for w in re.split(r"\s+", s_text) if w]
        if not raw_words:
            continue
        step = (s_end - s_start) / len(raw_words)
        for i, rw in enumerate(raw_words):
            clean = re.sub(r"[^\w]", "", rw).upper()
            if not clean:
                continue
            w_start = s_start + (i * step)
            w_end = w_start + step
            words.append({"word": clean, "start": w_start, "end": w_end})
    return words


def generate_karaoke_subtitles(words: list, output_ass_path: Path):
    """Generates TikTok/Shorts-style high-impact animated ASS subtitles with yellow active word highlight."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ShortsDefault, DejaVu Sans, 74, &H00FFFFFF&, &H000000FF&, &H00000000&, &H80000000&, 1, 0, 0, 0, 100, 100, 1, 0, 1, 4.5, 2.0, 2, 60, 60, 480, 1
Style: ShortsActive, DejaVu Sans, 78, &H0000FFFF&, &H000000FF&, &H00000000&, &H80000000&, 1, 0, 0, 0, 100, 100, 1, 0, 1, 5.5, 3.0, 2, 60, 60, 480, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def to_ass_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h:d}:{m:02d}:{s:05.2f}"

    lines = []
    # Group 3 words per subtitle card for fast mobile readability
    for i in range(0, len(words), 3):
        group = words[i:i+3]
        g_start = group[0]["start"]
        g_end = group[-1]["end"]

        for active_idx, active_word in enumerate(group):
            w_start = active_word["start"]
            w_end = active_word["end"]
            chunk = []
            for j, gw in enumerate(group):
                if j == active_idx:
                    chunk.append(r"{\rShortsActive}" + gw["word"] + r"{\rShortsDefault}")
                else:
                    chunk.append(gw["word"])
            line_text = " ".join(chunk)
            lines.append(f"Dialogue: 0,{to_ass_time(w_start)},{to_ass_time(w_end)},ShortsDefault,,0,0,0,,{line_text}")

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines))


def render_short_video(
    video_track_path: Path,
    audio_path: Path,
    ass_subtitle_path: Path,
    title: str,
    badge_text: str,
    output_final_path: Path
):
    """Composites AI video track, voiceover audio, and karaoke subtitles into final 1080x1920 Short."""
    clean_badge = re.sub(r"[^A-Za-z0-9\s\(\)\-\.\,\!\?]", "", badge_text or title).strip().upper()[:26]
    badge_display = f"BHALOO SHORTS • {clean_badge}"

    ass_esc = str(ass_subtitle_path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")

    # Font path detection
    font_opt = "font='DejaVu Sans'"
    for cand in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/system/fonts/Roboto-Bold.ttf", "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]:
        if os.path.exists(cand):
            font_opt = f"fontfile='{cand}'"
            break

    video_filters = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "eq=contrast=1.06:brightness=-0.02:saturation=1.12,unsharp=3:3:0.4[comp];"
        f"[comp]drawbox=x=40:y=130:w=1000:h=90:color=black@0.75:t=fill,"
        f"drawtext=text='{badge_display}':fontsize=36:fontcolor=white:{font_opt}:x=(w-text_w)/2:y=158,"
        f"ass='{ass_esc}'[vfinal]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_track_path),
        "-i", str(audio_path),
        "-filter_complex", video_filters,
        "-map", "[vfinal]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_final_path)
    ]
    subprocess.run(cmd, check=True)


def run_pipeline(
    topic: str = None,
    niche: str = None,
    voice: str = "en-US-ChristopherNeural",
    dry_run: bool = False
) -> Path:
    """Executes the complete AI Short creation workflow."""
    log("=" * 65)
    log("🚀 STARTING AUTOMATED VIRAL SHORTS GENERATOR (Bhaloo Shorts)")
    log("=" * 65)

    # 1. Select Topic & Generate Script via AI Model
    concept = select_topic(topic, niche=niche)
    concept_id = concept.get("id", f"short_{int(time.time())}")
    title = concept.get("title", "Viral Short")
    badge_text = concept.get("badge", "VIRAL SHORTS")
    script_text = concept.get("script", "")
    visual_prompts = concept.get("visual_prompts", [])

    log(f"📖 Topic: {title} [{concept.get('niche', 'general')}]")
    log(f"🎙️ Script ({len(script_text.split())} words): \"{script_text[:85]}...\"")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_path = OUTPUT_DIR / f"{concept_id}_audio_{timestamp}.mp3"
    subtitles_path = OUTPUT_DIR / f"{concept_id}_subtitles_{timestamp}.ass"
    video_track_path = OUTPUT_DIR / f"{concept_id}_video_track_{timestamp}.mp4"
    final_short_path = OUTPUT_DIR / f"bhaloo_short_{concept_id}_{timestamp}.mp4"

    # 2. Audio Generation
    sentences = asyncio.run(generate_speech(script_text, audio_path, voice=voice))
    duration = get_media_duration(audio_path)
    log(f"⏱️ Audio narration duration: {duration:.2f} seconds")

    # 3. Dynamic Subtitles
    words = create_word_timestamps(sentences)
    generate_karaoke_subtitles(words, subtitles_path)

    # 4. AI Video Generator directed by AI Model
    log(f"🤖 Directing AI Video Generator with {len(visual_prompts)} visual prompts...")
    ok = generate_ai_video_track(
        visual_prompts=visual_prompts,
        total_duration=duration,
        output_video_path=video_track_path,
        title=title,
        script_text=script_text,
        niche=concept.get("niche", niche)
    )
    if not ok or not video_track_path.exists():
        raise RuntimeError("AI Video Generator failed to assemble video track.")

    # 5. Composite Final Video
    log("🎨 Compositing 1080x1920 Short with subtitles and visual grade...")
    render_short_video(
        video_track_path=video_track_path,
        audio_path=audio_path,
        ass_subtitle_path=subtitles_path,
        title=title,
        badge_text=badge_text,
        output_final_path=final_short_path
    )

    # 6. Save in History
    history = load_history()
    history["generated_shorts"].append({
        "id": concept_id,
        "title": title,
        "niche": concept.get("niche", "general"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_path": str(final_short_path),
        "duration_sec": round(duration, 2)
    })
    save_history(history)

    # Cleanup temp intermediates
    for p in [audio_path, subtitles_path, video_track_path]:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    log("=" * 65)
    log(f"✅ BHALOO SHORT CREATION COMPLETE! Output: {final_short_path}")
    log("=" * 65)
    return final_short_path


def main():
    parser = argparse.ArgumentParser(description="Automated Viral Shorts Engine (Bhaloo Shorts)")
    parser.add_argument("--topic", type=str, default=None, help="Specific topic or prompt to generate")
    parser.add_argument("--niche", type=str, choices=["construction", "dogs", "curiosity"], default=None, help="Content niche filter")
    parser.add_argument("--voice", type=str, default="en-US-ChristopherNeural", help="Edge-TTS voice")
    parser.add_argument("--dry-run", action="store_true", help="Generate locally without uploading")
    parser.add_argument("--list", action="store_true", help="List catalog topics and generation history")
    args = parser.parse_args()

    if args.list:
        print("\n🎬 VIRAL SHORTS CATALOG:")
        for c in VIRAL_CATALOG:
            print(f"  • [{c['niche'].upper()}] {c['title']}")
        hist = load_history()
        print(f"\n📜 GENERATION HISTORY ({len(hist.get('generated_shorts', []))} items):")
        for h in hist.get("generated_shorts", [])[-5:]:
            print(f"  • {h.get('title')} ({h.get('timestamp')})")
        return

    run_pipeline(
        topic=args.topic,
        niche=args.niche,
        voice=args.voice,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
