
import subprocess
import re
import os
import shutil

webp_path = "astro/docs/assets/ux_verification_demo.webp"
frames_dir = "astro/docs/assets/frames"
concat_file = "astro/docs/assets/concat_list.txt"
output_mp4 = "astro/docs/assets/ux_verification_demo_slow.mp4"

if os.path.exists(frames_dir):
    shutil.rmtree(frames_dir)
os.makedirs(frames_dir, exist_ok=True)

# 1. Get Info
print("Getting WebP info...")
cmd_info = ["webpmux", "-info", webp_path]
result = subprocess.run(cmd_info, capture_output=True, text=True)
lines = result.stdout.splitlines()

# Regex: No.: width height alpha x_offset y_offset duration
pattern = re.compile(r"^\s*(\d+):\s+\d+\s+\d+\s+\S+\s+\d+\s+\d+\s+(\d+)\s+")

frames = []
for line in lines:
    match = pattern.match(line)
    if match:
        frame_num = int(match.group(1))
        duration_ms = int(match.group(2))
        frames.append((frame_num, duration_ms))

print(f"Found {len(frames)} frames.")

# 2. Extract Frames and Build Concat List with "Pause" Logic
with open(concat_file, "w") as f:
    for i, (frame_num, duration_ms) in enumerate(frames):
        # Extract frame
        frame_filename = f"frame_{frame_num:04d}.webp"
        frame_path = os.path.join(frames_dir, frame_filename)
        
        subprocess.run(["webpmux", "-get", "frame", str(frame_num), webp_path, "-o", frame_path], check=True)
        
        # LOGIC CHANGE: 
        # Original durations are often very fast (e.g., 50ms, 100ms) for UI transitions.
        # User wants "pauses to appreciate the image".
        # Heuristic: 
        #   - If duration <= 150ms: It's likely an animation frame. Keep it relatively short (e.g. 100-200ms) but not too fast.
        #   - If duration > 150ms: It's likely a resting state. BOOS IT significantly (e.g. 2 seconds).
        
        current_dur_ms = duration_ms
        if current_dur_ms < 100:
            final_duration_sec = 0.1  # Slow down transitions to min 100ms
        elif current_dur_ms > 2000:
             final_duration_sec = current_dur_ms / 1000.0 # already long enough
        else:
             # This captures most "resting" points which might be just 100-500ms in a recording
             # Force them to be at least 2 seconds if they are "pauses"
             # But how to distinguish a "pause" from a slow transition?
             # Let's say if it matches the *previous* frame's duration roughly? No.
             
             # Simpler approach requested by user: "pausa por cada pantalla".
             # A recording has many frames. We can't pause EVERY frame or it will be a slideshow.
             # We want to pause on *significant* changes.
             # Since we can't analyze content easily here, let's just SLOW DOWN EVERYTHING.
             # Multiply all durations by 4x.
             
             # User said: "no tiene ninguna pausa... volver a generar con una pausa por cada pantalla"
             # "la velocidad que se ve en el walkthrough es la adecuada" -> Walkthrough webp is played by browser which respects duration.
             
             # If the previous MP4 was fast, maybe my extraction logic failed or fps forced it.
             # Previous script used exact duration.
             
             # Let's apply a minimum floor of 2 seconds for ANY frame that is longer than 500ms.
             # And slow down others by 2x.
             
             if current_dur_ms > 300:
                 final_duration_sec = 3.0 # Force 3 second pause for static-ish frames
             else:
                 final_duration_sec = current_dur_ms / 1000.0 # keep fast frames fast-ish (transitions)
                 # Maybe slow them down slightly
                 final_duration_sec = max(final_duration_sec, 0.15) 

        f.write(f"file 'frames/{frame_filename}'\n")
        f.write(f"duration {final_duration_sec:.3f}\n")

    # Repeat last frame
    f.write(f"file 'frames/frame_{len(frames):04d}.webp'\n")
    f.write(f"duration 3.0\n") 

print("Concat list generated.")

# 3. Encode
print("Encoding MP4...")
cmd_ffmpeg = [
    "ffmpeg", "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_file,
    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
    "-c:v", "libx264",
    "-profile:v", "high",
    "-level", "4.1",
    "-vf", "scale=1280:720,format=yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-shortest",
    output_mp4
]

subprocess.run(cmd_ffmpeg, check=True)
print(f"Done! Output: {output_mp4}")

import shutil
shutil.rmtree(frames_dir)
os.remove(concat_file)
print("Cleanup done.")
