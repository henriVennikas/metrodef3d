"""Explicit read-only overlay loader. Never rewrites original metadata or sidecars."""
import hashlib,json
from pathlib import Path

def load_visible_reference(original_sidecar, overlay_directory):
    original_sidecar=Path(original_sidecar);overlay_directory=Path(overlay_directory)
    manifest=json.loads((overlay_directory/'manifest.json').read_text())
    entry=manifest['corrections'].get(original_sidecar.stem)
    raw=original_sidecar.read_bytes()
    if entry is None:return json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=entry['original_sha256']:
        raise ValueError('Original sidecar does not match the correction manifest')
    corrected_path=overlay_directory/entry['file']
    data=corrected_path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise ValueError('Corrected sidecar checksum mismatch')
    return json.loads(data)
