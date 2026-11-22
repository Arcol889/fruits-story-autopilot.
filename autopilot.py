#!/usr/bin/env python3
"""Fruits Story autopilot: Drive A/B -> ffmpeg -> Cloudinary -> Buffer.

No writes are performed unless PUBLISH_ENABLED=true.
Secrets are read from environment variables only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE = Path(__file__).resolve().parent
VIDEO_RE = re.compile(r"^FRUITS_EP(\d{1,4})_([AB])\.mp4$", re.IGNORECASE)
MARKER_RE = re.compile(r"#FruitsEP(\d{3,4})\b", re.I)
BUFFER_ENDPOINT = "https://api.buffer.com"
SERVICES = ("instagram", "tiktok", "youtube")


def config():
    obj = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    obj["timezone"] = ZoneInfo(obj.get("timezone", "Europe/Paris"))
    obj["start_date"] = date.fromisoformat(obj["start_date"])
    return obj


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Variable manquante: {name}. Consulter README.md.")
    return value


def gql_literal(value):
    """Only interpolate untrusted identifier data as JSON-escaped GraphQL strings."""
    return json.dumps(value, ensure_ascii=False)


class BufferAPI:
    def __init__(self, token: str, http=None):
        self.token = token
        self.http = http or requests.Session()

    def query(self, query: str, variables=None):
        response = self.http.post(
            BUFFER_ENDPOINT,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Buffer GraphQL: {payload['errors']}")
        return payload.get("data") or {}

    def organization_id(self, preferred=None):
        if preferred:
            return preferred
        account = self.query("query { account { organizations { id name } } }").get("account") or {}
        orgs = account.get("organizations") or []
        if len(orgs) != 1:
            raise RuntimeError("Buffer: plusieurs organisations (ou aucune); définir BUFFER_ORG_ID.")
        return orgs[0]["id"]

    def channels(self, org_id):
        result = self.query(
            f"query {{ channels(input: {{ organizationId: {gql_literal(org_id)} }}) "
            "{ id name displayName service isQueuePaused } }"
        )
        channels = result.get("channels") or []
        result = {}
        for service in SERVICES:
            matches = [x for x in channels if x.get("service") == service and not x.get("isQueuePaused")]
            if len(matches) > 1:
                raise RuntimeError(f"Buffer: plusieurs comptes {service}. Configurer un seul compte avant activation.")
            if matches:
                result[service] = matches[0]["id"]
        return result

    def posts(self, org_id: str, channel_ids: list[str]):
        """Get scheduled/sent/error posts with pagination, to deduplicate retries."""
        if not channel_ids:
            return []
        after = None
        all_posts = []
        for _ in range(30):
            cursor = f", after: {gql_literal(after)}" if after else ""
            filters = "[" + ",".join(gql_literal(x) for x in channel_ids) + "]"
            q = ("query { posts(first: 100" + cursor + ", input: {organizationId: "
                 + gql_literal(org_id) + ", filter: {channelIds: " + filters
                 + ", status: [scheduled,sent,sending,error]}}) "
                 "{ edges { node { id text status dueAt channelId } } "
                 "pageInfo { endCursor hasNextPage } } }")
            result = self.query(q).get("posts") or {}
            all_posts.extend(x["node"] for x in result.get("edges", []))
            page = result.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                return all_posts
            next_after = page.get("endCursor")
            if not next_after or next_after == after:
                raise RuntimeError("Pagination Buffer invalide : arrêt de sécurité.")
            after = next_after
        raise RuntimeError("Trop de pages Buffer; arrêt de sécurité pour éviter les doublons.")

    def create(self, *, channel_id: str, service: str, when: datetime, url: str,
               title: str, caption: str, for_kids: bool):
        metadata = {
            "instagram": {"instagram": {"type": "reel", "shouldShareToFeed": True,
                                        "isAiGenerated": True}},
            "tiktok": {"tiktok": {"isAiGenerated": True}},
            "youtube": {"youtube": {"title": title[:100], "categoryId": "1",
                                      "madeForKids": for_kids, "isAiGenerated": True,
                                      "privacy": "public"}},
        }[service]
        input_data = {
            "channelId": channel_id, "text": caption,
            "schedulingType": "automatic", "mode": "customScheduled",
            "dueAt": when.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "assets": [{"video": {"url": url, "metadata": {"thumbnailOffset": 1000}}}],
            "metadata": metadata,
            "aiAssisted": True,
        }
        out = self.query("""mutation ($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id dueAt status } }
            ... on MutationError { message }
          }
        }""", {"input": input_data}).get("createPost") or {}
        if "message" in out:
            raise RuntimeError(f"Échec de programmation Buffer ({service}): {out['message']}")
        if not out.get("post", {}).get("id"):
            raise RuntimeError(f"Réponse Buffer inattendue: {out}")
        return out["post"]["id"]


class DriveSources:
    """Read-only service-account access to folder shared by Google Drive owner."""
    def __init__(self, service_account_json):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        self.client = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_clips(self, folder_id):
        clips = {}
        token = None
        while True:
            page = self.client.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=1000, pageToken=token,
                fields="nextPageToken,files(id,name,mimeType,size)",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            for file in page.get("files", []):
                match = VIDEO_RE.fullmatch(file["name"])
                if match and file.get("mimeType") == "video/mp4":
                    episode, letter = int(match.group(1)), match.group(2).upper()
                    if (episode, letter) in clips:
                        raise RuntimeError(f"Deux sources avec le même nom pour épisode {episode}{letter}")
                    clips[(episode, letter)] = file["id"]
            token = page.get("nextPageToken")
            if not token:
                break
        return clips

    def download(self, file_id: str, dest: Path):
        from googleapiclient.http import MediaIoBaseDownload
        with dest.open("wb") as stream:
            media = self.client.files().get_media(fileId=file_id, supportsAllDrives=True)
            downloader = MediaIoBaseDownload(stream, media, chunksize=1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        if dest.stat().st_size == 0:
            raise RuntimeError("Drive a renvoyé un clip vide")


def run_command(args, timeout=900):
    output = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if output.returncode:
        raise RuntimeError(f"Commande ffmpeg/ffprobe échouée: {' '.join(args)}\n{output.stderr[-3000:]}")
    return output.stdout


def has_audio(file_path: Path) -> bool:
    text = run_command(["ffprobe", "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=index", "-of", "csv=p=0", str(file_path)])
    return bool(text.strip())


def make_video(a: Path, b: Path, output: Path):
    """Normalize both clips to identical H.264/AAC 9:16 format then concatenate."""
    vf = ("scale=w=1080:h=1920:force_original_aspect_ratio=decrease,"
          "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p")
    with tempfile.TemporaryDirectory(prefix="fruit_render_") as tmp:
        normalized = []
        for index, source in enumerate((a, b)):
            segment = Path(tmp) / f"part{index}.mp4"
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
            audio = has_audio(source)
            if not audio:
                command += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            command += ["-map", "0:v:0", "-map", "0:a:0" if audio else "1:a:0",
                        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                        "-pix_fmt", "yuv420p", "-r", "30", "-profile:v", "high",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                        "-shortest", str(segment)]
            run_command(command)
            normalized.append(segment)
        concat_list = Path(tmp) / "list.txt"
        concat_list.write_text("".join(f"file '{x.as_posix()}'\n" for x in normalized), encoding="utf-8")
        run_command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-f", "concat", "-safe", "0", "-i", str(concat_list),
                     "-c", "copy", "-movflags", "+faststart", str(output)])
    if not output.is_file() or output.stat().st_size < 1024:
        raise RuntimeError("Export vidéo absent ou anormalement petit")
    return output


class CloudVideo:
    def __init__(self, cloudinary_url):
        import cloudinary
        import cloudinary.api
        import cloudinary.uploader
        from urllib.parse import urlparse, unquote
        parsed = urlparse(cloudinary_url)
        if parsed.scheme != "cloudinary" or not parsed.username or not parsed.password or not parsed.hostname:
            raise RuntimeError("CLOUDINARY_URL invalide; format attendu cloudinary://cle:secret@nom_du_cloud")
        cloudinary.config(
            cloud_name=parsed.hostname,
            api_key=unquote(parsed.username),
            api_secret=unquote(parsed.password),
            secure=True,
        )

    def find(self, episode):
        import cloudinary.api
        from cloudinary.exceptions import NotFound
        try:
            info = cloudinary.api.resource(f"fruits-story/episode-{episode:03d}", resource_type="video")
            return info.get("secure_url")
        except NotFound:
            return None

    def upload(self, episode, file_path):
        import cloudinary.uploader
        result = cloudinary.uploader.upload_large(
            str(file_path), resource_type="video", chunk_size=6_000_000,
            public_id=f"fruits-story/episode-{episode:03d}", overwrite=False,
            unique_filename=False, use_filename=False,
        )
        url = result.get("secure_url")
        if not url or not url.startswith("https://"):
            raise RuntimeError("Cloudinary n'a pas renvoyé d'URL vidéo HTTPS")
        return url


def captions():
    path = BASE / "captions.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def caption_for(episode: int, captions_map: dict):
    info = captions_map.get(str(episode), {})
    title = info.get("title") or f"Fruits Story — Épisode {episode}"
    description = info.get("description") or (
        f"🍓 La suite de Fruits Story ! Découvrez l'épisode {episode} et dites-nous votre avis en commentaire."
    )
    marker = f"#FruitsEP{episode:03d}"
    text = (f"{title}\n{description}\nÉpisode {episode} | #FruitsStory #AnimationIA #MiniSerie {marker}")
    return title, text


def episodes_from_clips(clips, start_episode):
    """Only complete consecutive A+B pairs; don't jump over missing episodes."""
    output = []
    current = start_episode
    while (current, "A") in clips and (current, "B") in clips:
        output.append(current)
        current += 1
    return output


