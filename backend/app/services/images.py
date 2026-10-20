PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
SUPPORTED = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def has_image_signature(data: bytes, content_type: str) -> bool:
    kind = content_type.lower()
    if kind == "image/jpeg":
        return len(data) >= 3 and data[0] == 0xFF and data[1] == 0xD8 and data[2] == 0xFF
    if kind == "image/png":
        return len(data) >= 8 and data[:8] == PNG
    if kind == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False
