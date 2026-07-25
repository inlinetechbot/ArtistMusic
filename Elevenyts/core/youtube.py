# ==========================================================
# Copyright (c) 2026 ArtistBots
# All Rights Reserved.
#
# Project      : ArtistBots API Telegram Music Bot
# Powered By   : Artist
# Type         : API Based Telegram Music Bot
#
# Bot          : @ArtistApibot
# Channel      : https://t.me/artistbots
# GitHub       : https://github.com/elevenyts
#
# Unauthorized copying, modification, or redistribution
# of this source code without permission is prohibited.
# ==========================================================

import os
import re
import glob
import time
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist, VideosSearch
from Elevenyts import config, logger
from Elevenyts.helpers import Track, utils


# ==========================================================
# MusicSp API Configuration (3 APIs with fallback)
# ==========================================================
MUSICSP_APIS = [
    {
        "url": "https://apisparrow.site",
        "key": "sparrowJrFOmwb9DU9w9RfDk6NN79c0",
    },
    {
        "url": "https://apisparrow.site",
        "key": "sparrowFtvW7EnTC01FaJwdVY11o8Uj",
    },
    {
        "url": "https://apisparrow.site",
        "key": "sparrowLwA6J2dqwRKQp48ivcXZSt1r",
    },
]


class YouTube:
    def __init__(self):
        """Initialize YouTube handler with configuration and caching."""
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.warned = False

        self.enable_cookies_fallback = config.ENABLE_COOKIES_FALLBACK
        self.api_stream_timeout = config.API_STREAM_TIMEOUT

        # Regular expression to match YouTube URLs
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

        # Cache search results (10 minute TTL)
        self.search_cache = {}
        self._download_semaphore = asyncio.Semaphore(5)
        self._max_video_height = config.VIDEO_MAX_HEIGHT

        # Log initialization
        logger.info("=" * 50)
        logger.info("📹 YouTube Handler Initialized")
        logger.info(f"🎵 MusicSp APIs Configured: {len(MUSICSP_APIS)}")
        for i, api in enumerate(MUSICSP_APIS, 1):
            masked_key = api["key"][:8] + "..." if len(api["key"]) > 8 else "***"
            logger.info(f"   API {i}: {api['url']} | Key: {masked_key}")
        logger.info(f"🍪 Cookies Fallback: {'ENABLED' if self.enable_cookies_fallback else 'DISABLED'}")
        logger.info("=" * 50)

    def _locate_download_file(self, video_id: str, video: bool = False) -> Optional[str]:
        """Locate any completed download file for a video id."""
        pattern = f"downloads/{video_id}*"
        candidates = sorted([
            path for path in glob.glob(pattern)
            if not path.endswith((".part", ".ytdl", ".info.json", ".temp"))
        ])

        video_exts = {".mp4", ".mkv", ".webm", ".mov"}
        audio_exts = {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}

        if video:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in video_exts:
                    return path
        else:
            for path in candidates:
                if os.path.isdir(path):
                    continue
                if Path(path).suffix.lower() in audio_exts:
                    return path

        for path in candidates:
            if os.path.isdir(path):
                continue
            return path
        return None

    def get_cookies(self):
        """Get random cookie file from cookies directory."""
        if not self.checked:
            cookies_dir = "Elevenyts/cookies"
            if os.path.exists(cookies_dir):
                for file in os.listdir(cookies_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(file)
            self.checked = True

        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("🍪 Cookies are missing; downloads might fail.")
            return None

        cookie_file = f"Elevenyts/cookies/{random.choice(self.cookies)}"
        logger.debug(f"Using cookie file: {cookie_file}")
        return cookie_file

    async def save_cookies(self, urls: list[str]) -> None:
        """Save cookies from URLs to files."""
        logger.info("🍪 Saving cookies from urls...")
        saved_count = 0

        cookies_dir = Path("Elevenyts/cookies")
        cookies_dir.mkdir(parents=True, exist_ok=True)

        for url in urls:
            try:
                path = cookies_dir / f"cookie{random.randint(10000, 99999)}.txt"

                if "pastebin.com" in url:
                    link = url.replace("pastebin.com", "pastebin.com/raw")
                elif "batbin.me" in url:
                    link = url.replace("batbin.me", "batbin.me/raw")
                else:
                    link = url

                async with aiohttp.ClientSession() as session:
                    async with session.get(link, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            logger.error(f"❌ Cookie download failed: HTTP {resp.status} from {url}")
                            continue

                        content = await resp.read()
                        if not content or len(content) < 50:
                            logger.error(f"❌ Cookie file empty or invalid from {url}")
                            continue

                        with open(path, "wb") as fw:
                            fw.write(content)

                        if path.exists() and path.stat().st_size > 0:
                            saved_count += 1
                            cookie_filename = path.name
                            if cookie_filename not in self.cookies:
                                self.cookies.append(cookie_filename)
                            logger.info(f"✅ Saved: {cookie_filename} ({len(content)} bytes)")

            except asyncio.TimeoutError:
                logger.error(f"❌ Cookie download timeout from {url}")
            except Exception as e:
                logger.error(f"❌ Cookie download error from {url}: {e}")

        self.checked = True

        if saved_count > 0:
            logger.info(f"✅ Cookies saved successfully! ({saved_count} file(s))")
        else:
            logger.error("❌ No cookies saved! Check COOKIE_URL in .env.")

    async def _try_single_api(
        self,
        api: dict,
        video_id: str,
        file_path: str,
        video: bool = False,
        api_index: int = 1,
    ) -> Optional[str]:
        """
        Try downloading from a single MusicSp API.

        Args:
            api: Dict with 'url' and 'key'
            video_id: YouTube video ID
            file_path: Output file path
            video: True for video, False for audio
            api_index: API number for logging

        Returns:
            Path to downloaded file or None if failed
        """
        download_type = "video" if video else "audio"

        try:
            logger.info(f"🚀 [API {api_index}] Trying MusicSp API {api_index} for {video_id} ({download_type})")

            params = {
                "url": video_id,
                "type": download_type,
                "api_key": api["key"],
            }

            async with aiohttp.ClientSession() as session:
                api_endpoint = f"{api['url'].rstrip('/')}/download"
                logger.debug(f"Calling: {api_endpoint}")

                async with session.get(
                    api_endpoint,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.api_stream_timeout),
                ) as response:
                    logger.debug(f"API {api_index} response status: {response.status}")

                    if response.status != 200:
                        try:
                            error_text = await response.text()
                            logger.error(f"❌ API {api_index} returned {response.status}: {error_text[:200]}")
                        except Exception:
                            logger.error(f"❌ API {api_index} returned {response.status}")
                        return None

                    # Get file size if available
                    content_length = response.headers.get("content-length")
                    if content_length:
                        file_size_mb = int(content_length) / (1024 * 1024)
                        logger.info(f"📦 API {api_index} file size: {file_size_mb:.2f} MB")

                    # Download with progress
                    downloaded = 0
                    last_log = 0
                    with open(file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(131072):  # 128KB chunks
                            f.write(chunk)
                            downloaded += len(chunk)

                            if downloaded - last_log >= 5 * 1024 * 1024:
                                progress_mb = downloaded / (1024 * 1024)
                                if content_length:
                                    total_mb = int(content_length) / (1024 * 1024)
                                    percent = (downloaded / int(content_length)) * 100
                                    logger.info(f"📊 API {api_index} progress: {progress_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%)")
                                else:
                                    logger.info(f"📊 API {api_index} downloaded: {progress_mb:.1f} MB")
                                last_log = downloaded

                    # Verify file
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        logger.info(f"✅ [API {api_index} SUCCESS] Downloaded: {file_path} ({file_size_mb:.2f} MB)")
                        return file_path
                    else:
                        logger.error(f"❌ API {api_index} file empty or not created")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return None

        except asyncio.TimeoutError:
            logger.error(f"⏰ API {api_index} timeout for {video_id}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"🌐 API {api_index} client error for {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ API {api_index} failed for {video_id}: {type(e).__name__}: {e}")
            return None

    async def download_via_api(self, link: str, video: bool = False) -> Optional[str]:
        """
        Download audio/video using MusicSp APIs with fallback chain.
        Tries API 1 → API 2 → API 3 before giving up.

        Args:
            link: YouTube URL or video ID
            video: True for video download, False for audio

        Returns:
            Path to downloaded file or None if all APIs failed
        """
        # Extract video ID
        if "v=" in link:
            video_id = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link:
            video_id = link.split("/")[-1].split("?")[0]
        else:
            video_id = link

        if not video_id or len(video_id) < 3:
            logger.debug(f"Invalid video ID: {video_id}")
            return None

        DOWNLOAD_DIR = "downloads"
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        file_ext = ".mp4" if video else ".mp3"
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}{file_ext}")

        # Already downloaded
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            logger.debug(f"File already exists: {file_path}")
            return file_path

        # Try each API in order
        for i, api in enumerate(MUSICSP_APIS, 1):
            result = await self._try_single_api(
                api=api,
                video_id=video_id,
                file_path=file_path,
                video=video,
                api_index=i,
            )
            if result:
                return result
            logger.warning(f"⚠️ API {i} failed, trying next...")

        logger.error(f"❌ All {len(MUSICSP_APIS)} MusicSp APIs failed for {video_id}")
        return None

    async def download_via_cookies(self, video_id: str, video: bool = False) -> Optional[str]:
        """
        Download audio/video using yt-dlp with cookies (Last Resort Fallback).

        Args:
            video_id: YouTube video ID
            video: True for video download, False for audio

        Returns:
            Path to downloaded file or None if failed
        """
        if not self.enable_cookies_fallback:
            logger.debug("Cookies fallback is disabled in config")
            return None

        url = self.base + video_id
        filename_pattern = f"downloads/{video_id}"

        existing_files = [
            f for f in glob.glob(f"{filename_pattern}.*")
            if not f.endswith(".part")
        ]

        if video:
            video_candidates = [
                f for f in existing_files
                if Path(f).suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            ]
            if video_candidates:
                return video_candidates[0]
        else:
            audio_candidates = [
                f for f in existing_files
                if Path(f).suffix.lower() in {".m4a", ".webm", ".opus", ".mp3", ".ogg", ".wav", ".flac"}
            ]
            if audio_candidates:
                return audio_candidates[0]

            container_fallbacks = [
                f for f in existing_files
                if Path(f).suffix.lower() in {".mp4", ".mkv", ".mov"}
            ]
            if container_fallbacks:
                return container_fallbacks[0]

        downloads_dir = Path("downloads")
        if not downloads_dir.exists():
            try:
                downloads_dir.mkdir(parents=True, exist_ok=True)
                logger.info("📁 Created downloads directory")
            except Exception as e:
                logger.error(f"❌ Cannot create downloads directory: {e}")
                return None

        async with self._download_semaphore:
            cookie = self.get_cookies()
            base_opts = {
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "noplaylist": True,
                "geo_bypass": True,
                "no_warnings": True,
                "overwrites": False,
                "nocheckcertificate": True,
                "continuedl": True,
                "noprogress": True,
                "concurrent_fragment_downloads": 4,
                "http_chunk_size": 524288,
                "socket_timeout": 30,
                "retries": 2,
                "fragment_retries": 2,
                "extractor_retries": 5,
                "sleep_interval_requests": 1,
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            }

            if video:
                height_filter = ""
                if self._max_video_height and self._max_video_height > 0:
                    height_filter = f"[height<={self._max_video_height}]"
                format_chain = (
                    f"bestvideo[ext=mp4]{height_filter}+bestaudio[ext=m4a]/"
                    f"bestvideo{height_filter}+bestaudio/"
                    "bestvideo+bestaudio/best"
                )
                ydl_opts = {
                    **base_opts,
                    "format": format_chain,
                    "merge_output_format": "mp4",
                    "postprocessors": [
                        {
                            "key": "FFmpegVideoConvertor",
                            "preferedformat": "mp4",
                        }
                    ],
                }
            else:
                ydl_opts = {
                    **base_opts,
                    "format": "bestaudio[ext=m4a]/bestaudio[acodec=opus]/bestaudio/best",
                    "postprocessors": [],
                }

            ydl_opts_cookie = {
                **ydl_opts,
                "cookiefile": cookie,
            }

            def _download(ydl_runtime_opts):
                ydl_instance = None
                try:
                    ydl_instance = yt_dlp.YoutubeDL(ydl_runtime_opts)
                    info = ydl_instance.extract_info(url, download=True)
                    if not info:
                        logger.error(f"❌ Failed to extract info for {video_id}")
                        return None

                    time.sleep(0.5)
                    located = self._locate_download_file(video_id, video=video)
                    if located:
                        logger.info(f"✅ Download completed: {located}")
                        return located

                    logger.error(f"❌ Download completed but file not found for: {video_id}")
                    return None
                except Exception as ex:
                    logger.warning(f"⚠️ Download error for {video_id}: {ex}")
                    recovered = self._locate_download_file(video_id, video=video)
                    if recovered:
                        logger.info(f"✅ Recovered existing file: {recovered}")
                        return recovered
                    return None
                finally:
                    if ydl_instance:
                        try:
                            ydl_instance.close()
                        except Exception:
                            pass

            logger.info(f"🍪 [COOKIES LAST RESORT] Downloading {video_id} with cookies...")
            result = await asyncio.to_thread(_download, ydl_opts_cookie)

            if result:
                logger.info(f"✅ [COOKIES SUCCESS] Downloaded: {result}")
            else:
                logger.warning(f"⚠️ [COOKIES FAILED] Could not download {video_id}")

            return result

    async def download(self, link: str, video: bool = False) -> Optional[str]:
        """
        Main download method with full fallback chain:
        API 1 → API 2 → API 3 → Cookies (yt-dlp)

        Args:
            link: YouTube URL or video ID
            video: True for video, False for audio

        Returns:
            Path to downloaded file or None if everything failed
        """
        # Extract video ID for cookies fallback
        if "v=" in link:
            video_id = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link:
            video_id = link.split("/")[-1].split("?")[0]
        else:
            video_id = link

        # Step 1-3: Try all MusicSp APIs
        result = await self.download_via_api(link=link, video=video)
        if result:
            return result

        # Step 4: Cookies fallback (last resort)
        logger.warning(f"⚠️ All APIs failed for {video_id}, trying cookies fallback...")
        result = await self.download_via_cookies(video_id=video_id, video=video)
        if result:
            return result

        logger.error(f"❌ All download methods failed for {video_id}")
        return None

    def valid(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL."""
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        """Extract YouTube URL from message."""
        messages = [message_1]
        link = None

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

  
