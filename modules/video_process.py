"""
video_process.py — Mode 2: FFmpeg video processing
Trim + Logo overlay + Endscreen + Drive upload
"""

import os
import re
import subprocess
from pathlib import Path
from datetime import datetime

from modules.config import (
    OUT_BASE, LOGO_PATH, ENDSCREEN_VIDEO, TRIM_SECONDS,
    LOGO_X, LOGO_Y, LOGO_WIDTH, LOGO_OPACITY, ENDSCREEN_ENABLED,
    UPLOAD_TO_DRIVE, DRIVE_FOLDER_ID, VIDEO_EXTS
)
from modules.console_utils import ok, warn, err, info, console
from modules.drive import upload_file
from modules.sheet import update_row

try:
    from rich.progress import (Progress, SpinnerColumn, TextColumn,
                                BarColumn, TimeElapsedColumn)
    _has_rich = True
except ImportError:
    _has_rich = False


# ── Filename helpers ───────────────────────────────────────────────────────────
def extract_row_num(stem: str) -> int | None:
    m = re.match(r"row(\d+)[_\-]", stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def make_processed_name(row_num: int, title_part: str) -> str:
    safe = re.sub(r"[^\w\-]", "_", title_part.replace("_", " ")[:40])
    return f"row{row_num}-Processed-{safe}"


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────
def check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def get_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def has_valid_video(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True, timeout=10
        )
        return float(r.stdout.strip()) > 0
    except Exception:
        return False


def has_audio_stream(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def scan_videos(base: Path) -> list[Path]:
    if not base or not base.exists():
        return []
    return sorted(
        p for p in base.rglob("*")
        if p.is_file()
        and p.suffix.lower() in VIDEO_EXTS
        and not p.stem.endswith("_processed")
        and "-Processed-" not in p.stem
        and "_thumb" not in p.stem
    )


# ── FFmpeg encode profiles ─────────────────────────────────────────────────────
PROFILES = {
    # Basic profiles
    "720p":     {"label": "720p — Fast",                  "resolution": "1280x720",  "crf": 23, "preset": "fast",     "audio_br": "128k"},
    "1080p":    {"label": "1080p — Standard",             "resolution": "1920x1080", "crf": 23, "preset": "veryfast", "audio_br": "128k"},
    "1080p_hq": {"label": "1080p HQ — Slow",              "resolution": "1920x1080", "crf": 18, "preset": "slow",     "audio_br": "192k"},
    
    # YouTube-optimized profiles
    "youtube_720p":   {"label": "YouTube 720p — Optimized", "resolution": "1280x720",  "crf": 21, "preset": "fast",     "audio_br": "128k", "movflags": "+faststart"},
    "youtube_1080p":  {"label": "YouTube 1080p — Optimized","resolution": "1920x1080", "crf": 21, "preset": "fast",     "audio_br": "128k", "movflags": "+faststart"},
    "youtube_4k":     {"label": "YouTube 4K — Optimized",   "resolution": "3840x2160", "crf": 22, "preset": "medium",   "audio_br": "192k", "movflags": "+faststart"},
    
    # Social media profiles
    "tiktok":    {"label": "TikTok/Shorts 9:16",          "resolution": "1080x1920", "crf": 23, "preset": "fast",     "audio_br": "128k", "movflags": "+faststart"},
    "instagram": {"label": "Instagram 1:1",               "resolution": "1080x1080", "crf": 23, "preset": "fast",     "audio_br": "128k", "movflags": "+faststart"},
}


def build_ffmpeg_cmd(
    input_file: Path, output_file: Path,
    trim_seconds: int, logo_path: Path,
    logo_x: int, logo_y: int, logo_width: int, logo_opacity: float,
    endscreen_enabled: bool, endscreen_path,
    profile_key: str = "1080p"
) -> list[str]:
    profile = PROFILES.get(profile_key, PROFILES["1080p"])
    res = profile["resolution"]
    w, h = res.split("x")
    scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    crf    = profile["crf"]
    preset = profile["preset"]
    ab     = profile["audio_br"]

    dur      = get_duration(input_file)
    trim_dur = max(0.1, dur - trim_seconds) if dur > trim_seconds > 0 else dur
    input_has_audio = has_audio_stream(input_file)
    has_logo      = logo_path.exists() and logo_width > 0
    has_endscreen = (endscreen_enabled and endscreen_path and
                     Path(endscreen_path).exists() and has_valid_video(Path(endscreen_path)))

    inputs   = ["-i", str(input_file)]
    logo_idx = end_idx = None
    if has_logo:
        logo_idx = len(inputs) // 2
        inputs += ["-i", str(logo_path)]
    if has_endscreen:
        end_idx = len(inputs) // 2
        inputs += ["-i", str(endscreen_path)]

    filters = []
    filters.append(f"[0:v]trim=duration={trim_dur:.3f},setpts=PTS-STARTPTS,{scale}[base]")
    if input_has_audio:
        filters.append(f"[0:a]atrim=duration={trim_dur:.3f},asetpts=PTS-STARTPTS[main_a]")

    if has_logo:
        logo_scale = f"[{logo_idx}:v]scale={logo_width}:-1[logo_s]"
        if logo_opacity < 1.0:
            logo_scale += f";[logo_s]format=rgba,colorchannelmixer=aa={logo_opacity:.2f}[logo_f]"
            lref = "logo_f"
        else:
            lref = "logo_s"
        filters.append(logo_scale)
        filters.append(f"[base][{lref}]overlay={LOGO_X}:{LOGO_Y}[v_logo]")
        vref = "v_logo"
    else:
        vref = "base"

    if has_endscreen:
        filters.append(f"[{end_idx}:v]scale={w}:{h}[end_s]")
        filters.append(f"[{vref}][end_s]concat=n=1:v=1:a=0[v_final]")
        vref = "v_final"

    # Build final filter chain
    if input_has_audio:
        filters.append(f"[{vref}][main_a]concat=n=1:v=1:a=1[v_out][a_out]")
        map_v = "[v_out]"
        map_a = "[a_out]"
    else:
        filters.append(vref)
        map_v = "[0]"
        map_a = None

    # Build command
    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", ";".join(filters), "-map", map_v]
    if map_a:
        cmd += ["-map", map_a, "-c:a", "aac", "-b:a", ab]
    else:
        cmd += ["-an"]
    
    # Video encoding settings
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    
    # Add movflags if specified in profile
    if profile.get("movflags"):
        cmd += ["-movflags", profile["movflags"]]
    
    cmd += [str(output_file)]
    return cmd


def run_ffmpeg(cmd: list[str], input_file: Path, output_file: Path,
               dry_run: bool = False) -> bool:
    if dry_run:
        info(f"[DRY-RUN] {' '.join(cmd[:6])} ...")
        return True
    duration = get_duration(input_file)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, universal_newlines=True)
        if _has_rich:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                          TimeElapsedColumn(), console=console) as progress:
                task = progress.add_task(f"[cyan]Encoding {input_file.name}", total=100)
                for line in proc.stdout:
                    if "time=" in line:
                        try:
                            tp = line.split("time=")[1].split()[0]
                            h, m, s = tp.split(":")
                            cur = int(h) * 3600 + int(m) * 60 + float(s)
                            if duration > 0:
                                progress.update(task, completed=min(100, int(cur/duration*100)))
                        except Exception:
                            pass
        else:
            for line in proc.stdout:
                if "time=" in line: console.print(f"  {line.strip()}")
        rc = proc.wait()
        if rc == 0:
            ok(f"Encoded → {output_file.name}")
            return True
        else:
            err(f"FFmpeg exit code {rc}")
            return False
    except Exception as e:
        err(f"FFmpeg error: {e}")
        return False


