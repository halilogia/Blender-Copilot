"""ViewportReader for capturing active 3D Viewport images in Blender.

Provides main-thread viewport rendering via GPU offscreen buffer and
in-memory PNG encoding using standard library zlib and struct.
Zero filesystem writes, zero scene mutation.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import struct
from typing import Any, Dict, Optional, Tuple
import zlib

try:
    import bpy
    import gpu
except ImportError:
    bpy = None
    gpu = None


def encode_png_rgba(width: int, height: int, rgba_bytes: bytes) -> bytes:
    """Encode raw RGBA bytes into standard PNG bytes in-memory.

    Uses standard library zlib and struct. Zero third-party dependencies.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        rgba_bytes: Flat RGBA byte sequence of length width * height * 4.

    Returns:
        Standard PNG binary bytes starting with b'\\x89PNG\\r\\n\\x1a\\n'.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    # OpenGL / GPU offscreen textures are bottom-up; PNG scanlines are top-down
    row_stride = width * 4
    raw_scanlines = bytearray()
    for y in range(height - 1, -1, -1):
        raw_scanlines.append(0)  # Filter type 0 (None)
        start = y * row_stride
        raw_scanlines.extend(rgba_bytes[start : start + row_stride])

    idat = zlib.compress(bytes(raw_scanlines), level=6)
    return header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def compute_fit_size(width: int, height: int, max_side: int) -> Tuple[int, int]:
    """Compute aspect-preserving fit size so longest side <= max_side.

    Pure Python. Returns (new_w, new_h). If already within bound, returns input.
    """
    longest = max(width, height)
    if longest <= max_side or longest <= 0:
        return width, height
    scale = max_side / float(longest)
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    return new_w, new_h


def downscale_rgba_nearest(
    src: bytes, src_w: int, src_h: int, dst_w: int, dst_h: int
) -> bytes:
    """Downscale flat RGBA bytes with nearest-neighbor sampling.

    Pure Python stdlib only. Used as LLM cost guard (e.g. 512 -> 256 thumbnail).
    Raises ValueError on dimension mismatch.
    """
    if len(src) != src_w * src_h * 4:
        raise ValueError(
            f"RGBA buffer size mismatch: got {len(src)}, expected {src_w * src_h * 4}."
        )
    if dst_w <= 0 or dst_h <= 0:
        raise ValueError(f"Destination dimensions must be positive, got {(dst_w, dst_h)}.")
    if dst_w == src_w and dst_h == src_h:
        return bytes(src)
    out = bytearray(dst_w * dst_h * 4)
    for y in range(dst_h):
        src_y = min(src_h - 1, int(y * src_h / dst_h))
        for x in range(dst_w):
            src_x = min(src_w - 1, int(x * src_w / dst_w))
            src_off = (src_y * src_w + src_x) * 4
            dst_off = (y * dst_w + x) * 4
            out[dst_off : dst_off + 4] = src[src_off : src_off + 4]
    return bytes(out)


