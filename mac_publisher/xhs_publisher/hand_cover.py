"""Local reference-inspired cover renderer; uses local fonts, never copies source images."""
import hashlib
import math
import random
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont


def handwriting_font(fallback):
    candidates=['/System/Library/Fonts/Supplemental/Kaiti.ttc','/System/Library/Fonts/Supplemental/STKaiti.ttf','/System/Library/Fonts/STKaiti.ttf','/Library/Fonts/Kaiti.ttf','/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc']
    for name in candidates:
        if Path(name).is_file():return name
    return fallback


def render_cover(text,fallback):
    image=Image.new('RGB',(1080,1440),'white')
    font_path=handwriting_font(fallback)
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if len(lines)==1:
        # Existing drafts without intentional line breaks remain readable.
        text=lines[0];step=max(1,math.ceil(len(text)/3));lines=[text[i:i+step] for i in range(0,len(text),step)]
    middle=len(lines)//2
    positions=[.39,.60,.80] if len(lines)==3 else [.36+i*.55/max(1,len(lines)-1) for i in range(len(lines))]
    randomizer=random.Random(int(hashlib.sha256(text.encode()).hexdigest()[:12],16))
    for index,(line,position) in enumerate(zip(lines,positions)):
        size=200 if index==middle else 176
        while True:
            font=ImageFont.truetype(font_path,size)
            width=ImageDraw.Draw(image).textlength(line,font=font)
            if width<=960 or size<=40:break
            size-=4
        bbox=ImageDraw.Draw(image).textbbox((0,0),line,font=font,stroke_width=1)
        height=bbox[3]-bbox[1]
        top=min(int(1440*position),1360-height)
        left=(1080-width)/2
        if index==middle:
            for offset in [-12,3,15]:
                stroke=Image.new('RGBA',image.size,(0,0,0,0));pen=ImageDraw.Draw(stroke)
                y=top+height//2+offset
                points=[(55,y+randomizer.randint(-12,12)),(360,y+randomizer.randint(-9,9)),(720,y+randomizer.randint(-9,9)),(1025,y+randomizer.randint(-12,12))]
                thickness=height+40
                for x in range(35,1080,155):
                    py=y+randomizer.randint(-15,15)
                    rx=140+randomizer.randint(-8,12);ry=thickness//2+randomizer.randint(-10,12)
                    pen.ellipse((x-rx,py-ry,x+rx,py+ry),fill=(255,238,0,95))
                image=Image.alpha_composite(image.convert('RGBA'),stroke).convert('RGB')
        layer=Image.new('RGBA',image.size,(0,0,0,0));pen=ImageDraw.Draw(layer)
        key='邪修' if '邪修' in line else next((w for w in ['碳水','主食','晚餐','馒头','绿茶','减肥'] if w in line),line[:2])
        blue_start=line.find(key) if index==middle else -1
        x=left
        for char_index,char in enumerate(line):
            blue=blue_start>=0 and blue_start<=char_index<blue_start+len(key)
            pen.text((x,top),char,font=font,fill='#2966ED' if blue else '#111111',anchor='lt',stroke_width=1)
            x+=pen.textlength(char,font=font)
        layer=layer.rotate(randomizer.uniform(-.7,.7),resample=Image.Resampling.BICUBIC)
        image=Image.alpha_composite(image.convert('RGBA'),layer).convert('RGB')
    return image,Path(font_path).name