# ── Public: process a single video ────────────────────────────────────────────
def process_video(input_video: Path, dry_run: bool = False, profile: str = "1080p") -> bool:
    if not check_ffmpeg():
        err("FFmpeg not found. Install FFmpeg and add to PATH.")
        return False

    stem     = input_video.stem
    row_num  = extract_row_num(stem)

    if "-Generated-" in stem:
        title_part = stem.split("-Generated-", 1)[1]
    elif "_" in stem:
        title_part = stem.split("_", 1)[1]
    else:
        title_part = stem

    if row_num:
        safe_name   = make_processed_name(row_num, title_part)
        output_file = input_video.parent / f"{safe_name}{input_video.suffix}"
    else:
        output_file = input_video.parent / f"{input_video.stem}_processed{input_video.suffix}"

    if output_file.exists():
        info(f"Already processed — skipping ({output_file.name})")
        return True

    endscreen_enabled = ENDSCREEN_ENABLED
    endscreen_path    = ENDSCREEN_VIDEO
    if ENDSCREEN_ENABLED and not ENDSCREEN_VIDEO.exists():
        warn("Endscreen not found — skipping")
        endscreen_enabled = False
        endscreen_path    = None

    cmd = build_ffmpeg_cmd(
        input_file=input_video, output_file=output_file,
        trim_seconds=TRIM_SECONDS, logo_path=LOGO_PATH,
        logo_x=LOGO_X, logo_y=LOGO_Y, logo_width=LOGO_WIDTH,
        logo_opacity=LOGO_OPACITY, endscreen_enabled=endscreen_enabled,
        endscreen_path=endscreen_path, profile_key=profile
    )
    info(f"Processing → {output_file.name}")
    return run_ffmpeg(cmd, input_video, output_file, dry_run=dry_run)


