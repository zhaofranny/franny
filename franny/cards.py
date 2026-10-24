"""Original local typography PNGs; no third-party note assets or external calls."""
import io
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

THEMES = {'奶油绿':('#F4F0E6','#174A3B','#D96A3C'), '黑金':('#171F1C','#F4E7C6','#E5B65B')}

def font_path():
    for p in [os.getenv('CJK_FONT_PATH',''), '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/System/Library/Fonts/PingFang.ttc', 'C:/Windows/Fonts/msyh.ttc']:
        if p and Path(p).is_file(): return p
    raise ValueError('缺少中文字体。云端请安装packages.txt，本地设置CJK_FONT_PATH指向中文字体文件。')

def lines(text, font, width):
    result = []
    for paragraph in text.split('\n'):
        line = ''
        for ch in paragraph:
            if font.getlength(line + ch) > width and line:
                result.append(line); line = ch
            else: line += ch
        result.append(line)
    return result

def draw_text(draw, text, xy, width, size, color, max_height):
    for candidate in range(size, 23, -2):
        font = ImageFont.truetype(font_path(), candidate)
        wrapped = lines(text, font, width)
        step = int(candidate * 1.6)
        if len(wrapped) * step <= max_height:
            for index,line in enumerate(wrapped):
                draw.text((xy[0],xy[1]+index*step),line,font=font,fill=color)
            return
    raise ValueError('卡片文字过长，请缩短后重新排版')

def render_cards(payload, theme='奶油绿'):
    from .editorial import public_text
    from .health import review
    if review(public_text(payload))['status'] == 'blocked':
        raise ValueError('请先修正高风险内容')
    bg, ink, accent = THEMES[theme]
    pages = [{'heading':payload['title'],'text':'省力习惯 / 日常搭配 / 循序渐进'}] + payload.get('cards',[])
    output = {}
    for index,page in enumerate(pages):
        im=Image.new('RGB',(1080,1440),bg); d=ImageDraw.Draw(im)
        d.rounded_rectangle((64,64,1016,1376),radius=36,outline=ink,width=3)
        d.rectangle((104,200,240,212), fill=accent)
        draw_text(d,'FRANNY / 省力生活研究所',(104,110),870,28,ink,80)
        draw_text(d,page['heading'],(104,300),850,86 if index==0 else 66,ink,430)
        draw_text(d,page['text'],(104,800 if index==0 else 760),850,38,ink,400)
        footer = '风格示例 · 非在线生成' if payload.get('mode') != 'openai' else '健康科普 · 个体情况不同'
        draw_text(d,footer,(104,1260),740,25,ink,70)
        draw_text(d,f'{index+1:02d}/{len(pages):02d}',(890,1260),100,24,accent,70)
        buf=io.BytesIO();im.save(buf,format='PNG');output[f'{index+1:02d}.png']=buf.getvalue()
    return output
