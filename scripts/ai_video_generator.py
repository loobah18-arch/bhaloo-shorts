#!/usr/bin/env python3
"""
🎬 AI Video Generator for Bhaloo Shorts
Generates REAL, HIGH-QUALITY 9:16 VERTICAL MOTION VIDEOS directed by the AI model.

No still images. No photo slideshows with Ken Burns zoom.
Every scene is an authentic moving MP4 video clip with 24-30fps motion.

Two-Tier Motion Video Architecture:
1. Tier 1: True AI Generative Video (Text-to-Video Diffusion via Lightricks LTX-Video / Hugging Face ZeroGPU).
   Produces authentic 30fps AI-generated motion video clips with physical movement.
2. Tier 2: Real High-Definition Moving Stock Video Footage (Wikimedia Commons & Open Archive Video).
   Searches and slices genuine .webm / .mp4 video files (excavators, demolitions, dogs, toddlers).
"""

import os
import re
import sys
import time
import json
import random
import shutil
import urllib.parse
import urllib.request
import subprocess
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = WORKSPACE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = WORKSPACE_DIR / ".cache" / "ai_scenes"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# In-memory circuit breaker for external AI diffusion space
_DIFFUSION_SPACE_ACTIVE = True


def log(msg: str):
    print(f"[ai_video_generator] {msg}", flush=True)


def clean_prompt_for_video(prompt: str) -> str:
    """Cleans prompt for high-impact generative motion video."""
    cleaned = re.sub(r"^(scene\s*\d*[\s:\-–—\(\)\d\w]*:)", "", prompt, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'^["\']|["\']$', "", cleaned).strip()
    if not cleaned:
        cleaned = "cinematic atmospheric action scene, 4k fluid motion"
    return cleaned


clean_prompt_for_image_gen = clean_prompt_for_video


def extract_search_keywords(prompt: str, niche: str = "") -> list:
    """
    Intelligently extracts core subject nouns for video search,
    stripping conversational stop words (e.g. 'watch this', 'happens when').
    """
    p_lower = prompt.lower()
    keywords = []

    # Domain keyword mapping
    domain_map = [
        ("excavator", ["excavator", "digger"]),
        ("demolition", ["demolition", "building demolition"]),
        ("crusher", ["excavator", "demolition"]),
        ("bridge", ["bridge construction", "demolition"]),
        ("crane", ["construction crane", "crane"]),
        ("3d print", ["3d printing", "robotics"]),
        ("spider excavator", ["excavator", "walking excavator"]),
        ("golden retriever", ["golden retriever", "dog playing"]),
        ("puppy", ["dog puppy", "puppy playing"]),
        ("dog", ["dog playing", "dog park"]),
        ("toddler", ["baby playing", "toddler"]),
        ("robot", ["robot arm", "robotics"]),
    ]

    for key, terms in domain_map:
        if key in p_lower:
            keywords.extend(terms)

    # If niche is provided
    if niche == "construction" and not keywords:
        keywords = ["excavator", "demolition", "construction site"]
    elif niche == "dogs" and not keywords:
        keywords = ["dog playing", "golden retriever", "puppy"]

    # Fallback noun extraction
    if not keywords:
        stop_words = {
            "watch", "this", "what", "happens", "when", "second", "crawls", "toward",
            "stairs", "refuses", "move", "acting", "like", "soft", "furry", "barrier",
            "until", "arrives", "gently", "nudges", "baby", "back", "with", "nose",
            "giggles", "hugs", "neck", "dogs", "truly", "are", "greatest", "guardians",
            "giant", "monster", "reinforced", "concrete", "under", "minute", "chewing",
            "through", "thick", "precision", "engineering", "allows", "dismantle",
            "without", "damaging", "surrounding", "roads", "would", "trust", "near",
            "house", "vertical", "photorealistic", "cinematic", "scene", "shot", "detailed"
        }
        words = [w for w in re.sub(r"[^A-Za-z0-9\s]", "", prompt).split() if len(w) > 3 and w.lower() not in stop_words]
        if words:
            keywords = [words[0]]

    return list(dict.fromkeys(keywords)) if keywords else ["action"]