# ── Public: process local files (Mode 2 Local) ────────────────────────────────
def process_local_files(directory: Path, upload: bool = False, profile: str = "1080p", max_files: int = 0) -> int:
    """Process video files from local directory and optionally update sheet."""
    if not directory.exists():
        err(f"Directory not found: {directory}")
        return 1
    
    # Scan for video files in directory (recursive)
    videos = []
    for ext in VIDEO_EXTS:
        videos.extend(directory.rglob(f"*{ext}"))
        videos.extend(directory.rglob(f"*{ext.upper()}"))
    
    # Filter out already processed files
    unprocessed = []
    for video in videos:
        if (video.stem.endswith("_processed") or 
            "-Processed-" in video.stem or 
            "_thumb" in video.stem):
            continue
        unprocessed.append(video)
    
    if not unprocessed:
        warn(f"No unprocessed video files found in {directory}")
        return 0
    
    # Apply quantity limit
    if max_files > 0:
        unprocessed = unprocessed[:max_files]
        ok(f"Processing {len(unprocessed)} video file(s) (limited to {max_files})")
    else:
        ok(f"Found {len(unprocessed)} video file(s) to process")
    
    ok_count = fail_count = 0
    for i, vid in enumerate(unprocessed, 1):
        console.rule(f"[cyan][{i}/{len(unprocessed)}]  {vid.name}[/cyan]")
        
        # Process the video
        success = process_video(vid, dry_run=False, profile=profile)
        if success:
            ok_count += 1
            
            # Upload to Drive if requested
            if upload:
                try:
                    # Try multiple naming conventions for processed file
                    processed_file = None
                    
                    # Option 1: Standard naming
                    candidate = vid.parent / f"{vid.stem}_processed{vid.suffix}"
                    if candidate.exists():
                        processed_file = candidate
                    
                    # Option 2: Row-based naming (from make_processed_name)
                    if not processed_file:
                        row_num = extract_row_num(vid.stem)
                        if row_num:
                            if "-Generated-" in vid.stem:
                                title_part = vid.stem.split("-Generated-", 1)[1]
                            elif "_" in vid.stem:
                                title_part = vid.stem.split("_", 1)[1]
                            else:
                                title_part = vid.stem
                            
                            safe_name = make_processed_name(row_num, title_part)
                            candidate = vid.parent / f"{safe_name}{vid.suffix}"
                            if candidate.exists():
                                processed_file = candidate
                    
                    # Option 3: Search for any processed file in the same directory
                    if not processed_file:
                        for f in vid.parent.glob("*Processed*"):
                            if f.suffix == vid.suffix and vid.stem in f.stem:
                                processed_file = f
                                break
                    
                    if processed_file and processed_file.exists():
                        folder_name = directory.name or "Local_Processed"
                        processed_link = upload_file(str(processed_file), folder_name)
                        ok(f"Uploaded to Drive: {processed_link}")
                        
                        # Ask if user wants to update sheet
                        update_sheet = console.input("  [bold cyan]Update sheet with this result?[/bold cyan] [dim](Y/N)[/dim]: ").strip().upper()
                        if update_sheet == "Y":
                            _update_sheet_for_local_file(vid, processed_file, processed_link)
                    else:
                        warn(f"Processed file not found for upload. Checked: {vid.parent}")
                        # List all files in directory for debugging
                        files = [f.name for f in vid.parent.glob("*.mp4")]
                        info(f"Available files: {files}")
                except Exception as e:
                    err(f"Upload failed: {e}")
        else:
            fail_count += 1
    
    console.print()
    console.rule()
    ok(f"Local processing done!  OK={ok_count}  FAIL={fail_count}")
    return 0 if fail_count == 0 else 1


