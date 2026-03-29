import json
import random
import urllib.request
import os
import time
import shutil
import re
from pathlib import Path
from datetime import timedelta

# ============ CONFIGURATION ============
COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_API_PATH = "workflow.json"
CAPTIONS_FOLDER = "./captions"
PROCESSED_FOLDER = "./captions_done"         # processed captions move here
IMAGES_PER_CAPTION = 4

# Node IDs from your workflow
PROMPT_NODE_ID = "11"
PROMPT_FIELD = "text"
SAMPLER_NODE_ID = "19"
SEED_FIELD = "seed"
SAVE_NODE_ID = "29"

# ============ TAG EDITING ============
# Tags to prepend to every prompt (comma-separated string, or empty to skip)
PREPEND_TAGS = "masterpiece, best quality, good quality, newest, absurdres, highres"

# Tags to remove from every prompt (comma-separated string, or empty to skip)
# Case-insensitive matching
REMOVE_TAGS = ""
# =======================================


def load_workflow(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def queue_prompt(workflow: dict) -> dict:
    """Send a prompt to ComfyUI's API queue."""
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_queue_size() -> int:
    """Check how many items are in the queue."""
    req = urllib.request.Request(f"{COMFYUI_URL}/queue")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        running = len(data.get("queue_running", []))
        pending = len(data.get("queue_pending", []))
        return running + pending


def wait_for_queue(max_queue: int = 4, poll_interval: float = 2.0):
    """Wait until the queue has fewer than max_queue items."""
    while get_queue_size() >= max_queue:
        time.sleep(poll_interval)


def parse_tags(tag_string: str) -> list[str]:
    """Parse a comma-separated tag string into a clean list."""
    if not tag_string or not tag_string.strip():
        return []
    return [t.strip() for t in tag_string.split(",") if t.strip()]


def process_caption(caption_text: str, prepend_tags: list[str], remove_tags: list[str]) -> str:
    """Prepend tags and remove unwanted tags from caption text."""

    # Split caption into individual tags
    caption_tags = [t.strip() for t in caption_text.split(",") if t.strip()]

    # Remove unwanted tags (case-insensitive)
    if remove_tags:
        remove_lower = {t.lower() for t in remove_tags}
        caption_tags = [t for t in caption_tags if t.lower() not in remove_lower]

    # Prepend tags (avoid duplicates, case-insensitive)
    if prepend_tags:
        existing_lower = {t.lower() for t in caption_tags}
        unique_prepend = [t for t in prepend_tags if t.lower() not in existing_lower]
        caption_tags = unique_prepend + caption_tags

    return ", ".join(caption_tags)


def format_time(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 0:
        return "??:??"
    td = timedelta(seconds=int(seconds))
    parts = []
    hours, remainder = divmod(td.seconds + td.days * 86400, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def move_to_processed(caption_file: Path, processed_folder: Path):
    """Move a processed caption file to the processed folder."""
    processed_folder.mkdir(parents=True, exist_ok=True)
    dest = processed_folder / caption_file.name

    # Handle name collisions
    if dest.exists():
        stem = caption_file.stem
        suffix = caption_file.suffix
        counter = 1
        while dest.exists():
            dest = processed_folder / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(str(caption_file), str(dest))


def main():
    # Load the base workflow
    base_workflow = load_workflow(WORKFLOW_API_PATH)

    # Parse tag lists
    prepend_tags = parse_tags(PREPEND_TAGS)
    remove_tags = parse_tags(REMOVE_TAGS)

    # Show tag config
    if prepend_tags:
        print(f"✚ Prepending tags: {', '.join(prepend_tags)}")
    if remove_tags:
        print(f"✖ Removing tags:   {', '.join(remove_tags)}")
    if prepend_tags or remove_tags:
        print()

    # Collect all caption files
    caption_files = sorted(Path(CAPTIONS_FOLDER).glob("*.txt"))
    total_captions = len(caption_files)
    total_images = total_captions * IMAGES_PER_CAPTION

    if total_captions == 0:
        print(f"No .txt files found in '{CAPTIONS_FOLDER}'. Nothing to do.")
        return

    print(f"Found {total_captions} caption files")
    print(f"Will generate {IMAGES_PER_CAPTION} images each → {total_images} total images")
    print(f"Processed captions will be moved to: {PROCESSED_FOLDER}\n")
    print("=" * 60)

    processed_folder = Path(PROCESSED_FOLDER)
    start_time = time.time()
    images_completed = 0

    for cap_idx, caption_file in enumerate(caption_files):
        caption_text = caption_file.read_text(encoding="utf-8").strip()
        caption_name = caption_file.stem

        if not caption_text:
            print(f"⚠ Skipping empty file: {caption_file.name}")
            continue

        # Process tags
        final_prompt = process_caption(caption_text, prepend_tags, remove_tags)

        # Progress header for this caption
        print(f"\n[{cap_idx + 1}/{total_captions}] 📄 {caption_file.name}")
        print(f"  Original:  \"{caption_text[:100]}{'...' if len(caption_text) > 100 else ''}\"")
        if final_prompt != caption_text:
            print(f"  Processed: \"{final_prompt[:100]}{'...' if len(final_prompt) > 100 else ''}\"")

        for i in range(IMAGES_PER_CAPTION):
            # Deep copy the workflow
            workflow = json.loads(json.dumps(base_workflow))

            # Set the processed caption text
            workflow[PROMPT_NODE_ID]["inputs"][PROMPT_FIELD] = final_prompt

            # Set a random seed
            seed = random.randint(0, 2**63 - 1)
            workflow[SAMPLER_NODE_ID]["inputs"][SEED_FIELD] = seed

            # Set a meaningful filename prefix
            if SAVE_NODE_ID and SAVE_NODE_ID in workflow:
                safe_name = caption_name.replace(" ", "_")[:50]
                workflow[SAVE_NODE_ID]["inputs"]["filename_prefix"] = (
                    f"{safe_name}/{safe_name}_{i + 1}"
                )

            # Throttle: don't overload the queue
            wait_for_queue(max_queue=8)

            # Queue it
            result = queue_prompt(workflow)
            prompt_id = result.get("prompt_id", "?")
            images_completed += 1

            # ETA calculation
            elapsed = time.time() - start_time
            avg_per_image = elapsed / images_completed if images_completed else 0
            remaining = (total_images - images_completed) * avg_per_image
            eta_str = format_time(remaining)

            # Progress bar
            pct = images_completed / total_images * 100
            bar_len = 30
            filled = int(bar_len * images_completed / total_images)
            bar = "█" * filled + "░" * (bar_len - filled)

            print(
                f"  [{bar}] {pct:5.1f}% "
                f"({images_completed}/{total_images}) "
                f"seed={seed}  ETA: {eta_str}"
            )

        # Move processed caption to done folder
        move_to_processed(caption_file, processed_folder)
        print(f"  ✓ Moved {caption_file.name} → {PROCESSED_FOLDER}/")

    # Final summary
    total_elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ All done! {images_completed} images queued in {format_time(total_elapsed)}")
    print(f"   Average: {format_time(total_elapsed / images_completed if images_completed else 0)} per image")
    print(f"   Processed captions moved to: {PROCESSED_FOLDER}/")


if __name__ == "__main__":
    main()