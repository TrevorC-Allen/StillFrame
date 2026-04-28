from __future__ import annotations

import platform
import subprocess
from typing import Optional

from fastapi import APIRouter, HTTPException


router = APIRouter(tags=["dialog"])


@router.post("/dialog/folder")
def choose_folder() -> dict[str, Optional[str]]:
    if platform.system() != "Darwin":
        raise HTTPException(status_code=501, detail="Native folder picker is only implemented on macOS")

    script = """
    try
      set chosenFolder to choose folder with prompt "Choose a StillFrame media folder"
      return POSIX path of chosenFolder
    on error number -128
      return ""
    end try
    """
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip() or "Folder picker failed")

    path = result.stdout.strip().rstrip("/")
    return {"path": path or None}
