from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).resolve().parents[1]/"desktop"/"assets"
root.mkdir(parents=True,exist_ok=True)
img=Image.new("RGBA",(256,256),(15,27,42,255))
draw=ImageDraw.Draw(img)
draw.rounded_rectangle((16,16,240,240),radius=62,fill=(22,48,60,255))
draw.ellipse((32,32,224,224),outline=(111,228,177,255),width=12)
draw.line([(52,134),(88,134),(111,86),(144,183),(167,116),(190,137),(207,137)],fill=(145,246,198,255),width=14,joint="curve")
img.save(root/"icon.ico",format="ICO",sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
img.resize((32,32),Image.Resampling.LANCZOS).save(root/"tray.png")
print("Created desktop/assets/icon.ico and tray.png")
