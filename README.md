# ComfyUI Batch Generator

A Python script for batch generating images in ComfyUI from text caption files.

## Features

- Reads caption files from a folder and processes them sequentially
- Prepends quality tags and removes unwanted tags from prompts
- Generates multiple images per caption with random seeds
- Moves processed captions to a separate folder
- Shows progress bar with ETA
- Throttles queue submissions to avoid overloading ComfyUI

## Requirements

- Python 3.8+
- ComfyUI running locally with API enabled

## Configuration

Edit the variables at the top of the script:

| Variable | Description |
|----------|-------------|
| `COMFYUI_URL` | ComfyUI server address |
| `WORKFLOW_API_PATH` | Path to your workflow JSON file |
| `CAPTIONS_FOLDER` | Folder containing caption .txt files |
| `PROCESSED_FOLDER` | Where processed captions are moved |
| `IMAGES_PER_CAPTION` | Number of images to generate per caption |
| `PREPEND_TAGS` | Tags to add to every prompt |
| `REMOVE_TAGS` | Tags to remove from every prompt |

## Workflow Setup

1. Export your ComfyUI workflow as API format (workflow.json)
2. Note the node IDs for:
   - Prompt text node
   - Sampler node (for seed)
   - Save image node (for filename prefix)
3. Update the node IDs in the configuration section

## Usage

```bash
python script_name.py
```

Place your caption files (one prompt per .txt file) in the captions folder and run the script.

## Notes

- Empty caption files are skipped
- Filename collisions in the processed folder are handled automatically
- Queue throttling prevents overloading ComfyUI