def format_motion_clip_to_vertical(
    input_video_path: str,
    output_clip_path: Path,
    target_duration: float
) -> bool:
    """
    Standardizes any video clip to 1080x1920 (9:16 vertical) @ 30fps with libx264,
    adjusting playback speed or looping to seamlessly match target_duration.
    """
    try:
        # Check source duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_video_path)
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True)
        src_dur = float(res.stdout.strip()) if res.returncode == 0 and res.stdout.strip() else 2.0
    except Exception:
        src_dur = 2.0

    # Calculate speed factor: if source is shorter than target, slow it down slightly (up to 1.5x) or loop
    speed_factor = max(0.65, min(1.5, target_duration / max(0.5, src_dur)))

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "3",
        "-i", str(input_video_path),
        "-t", f"{target_duration:.2f}",
        "-filter_complex", (
            f"[0:v]setpts={speed_factor:.3f}*PTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30[v]"
        ),
        "-map", "[v]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-an",
        str(output_clip_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_clip_path.exists() and output_clip_path.stat().st_size > 10000
    except Exception as e:
        log(f"   ⚠️ FFmpeg vertical formatting error: {e}")
        return False


def generate_ai_diffusion_clip(
    prompt: str,
    duration: float,
    output_clip_path: Path
) -> bool:
    """
    Tier 1: True AI Generative Video (Text-to-Video Diffusion).
    Calls Lightricks LTX-Video distilled model on Hugging Face ZeroGPU via gradio_client.
    Produces authentic 30fps generated video.
    """
    global _DIFFUSION_SPACE_ACTIVE
    if not _DIFFUSION_SPACE_ACTIVE:
        return False

    try:
        from gradio_client import Client
    except ImportError:
        log("   ℹ️ gradio_client not installed, skipping diffusion tier.")
        return False

    clean_p = clean_prompt_for_video(prompt)
    log(f"   🤖 [Tier 1: AI Diffusion Video] Submitting prompt: \"{clean_p[:60]}...\"")

    try:
        client = Client("Lightricks/ltx-video-distilled", verbose=False)
        res = client.predict(
            prompt=f"{clean_p}, high quality, cinematic fluid motion, 4k",
            negative_prompt="worst quality, static image, blurry, photo, still picture, distorted",
            input_image_filepath=None,
            input_video_filepath=None,
            height_ui=704,
            width_ui=512,
            mode="text-to-video",
            duration_ui=2,
            ui_frames_to_use=9,
            seed_ui=random.randint(1, 999999),
            randomize_seed=True,
            ui_guidance_scale=1.0,
            improve_texture_flag=True,
            api_name="/text_to_video"
        )

        if isinstance(res, (tuple, list)) and len(res) > 0:
            v_info = res[0]
            raw_path = v_info.get("video") if isinstance(v_info, dict) else str(v_info)
            if raw_path and os.path.exists(raw_path):
                ok = format_motion_clip_to_vertical(raw_path, output_clip_path, target_duration=duration)
                if ok:
                    log(f"   ✅ [Tier 1: AI Diffusion Video] Generated {duration:.1f}s moving video clip!")
                    return True
    except Exception as e:
        log(f"   ⚠️ Tier 1 diffusion notice ({e}), failing over to Tier 2 stock motion video...")
        # If connection or space is down, temporarily trip circuit breaker
        if "timeout" in str(e).lower() or "503" in str(e) or "queue" in str(e).lower():
            _DIFFUSION_SPACE_ACTIVE = False

    return False


def fetch_real_stock_video_clip(
    query_keyword: str,
    duration: float,
    output_clip_path: Path
) -> bool:
    """
    Tier 2: Real High-Definition Moving Stock Video Footage.
    Searches and downloads genuine WebM / MP4 video files from Wikimedia Commons Open Media with browser UA.
    Slices the segment and formats to 1080x1920 30fps vertical video.
    """
    log(f"   🎥 [Tier 2: Real Stock Video] Searching open video library for: '{query_keyword}'...")
    search_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(query_keyword)}%20filetype:video&srnamespace=6&srlimit=4&format=json"
    )

    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = data.get("query", {}).get("search", [])

        for item in results:
            title = item.get("title")
            if not title:
                continue

            info_url = (
                f"https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}"
                f"&prop=imageinfo&iiprop=url|mime|size&format=json"
            )
            i_req = urllib.request.Request(info_url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(i_req, timeout=10) as ir:
                i_data = json.loads(ir.read())

            pages = i_data.get("query", {}).get("pages", {})
            for _, p in pages.items():
                for info in p.get("imageinfo", []):
                    v_url = info.get("url")
                    mime = info.get("mime", "")
                    size = info.get("size", 0)

                    if v_url and ("video" in mime or v_url.endswith((".webm", ".mp4", ".ogv"))):
                        # Stream up to 15MB of the video file
                        raw_temp = CACHE_DIR / f"raw_stock_{int(time.time())}_{random.randint(100,999)}.webm"
                        d_req = urllib.request.Request(v_url, headers={"User-Agent": BROWSER_UA})
                        with urllib.request.urlopen(d_req, timeout=20) as d_resp, open(raw_temp, "wb") as out_f:
                            chunk = d_resp.read(12_000_000)
                            out_f.write(chunk)

                        if raw_temp.exists() and raw_temp.stat().st_size > 100_000:
                            # Slice a 3-second segment and format to vertical 1080x1920
                            start_seek = 2.0 if size > 5_000_000 else 0.5
                            slice_cmd = [
                                "ffmpeg", "-y",
                                "-ss", f"{start_seek:.1f}",
                                "-i", str(raw_temp),
                                "-t", f"{duration:.2f}",
                                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
                                "-c:v", "libx264",
                                "-preset", "ultrafast",
                                "-pix_fmt", "yuv420p",
                                "-crf", "20",
                                "-an",
                                str(output_clip_path)
                            ]
                            subprocess.run(slice_cmd, capture_output=True)
                            raw_temp.unlink(missing_ok=True)

                            if output_clip_path.exists() and output_clip_path.stat().st_size > 10000:
                                log(f"   ✅ [Tier 2: Real Stock Video] Formatted moving clip from: {title[:40]}...")
                                return True

    except Exception as e:
        log(f"   ⚠️ Tier 2 stock video notice: {e}")

    return False


def generate_motion_backdrop_clip(
    title: str,
    duration: float,
    output_clip_path: Path
) -> bool:
    """
    Emergency zero-network fallback: Generates an animated dynamic geometric motion backdrop
    with moving light ripples and particles (never a static photo).
    """
    fps = 30
    total_frames = int(duration * fps)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"gradients=s=1080x1920:c0=0x0b132b:c1=0x1c2541:d={duration}:speed=0.03",
        "-vf", (
            f"drawbox=x='(w-400)/2+sin(t*2)*80':y='(h-400)/2+cos(t*2)*80':w=400:h=400:color=white@0.05:t=fill,"
            f"drawtext=text='{title.upper()[:24]}':fontsize=48:fontcolor=white@0.85:x=(w-text_w)/2:y=(h-text_h)/2"
        ),
        "-t", f"{duration:.2f}",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_clip_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_clip_path.exists() and output_clip_path.stat().st_size > 1000
    except Exception as e:
        log(f"   ⚠️ Motion backdrop notice: {e}")
        return False


def get_or_generate_video_clip(
    prompt: str,
    duration: float,
    output_clip_path: Path,
    scene_idx: int = 0,
    niche: str = ""
) -> bool:
    """
    Acquires an authentic moving video clip:
    1. Try Tier 1: True AI Generative Video (LTX-Video Diffusion via Hugging Face ZeroGPU).
    2. Try Tier 2: Real High-Definition Moving Stock Video Footage (Wikimedia Commons Video).
    3. Emergency Fallback: Animated dynamic motion backdrop.
    """
    # 1. Tier 1: AI Diffusion Video (preferred for opening hook and peak action)
    if generate_ai_diffusion_clip(prompt, duration, output_clip_path):
        return True

    # 2. Tier 2: Real Stock Video Footage
    keywords = extract_search_keywords(prompt, niche=niche)
    for kw in keywords:
        if fetch_real_stock_video_clip(kw, duration, output_clip_path):
            return True

    # Fallback keyword by niche
    default_niche_kw = "demolition" if niche == "construction" else "dog playing"
    if fetch_real_stock_video_clip(default_niche_kw, duration, output_clip_path):
        return True

    # 3. Emergency Animated Motion Backdrop
    log("   ⚠️ Generating animated motion backdrop fallback...")
    return generate_motion_backdrop_clip("ACTION SCENE", duration, output_clip_path)


def generate_ai_video_track(
    visual_prompts: list,
    total_duration: float,
    output_video_path: Path,
    title: str = "Video Short",
    script_text: str = "",
    niche: str = ""
) -> bool:
    """
    Main entry point for generating the complete moving video track:
    1. Directs AI video generation and real stock video slicing for every scene.
    2. Ensures every scene is an actual moving MP4 video clip (no still photos).
    3. Stitches all clips into a seamless 1080x1920 30fps vertical video track matching the audio duration.
    """
    log("=" * 65)
    log(f"🎬 BHALOO REAL VIDEO ENGINE: Producing {total_duration:.1f}s video track for '{title}'")
    log("=" * 65)

    if not visual_prompts:
        visual_prompts = [
            f"Action shot of {title}, fluid motion",
            f"Close up detail of {title} in action",
            f"Wide angle dynamic movement of {title}"
        ]

    num_scenes = len(visual_prompts)
    scene_duration = round(total_duration / max(1, num_scenes), 2)
    if scene_duration < 2.5 and num_scenes > 3:
        num_scenes = max(3, int(total_duration // 3.0))
        visual_prompts = visual_prompts[:num_scenes]
        scene_duration = round(total_duration / num_scenes, 2)

    log(f"📽️ Generating {num_scenes} REAL MOVING SCENES (~{scene_duration:.2f}s each)...")

    scene_clips = []
    temp_files = []

    try:
        for idx, prompt_item in enumerate(visual_prompts):
            prompt_text = prompt_item if isinstance(prompt_item, str) else prompt_item.get("prompt", str(prompt_item))
            scene_num = idx + 1
            log(f"🎞️ Scene {scene_num}/{num_scenes}: \"{prompt_text[:60]}...\"")

            current_scene_dur = scene_duration
            if scene_num == num_scenes:
                current_scene_dur = max(1.5, total_duration - (scene_duration * (num_scenes - 1)))

            clip_path = CACHE_DIR / f"moving_scene_{scene_num}_{int(time.time())}_{random.randint(100,999)}.mp4"
            temp_files.append(clip_path)

            ok = get_or_generate_video_clip(
                prompt=prompt_text,
                duration=current_scene_dur,
                output_clip_path=clip_path,
                scene_idx=idx,
                niche=niche
            )

            if ok and clip_path.exists() and clip_path.stat().st_size > 10000:
                scene_clips.append(clip_path)
            else:
                log(f"   ❌ Failed to acquire moving clip for scene {scene_num}")

        if not scene_clips:
            log("❌ No valid moving video clips could be assembled.")
            return False

        log(f"🎞️ Concat-stitching {len(scene_clips)} genuine video clips into master track...")

        concat_list_file = CACHE_DIR / f"concat_list_{int(time.time())}_{random.randint(100,999)}.txt"
        temp_files.append(concat_list_file)
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for c in scene_clips:
                f.write(f"file '{c.resolve()}'\n")

        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-t", f"{total_duration:.2f}",
            "-an",
            str(output_video_path)
        ]

        res = subprocess.run(concat_cmd, capture_output=True, text=True)
        if res.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 10000:
            log(f"✅ Real Video Track assembled: {output_video_path} ({output_video_path.stat().st_size / 1024 / 1024:.2f} MB)")
            return True
        else:
            # Fallback filter concat
            inputs = []
            filter_chunks = []
            for i, c in enumerate(scene_clips):
                inputs.extend(["-i", str(c)])
                filter_chunks.append(f"[{i}:v]")
            filter_str = f"{''.join(filter_chunks)}concat=n={len(scene_clips)}:v=1:a=0[v]"

            fb_cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_str,
                "-map", "[v]",
                "-t", f"{total_duration:.2f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-an",
                str(output_video_path)
            ]
            fb_res = subprocess.run(fb_cmd, capture_output=True)
            return fb_res.returncode == 0 and output_video_path.exists()

    finally:
        for tf in temp_files:
            try:
                if tf.exists():
                    tf.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    test_prompts = [
        "A heavy excavator crushing a concrete pillar with sparks flying",
        "A cute golden retriever puppy running happily on green lawn"
    ]
    test_out = OUTPUT_DIR / "test_real_video_track.mp4"
    log("Running REAL VIDEO ENGINE standalone test...")
    success = generate_ai_video_track(
        visual_prompts=test_prompts,
        total_duration=6.0,
        output_video_path=test_out,
        title="Real Video Test"
    )
    print(f"Test Result: {'SUCCESS' if success else 'FAILED'} -> {test_out}")
