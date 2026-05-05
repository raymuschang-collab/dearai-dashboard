"""Upload a file to Google Drive root and print its shareable link."""
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from auth import get_credentials


def upload(local_path: Path) -> None:
    if not local_path.exists():
        sys.exit(f"File not found: {local_path}")

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    metadata = {"name": local_path.name}
    media = MediaFileUpload(str(local_path), mimetype="text/html", resumable=True)

    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    file_id = file["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    refreshed = service.files().get(fileId=file_id, fields="webViewLink").execute()

    print(f"Uploaded: {file['name']}")
    print(f"File ID:  {file_id}")
    print(f"Link:     {refreshed['webViewLink']}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "pharaoh_king_gallery_PRODUCTION_v2.html"
    upload(target)
