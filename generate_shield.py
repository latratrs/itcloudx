import os
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
import io

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

print("🎨 Generating shield with Imagen 4.0...")

response = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="""A shield icon logo. Classic heraldic shield shape: rounded arch at top, straight sides, pointed bottom tip. Glowing cyan teal border outline, very dark navy blue fill inside. Bold bright yellow checkmark in center. Clean flat vector style, no text, dark background, centered icon.""",
    config=types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio="1:1",
    )
)

shield_img = Image.open(io.BytesIO(response.generated_images[0].image.image_bytes)).convert("RGBA")
print(f"✅ Shield generated: {shield_img.size}")

W, H = 800, 800
NAVY      = (13, 17, 30)
YELLOW    = (251, 191, 36)
WHITE     = (255, 255, 255)
TEAL_TEXT = (20, 184, 166)
GREY      = (148, 163, 184)
TEAL_DIM  = (13, 115, 119)

canvas = Image.new("RGB", (W, H), NAVY)
draw   = ImageDraw.Draw(canvas)

for y in range(H):
    t=y/H
    draw.line([(0,y),(W,y)],fill=(int(13+5*t),int(17+8*t),int(30+15*t)))
for x in range(0,W,50): draw.line([(x,0),(x,H)],fill=(25,38,65),width=1)
for y in range(0,H,50): draw.line([(0,y),(W,y)],fill=(25,38,65),width=1)
for r in range(140,0,-18):
    c=int(10*(1-r/140))
    draw.ellipse([(-r,-r),(r,r)],fill=(10,80+c,90+c))
for r in range(110,0,-18):
    c=int(10*(1-r/110))
    draw.ellipse([(W-r,H-r),(W+r,H+r)],fill=(10,70+c,80+c))

shield_resized = shield_img.resize((220,220), Image.LANCZOS)
canvas.paste(shield_resized, ((W-220)//2, 108), shield_resized)

try:
    fb=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",78)
    fs=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",26)
    ft=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",19)
    fy=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",18)
except:
    fb=fs=ft=fy=ImageFont.load_default()

draw2=ImageDraw.Draw(canvas)

t_w=draw2.textbbox((0,0),"Trade",font=fb)[2]
s_w=draw2.textbbox((0,0),"Shield",font=fb)[2]
tx=(W-t_w-s_w-draw2.textbbox((0,0)," AI",font=fb)[2])//2; ty=408
draw2.text((tx,ty),"Trade",font=fb,fill=WHITE)
draw2.text((tx+t_w,ty),"Shield",font=fb,fill=TEAL_TEXT)
draw2.text((tx+t_w+s_w,ty)," AI",font=fb,fill=YELLOW)

by_t="powered by ITCloudX.com"
by_w=draw2.textbbox((0,0),by_t,font=fy)[2]
draw2.text(((W-by_w)//2,500),by_t,font=fy,fill=GREY)
draw2.line([(100,538),(W-100,538)],fill=TEAL_DIM,width=1)

hl="The Trade News Blog"
hl_w=draw2.textbbox((0,0),hl,font=fs)[2]
draw2.text(((W-hl_w)//2,554),hl,font=fs,fill=WHITE)

badges=["HS Code","OFAC Screening","PDF Reports"]
bws=[draw2.textbbox((0,0),b,font=ft)[2]+26 for b in badges]
bx=(W-sum(bws)-28)//2
for badge,bw in zip(badges,bws):
    draw2.rounded_rectangle([bx,618,bx+bw,651],radius=5,fill=(15,50,60),outline=TEAL_DIM,width=1)
    draw2.text((bx+13,626),badge,font=ft,fill=TEAL_TEXT)
    bx+=bw+14

draw2.rectangle([(0,H-5),(W,H)],fill=YELLOW)

out=os.path.expanduser("~/itcloudx/astrowind/src/assets/images/default.jpg")
canvas.save(out,"JPEG",quality=92)
print(f"✅ Saved to: {out}")
print("   Run ~/itcloudx/publish.sh to deploy")