def parse_existing(posts):
    already = set()
    queued = {}
    for post in posts:
        channel = post.get("channelId")
        status = post.get("status")
        if status in ("scheduled", "sending"):
            queued[channel] = queued.get(channel, 0) + 1
        match = MARKER_RE.search(post.get("text") or "")
        if match and status in ("scheduled", "sending", "sent", "error"):
            already.add((channel, int(match.group(1))))
    return already, queued


def next_time(episode: int, cfg: dict, now: datetime, reserved: set[date]):
    wanted = cfg["start_date"] + timedelta(days=episode - cfg["start_episode"])
    min_date = now.date() if now.time() < time(cfg["post_hour"], cfg["post_minute"]) else now.date() + timedelta(days=1)
    day = max(wanted, min_date)
    while day in reserved:
        day += timedelta(days=1)
    scheduled = datetime.combine(day, time(cfg["post_hour"], cfg["post_minute"]), cfg["timezone"])
    return scheduled


def run():
    cfg = config()
    now = datetime.now(cfg["timezone"])
    publishing = os.getenv("PUBLISH_ENABLED", "false").lower() == "true"
    print(f"Fruits Autopilot | {now.isoformat()} | mode={'PUBLICATION' if publishing else 'SIMULATION'}")
    print("Prochains épisodes recherchés: FRUITS_EP014_A.mp4 + FRUITS_EP014_B.mp4, etc.")
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        print("Google Drive non autorisé : ajouter le secret GOOGLE_SERVICE_ACCOUNT_JSON.")
        return 0 if not publishing else 2
    drive = DriveSources(env("GOOGLE_SERVICE_ACCOUNT_JSON"))
    clips = drive.list_clips(cfg["drive_source_folder_id"])
    episodes = episodes_from_clips(clips, cfg["start_episode"])
    print(f"Clips reconnus: {len(clips)} | Nouveaux épisodes complets: {episodes}")
    if not episodes:
        print("Aucun nouvel épisode complet. Aucune publication créée.")
        return 0
    if not os.getenv("BUFFER_API_KEY"):
        print("Buffer non autorisé : ajouter le secret BUFFER_API_KEY.")
        return 0 if not publishing else 2
    buffer = BufferAPI(env("BUFFER_API_KEY"))
    org = buffer.organization_id(os.getenv("BUFFER_ORG_ID") or None)
    channels = buffer.channels(org)
    if not channels:
        raise RuntimeError("Aucun compte Instagram/TikTok/YouTube autorisé dans Buffer")
    existing = buffer.posts(org, list(channels.values()))
    already, queued = parse_existing(existing)
    reserved = {s: set() for s in channels}
    for item in existing:
        dt = item.get("dueAt")
        s = next((s for s, id_ in channels.items() if id_ == item.get("channelId")), None)
        if s and dt and item.get("status") in ("scheduled", "sending"):
            try:
                reserved[s].add(datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(cfg["timezone"]).date())
            except ValueError:
                pass
    caption_map = captions()
    cloud = None
    failed = False
    for episode in episodes[:cfg["max_episodes_per_run"]]:
        targets = []
        for service, channel_id in channels.items():
            if (channel_id, episode) in already:
                print(f"Épisode {episode} {service}: déjà traité; ignoré")
                continue
            if queued.get(channel_id, 0) >= cfg["max_buffer_pending"]:
                print(f"Épisode {episode} {service}: file pleine, reporté")
                continue
            when = next_time(episode, cfg, now, reserved[service])
            targets.append((service, channel_id, when))
        if not targets:
            continue
        print(f"Épisode {episode} | " + ", ".join(f"{s} {when.isoformat()}" for s, _, when in targets))
        if not publishing:
            continue
        if cloud is None:
            cloud = CloudVideo(env("CLOUDINARY_URL"))
        media_url = cloud.find(episode)
        if not media_url:
            with tempfile.TemporaryDirectory(prefix=f"fruit_ep{episode:03d}_") as tmp:
                folder = Path(tmp)
                a, b, output = folder / "A.mp4", folder / "B.mp4", folder / "final.mp4"
                drive.download(clips[(episode, "A")], a)
                drive.download(clips[(episode, "B")], b)
                make_video(a, b, output)
                media_url = cloud.upload(episode, output)
        title, body = caption_for(episode, caption_map)
        for service, channel_id, when in targets:
            try:
                post_id = buffer.create(channel_id=channel_id, service=service,
                                        when=when, url=media_url, title=title,
                                        caption=body, for_kids=cfg["youtube_made_for_kids"])
                print(f"✅ Épisode {episode} {service}: programmé pour {when.isoformat()} (id={post_id})")
                queued[channel_id] = queued.get(channel_id, 0) + 1
                reserved[service].add(when.date())
                already.add((channel_id, episode))
            except Exception as exc:
                failed = True
                print(f"❌ Épisode {episode} {service}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as error:
        print(f"❌ Erreur : {error}", file=sys.stderr)
        sys.exit(1)
