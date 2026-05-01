"""
drive.py — Google Drive upload helpers
"""

import os
from pathlib import Path

from modules.config import DRIVE_FOLDER_ID, UPLOAD_TO_DRIVE
from modules.console_utils import ok, warn, info
from modules.sheet import update_row, _get_creds   # reuse auth


def upload_file(file_path: str, folder_name: str = None) -> str:
    """Upload a single file to Drive root folder. Returns webViewLink or ''."""
    file_path = str(file_path)
    if not file_path or not os.path.exists(file_path):
        warn(f"[drive] File not found: {file_path}")
        return ""
    if not DRIVE_FOLDER_ID:
        warn("[drive] DRIVE_FOLDER_ID not set — skipping")
        return ""
    if not folder_name:
        folder_name = Path(file_path).stem

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        creds   = _get_creds()
        service = build("drive", "v3", credentials=creds)

        # Find or create sub-folder
        resp = service.files().list(
            q=(f"name='{folder_name}' and '{DRIVE_FOLDER_ID}' in parents "
               f"and mimeType='application/vnd.google-apps.folder'"),
            fields="files(id)"
        ).execute()
        if resp.get("files"):
            folder_id = resp["files"][0]["id"]
        else:
            meta = {"name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [DRIVE_FOLDER_ID]}
            folder_id = service.files().create(body=meta, fields="id").execute()["id"]

        file_meta = {"name": os.path.basename(file_path), "parents": [folder_id]}
        media     = MediaFileUpload(file_path, resumable=True)
        result    = service.files().create(
            body=file_meta, media_body=media, fields="id,webViewLink"
        ).execute()
        link = result.get("webViewLink", "")
        ok(f"[drive] Uploaded → {link}")
        return link
    except Exception as e:
        warn(f"[drive] Upload failed: {e}")
        return ""


def upload_story(safe_name: str, video_path, thumb_path,
                 sheet_row_num: int = None) -> dict:
    """
    Upload processed video + thumbnail for a story.
    Returns {"video_link": str, "thumb_link": str}
    """
    result = {"video_link": "", "thumb_link": ""}

    if not UPLOAD_TO_DRIVE:
        info("[drive] UPLOAD_TO_DRIVE disabled — local only")
        return result
    if not DRIVE_FOLDER_ID:
        warn("[drive] DRIVE_FOLDER_ID not set")
        return result
    if not video_path or not os.path.exists(str(video_path)):
        warn(f"[drive] Video missing: {video_path}")
        return result

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        creds   = _get_creds()
        service = build("drive", "v3", credentials=creds)

        # Create story sub-folder
        folder_meta = {"name": safe_name,
                       "mimeType": "application/vnd.google-apps.folder",
                       "parents": [DRIVE_FOLDER_ID]}
        folder      = service.files().create(body=folder_meta,
                                              fields="id,webViewLink").execute()
        folder_id   = folder["id"]

        # Upload video
        vid_meta  = {"name": os.path.basename(str(video_path)), "parents": [folder_id]}
        vid_media = MediaFileUpload(str(video_path), resumable=True)
        vid_file  = service.files().create(body=vid_meta, media_body=vid_media,
                                            fields="id,webViewLink").execute()
        result["video_link"] = vid_file.get("webViewLink", "")
        ok(f"[drive] Video → {result['video_link']}")

        if sheet_row_num and result["video_link"]:
            try:
                from modules.sheet import SCHEMA_VIDEOS
                update_row("2_Videos", sheet_row_num, SCHEMA_VIDEOS, Drive_Link=result["video_link"])
            except Exception as se:
                warn(f"[sheet] Drive_Link write: {se}")

        # Upload thumbnail (non-fatal)
        if thumb_path and os.path.exists(str(thumb_path)):
            try:
                thumb_meta  = {"name": os.path.basename(str(thumb_path)),
                               "parents": [folder_id]}
                thumb_media = MediaFileUpload(str(thumb_path), resumable=True)
                thumb_file  = service.files().create(body=thumb_meta,
                                                      media_body=thumb_media,
                                                      fields="id,webViewLink").execute()
                result["thumb_link"] = thumb_file.get("webViewLink", "")
                ok(f"[drive] Thumbnail → {result['thumb_link']}")
                if sheet_row_num and result["thumb_link"]:
                    try:
                        from modules.sheet import SCHEMA_VIDEOS
                        update_row("2_Videos", sheet_row_num, SCHEMA_VIDEOS, DriveImg_Link=result["thumb_link"])
                    except Exception: pass
            except Exception as te:
                warn(f"[drive] Thumbnail upload failed (non-fatal): {te}")

        ok("[drive] Story upload complete")
        return result
    except Exception as e:
        warn(f"[drive] Story upload failed: {e}")
        return result
