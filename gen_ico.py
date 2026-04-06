"""Generate .ico file from logo PNG."""
from PIL import Image

img = Image.open("acset/KEYTECH-e1718420445743-removebg-preview.png")
img = img.convert("RGBA")

# Resize to square for icon
size = max(img.size)
square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
offset = ((size - img.width) // 2, (size - img.height) // 2)
square.paste(img, offset)

square.save(
    "acset/icon.ico",
    format="ICO",
    sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
)
print("ICO created: acset/icon.ico")