def _update_sheet_for_local_file(original_file: Path, processed_file: Path, drive_link: str):
    """Update sheet with local file processing results."""
    try:
        from modules.sheet import append_row, SCHEMA_VIDEOS
        import uuid
        
        # Generate a unique Row_ID for local files
        row_id = f"LOCAL_{uuid.uuid4().hex[:8]}"
        
        # Append to Videos tab
        append_row(
            "2_Videos", SCHEMA_VIDEOS,
            Row_ID         = row_id,
            Title          = original_file.stem,
            Local_Path     = str(processed_file),
            Drive_Raw      = "",  # No raw video for local files
            Drive_Thumb    = "",
            Status         = "Done",
            Process_Time   = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            Process_Drive  = drive_link,
            Completed_Time = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            Notes          = "Processed from local file"
        )
        ok(f"[sheet] Added to Videos tab with Row_ID: {row_id}")
    except Exception as e:
        warn(f"[sheet] Failed to update: {e}")


# ── Public: process all pending videos ────────────────────────────────────────
def process_all(videos: list[Path] = None, dry_run: bool = False,
                upload: bool = False, profile: str = "1080p") -> int:
    base = Path(OUT_BASE)
    if videos is None:
        videos = scan_videos(base)
    if not videos:
        warn("No unprocessed videos found.")
        return 0

    ok_count = fail_count = 0
    total = len(videos)
    for i, vid in enumerate(videos, 1):
        console.rule(f"[cyan][{i}/{total}]  {vid.parent.name} / {vid.name}[/cyan]")
        row_num = extract_row_num(vid.stem)
        if "-Generated-" in vid.stem:
            title_part = vid.stem.split("-Generated-", 1)[1]
        elif "_" in vid.stem:
            title_part = vid.stem.split("_", 1)[1]
        else:
            title_part = vid.stem

        if row_num:
            safe_name = make_processed_name(row_num, title_part)
            dst       = vid.parent / f"{safe_name}{vid.suffix}"
        else:
            dst = vid.parent / f"{vid.stem}_processed{vid.suffix}"

        if dst.exists():
            info(f"Already processed — skipping ({dst.name})")
            ok_count += 1
            continue

        dur = get_duration(vid)
        mb  = vid.stat().st_size / 1_048_576
        info(f"Duration: {dur:.1f}s   Size: {mb:.1f} MB")
        info(f"Output:   {dst.name}")

        success = process_video(vid, dry_run=dry_run, profile=profile)
        if success:
            ok_count += 1
            if upload and not dry_run and dst.exists():
                folder_name    = vid.parent.name or vid.stem
                processed_link = upload_file(str(dst), folder_name)
                if row_num:
                    try:
                        from modules.sheet import SCHEMA_VIDEOS
                        update_row(
                            "2_Videos", row_num, SCHEMA_VIDEOS,
                            Status         = "Done",
                            Process_Drive  = processed_link,
                            Completed_Time = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            Notes          = "Processed OK"
                        )
                        ok(f"[sheet] Row {row_num} → Done | Process_Drive written")
                    except Exception as se:
                        warn(f"[sheet] Process_Drive update: {se}")
        else:
            fail_count += 1
            if dst.exists() and not dry_run:
                try: dst.unlink()
                except Exception: pass

    console.print()
    console.rule()
    ok(f"Processing done!  OK={ok_count}  FAIL={fail_count}")
    return 0 if fail_count == 0 else 1
