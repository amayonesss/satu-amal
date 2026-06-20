from PIL import Image
import sys

try:
    img = Image.open(r"C:\Users\Elitebook\.gemini\antigravity\brain\3c9a829d-c005-489b-a551-85fb9005cfc0\media__1778036050951.png")
    img = img.convert('RGB')
    width, height = img.size
    r, g, b = img.getpixel((width//2, height//2))
    print(f"#{r:02x}{g:02x}{b:02x}")
except Exception as e:
    print("Error:", e)
