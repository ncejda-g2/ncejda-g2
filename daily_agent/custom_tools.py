"""
Custom tools for the autonomous README agent.
These tools are used by Claude to fetch XKCD comics and generate images.
"""

import os
import aiohttp
import json
from typing import Any
from pathlib import Path
from claude_agent_sdk import tool

PROJECT_ROOT = Path(__file__).parent.parent


@tool(
    "get_max_xkcd_number",
    "Get the latest XKCD comic number to determine the valid range for random selection",
    {}
)
async def get_max_xkcd_number(args: dict[str, Any]) -> dict[str, Any]:
    """Fetch the latest XKCD comic number."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://xkcd.com/info.0.json") as response:
                if response.status != 200:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Error: HTTP {response.status}"
                        }],
                        "is_error": True
                    }

                data = await response.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Maximum XKCD comic number: {data['num']}"
                    }]
                }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching max XKCD number: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "fetch_xkcd_comic",
    "Fetch a specific XKCD comic by number and return its title, image URL, and alt text",
    {"comic_number": int}
)
async def fetch_xkcd_comic(args: dict[str, Any]) -> dict[str, Any]:
    """Fetch specific XKCD comic metadata."""
    try:
        comic_number = args["comic_number"]

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://xkcd.com/{comic_number}/info.0.json") as response:
                if response.status != 200:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Error: HTTP {response.status}"
                        }],
                        "is_error": True
                    }

                data = await response.json()

                result = {
                    "number": data["num"],
                    "title": data["title"],
                    "image_url": data["img"],
                    "alt_text": data["alt"],
                    "xkcd_url": f"https://xkcd.com/{comic_number}/"
                }

                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }]
                }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching XKCD comic: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "generate_dalle_image",
    "Generate an image using OpenAI's DALL-E 3 based on a prompt",
    {"prompt": str}
)
async def generate_dalle_image(args: dict[str, Any]) -> dict[str, Any]:
    """Generate image using DALL-E 3."""
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return {
                "content": [{
                    "type": "text",
                    "text": "Error: OPENAI_API_KEY environment variable not set"
                }],
                "is_error": True
            }

        prompt = args["prompt"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "size": "1024x1024",
                    "quality": "standard",
                    "n": 1
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"DALL-E API error {response.status}: {error_text}"
                        }],
                        "is_error": True
                    }

                data = await response.json()
                image_url = data["data"][0]["url"]

                return {
                    "content": [{
                        "type": "text",
                        "text": f"Image generated successfully!\nURL: {image_url}\nPrompt used: {prompt}"
                    }]
                }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error generating image: {str(e)}"
            }],
            "is_error": True
        }


@tool(
    "download_image",
    "Download an image from a URL and save it to the generated_images directory",
    {"image_url": str, "filename": str}
)
async def download_image(args: dict[str, Any]) -> dict[str, Any]:
    """Download and save an image file."""
    try:
        image_url = args["image_url"]
        filename = args["filename"]

        # Ensure filename ends with .png
        if not filename.endswith(".png"):
            filename = f"{filename}.png"

        save_path = PROJECT_ROOT / "daily_agent" / "generated_images" / filename

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Error downloading image: HTTP {response.status}"
                        }],
                        "is_error": True
                    }

                image_data = await response.read()
                save_path.write_bytes(image_data)

                relative_path = f"daily_agent/generated_images/{filename}"

                return {
                    "content": [{
                        "type": "text",
                        "text": f"Image saved successfully to: {relative_path}"
                    }]
                }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error downloading/saving image: {str(e)}"
            }],
            "is_error": True
        }


