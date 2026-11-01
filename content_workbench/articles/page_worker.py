"""Local Pillow paginator. Each line/image is placed within an explicit page box."""
import argparse
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT, MARGIN = 1080,1440,84
TOP,BOTTOM=110,1320

def render_pages(data, destination, font_path):
    directory=Path(destination);directory.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype(str(font_path),38)
    title_font=ImageFont.truetype(str(font_path),52)
    small=ImageFont.truetype(str(font_path),25)
    pages=[];canvas=None;draw=None;y=TOP;records=[]
    def flush():
        nonlocal canvas,draw,y,records
        if canvas is not None:
            index=len(pages)+1
            draw.text((MARGIN,HEIGHT-72),str(index),fill='#9b7651',font=small)
            path=directory/('page-%03d.png'%index);canvas.save(path)
            pages.append({'file':path.name,'blocks':records})
        if len(pages)>=100:raise ValueError('内容超过 100 页，请拆分文章')
        canvas=Image.new('RGB',(WIDTH,HEIGHT),'#fffdf8');draw=ImageDraw.Draw(canvas);y=TOP;records=[]
    flush()
    def lines(text, selected_font):
        result=[]
        for original in str(text).split('\n'):
            line=''
            for char in original:
                if line and draw.textlength(line+char,font=selected_font)>WIDTH-2*MARGIN:
                    result.append(line);line=char
                else:line+=char
            result.append(line)
        return result
    def text_block(text, selected_font, color, line_height):
        nonlocal y
        for line in lines(text,selected_font):
            if y+line_height>BOTTOM:flush()
            draw.text((MARGIN,y),line,font=selected_font,fill=color)
            records.append({'kind':'text','text':line,'y':y,'height':line_height})
            y+=line_height
        y+=24
    def pictures(position):
        nonlocal y
        for entry in data.get('images',[]):
            if entry['after_paragraph']!=position:continue
            with Image.open(entry['path']) as raw:
                raw.load();picture=ImageOps.exif_transpose(raw).convert('RGB')
            picture.thumbnail((WIDTH-2*MARGIN,850))
            if y+picture.height+24>BOTTOM:flush()
            canvas.paste(picture,((WIDTH-picture.width)//2,y))
            records.append({'kind':'image','asset_id':entry['asset_id'],'y':y,'height':picture.height})
            y+=picture.height+24
            if entry.get('description'):text_block(entry['description'],small,'#786e63',38)
    text_block(data['title'],title_font,'#342b20',76)
    pictures(0)
    for index,paragraph in enumerate(re.split(r'\n\s*\n',data['text'].strip()),1):
        text_block(paragraph,font,'#302d29',62)
        pictures(index)
    # Final page only; avoid generating an empty trailing page.
    index=len(pages)+1
    draw.text((MARGIN,HEIGHT-72),str(index),fill='#9b7651',font=small)
    path=directory/('page-%03d.png'%index);canvas.save(path)
    pages.append({'file':path.name,'blocks':records})
    (directory/'pages.json').write_text(json.dumps({'width':WIDTH,'height':HEIGHT,'pages':pages},ensure_ascii=False))
    return pages

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--font',required=True)
    args=parser.parse_args()
    render_pages(json.loads(Path(args.input).read_text()),args.output,args.font)
