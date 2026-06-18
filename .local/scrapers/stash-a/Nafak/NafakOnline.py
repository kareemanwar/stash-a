import sys
from pathlib import Path
from typing import Any

import Nafak

sys.path.append(str(Path(__file__).resolve().parents[1]))

from _shared.online_hosts import enhance_online_media, remove_internal_online_media_fields


ORIGINAL_BUILD_ONLINE_MEDIA = Nafak.build_online_media


def build_online_media(*args: Any, **kwargs: Any) -> dict[str, Any]:
    media = ORIGINAL_BUILD_ONLINE_MEDIA(*args, **kwargs)
    page_url = kwargs.get("url")
    if isinstance(page_url, str):
        media = enhance_online_media(
            media,
            page_url,
            user_agent=Nafak.USER_AGENT,
            source_slug=Nafak.STUDIO_SLUG,
            clean_text=Nafak.clean_text,
        )

    return remove_internal_online_media_fields(media)


Nafak.build_online_media = build_online_media
Nafak.main()