class ViewportReader:
    """Reads and captures rendered 3D Viewport imagery into in-memory PNG format."""

    DEFAULT_WIDTH: int = 512
    DEFAULT_HEIGHT: int = 512
    MIN_DIMENSION: int = 64
    MAX_DIMENSION: int = 2048
    MAX_CACHE_SIZE: int = 10
    THUMBNAIL_SIDE: int = 256

    def __init__(self):
        # Bounded in-memory image store: image_id -> png_bytes
        self._cache: OrderedDict[str, bytes] = OrderedDict()

    def _resolve_view3d_context(self) -> Tuple[Any, Any]:
        """Resolve available 3D Viewport space and region in Blender.

        Searches active area, active screen, and available screens in order.

        Returns:
            Tuple of (SpaceView3D, Region).

        Raises:
            RuntimeError: If no 3D Viewport area is found.
        """
        # 1. Active area if VIEW_3D
        if bpy.context and hasattr(bpy.context, "area") and bpy.context.area:
            if bpy.context.area.type == "VIEW_3D":
                space = bpy.context.area.spaces.active
                region = next((r for r in bpy.context.area.regions if r.type == "WINDOW"), None)
                if space and region and hasattr(space, "region_3d") and space.region_3d:
                    return space, region

        # 2. Active screen's areas
        if bpy.context and hasattr(bpy.context, "screen") and bpy.context.screen:
            for area in bpy.context.screen.areas:
                if area.type == "VIEW_3D":
                    space = area.spaces.active
                    region = next((r for r in area.regions if r.type == "WINDOW"), None)
                    if space and region and hasattr(space, "region_3d") and space.region_3d:
                        return space, region

        # 3. Fallback across all screens (e.g. Layout, Modeling, Shading)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    space = area.spaces.active
                    region = next((r for r in area.regions if r.type == "WINDOW"), None)
                    if space and region and hasattr(space, "region_3d") and space.region_3d:
                        return space, region

        raise RuntimeError("No 3D Viewport (VIEW_3D) area found in current Blender session.")

    def capture(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        max_side: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Render active 3D Viewport into an in-memory PNG image.

        Guarantees zero scene mutation and zero filesystem leakage.

        Args:
            width: Desired image width in pixels (64 to 2048).
            height: Desired image height in pixels (64 to 2048).
            max_side: Optional cost-guard bound; longest side is downscaled
                with nearest-neighbor to fit within max_side (64-2048).
                None disables downscaling (backward compatible).

        Returns:
            Machine-readable metadata dict conforming to capture_viewport contract.
        """
        # Validate dimensions
        if not isinstance(width, int) or isinstance(width, bool) or width < self.MIN_DIMENSION or width > self.MAX_DIMENSION:
            raise ValueError(f"width must be an integer between {self.MIN_DIMENSION} and {self.MAX_DIMENSION}, got {width}.")
        if not isinstance(height, int) or isinstance(height, bool) or height < self.MIN_DIMENSION or height > self.MAX_DIMENSION:
            raise ValueError(f"height must be an integer between {self.MIN_DIMENSION} and {self.MAX_DIMENSION}, got {height}.")
        if max_side is not None:
            if not isinstance(max_side, int) or isinstance(max_side, bool) or max_side < self.MIN_DIMENSION or max_side > self.MAX_DIMENSION:
                raise ValueError(
                    f"max_side must be an integer between {self.MIN_DIMENSION} and {self.MAX_DIMENSION}, got {max_side}."
                )

        if bpy is None or gpu is None:
            raise RuntimeError("Blender runtime (bpy/gpu) is not available.")

        # Find 3D Viewport
        space, region = self._resolve_view3d_context()
        r3d = space.region_3d

        # Ensure GPU subsystem initialized (required in background mode)
        if hasattr(gpu, "init"):
            try:
                gpu.init()
            except Exception:
                pass

        # Create offscreen surface and render viewport
        off = gpu.types.GPUOffScreen(width, height)
        try:
            off.draw_view3d(
                scene=bpy.context.scene,
                view_layer=bpy.context.view_layer,
                view3d=space,
                region=region,
                view_matrix=r3d.view_matrix,
                projection_matrix=r3d.window_matrix,
                do_color_management=True,
                draw_background=True,
            )
            buf = off.texture_color.read()
            raw_bytes = bytes(buf)
        finally:
            off.free()

        # Optional cost-guard downscale before PNG encode
        out_w, out_h = width, height
        downscaled = False
        if max_side is not None:
            fit_w, fit_h = compute_fit_size(width, height, max_side)
            if (fit_w, fit_h) != (width, height):
                raw_bytes = downscale_rgba_nearest(raw_bytes, width, height, fit_w, fit_h)
                out_w, out_h = fit_w, fit_h
                downscaled = True

        # Encode to PNG in-memory
        png_bytes = encode_png_rgba(out_w, out_h, raw_bytes)
        image_hash = hashlib.sha256(png_bytes).hexdigest()[:12]
        image_id = f"vp_{image_hash}"

        # Store in bounded LRU cache
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        self._cache[image_id] = png_bytes

        meta: Dict[str, Any] = {
            "image_id": image_id,
            "width": out_w,
            "height": out_h,
            "format": "PNG",
            "mime_type": "image/png",
            "byte_size": len(png_bytes),
            "channels": 4,
        }
        if downscaled:
            meta["downscaled"] = True
            meta["requested"] = f"{width}x{height}"
        return meta

    def get_image_bytes(self, image_id: str) -> Optional[bytes]:
        """Retrieve raw PNG bytes from in-memory cache."""
        return self._cache.get(image_id)

    def clear_cache(self) -> None:
        """Clear all cached images from memory."""
        self._cache.clear()
