#!/usr/bin/env python3
"""
AI Short Video Generator - Runs on GitHub Actions
Generates vertical 9:16 short videos with TTS, images, captions & FFmpeg
"""
import os, sys, json, tempfile, subprocess, random, textwrap
from pathlib import Path
from datetime import datetime

# === CONFIG ===
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
OUTPUT_DIR = Path("output")
TEMP_DIR = Path("temp")

# === TOPICS ===
TOPICS = [
    {"title": "每天一个赚钱冷知识", "category": "money"},
    {"title": "30秒学会一个技巧", "category": "tips"},
    {"title": "今天才知道的真相", "category": "facts"},
    {"title": "外贸人的一天", "category": "business"},
    {"title": "冷门暴利小生意", "category": "money"},
]

SCRIPTS = {
    "money": [
        "你知道吗？有人专门倒卖过期域名，一个月赚五位数。他们抢注那些曾经有流量的老域名，挂上广告或者转卖，成本只要几十块。",
        "闲鱼上有种生意叫'信息差套利'。1688上5块钱的东西，换个标题加个滤镜，挂29包邮，一天能出几十单。",
        "跨境电商最简单的玩法：从1688拿货，挂到eBay上卖。一个车载手机支架进价3块，卖到美国就是12美元。",
    ],
    "tips": [
        "电脑卡了别急着换，先试试这个：Win+R输入temp，回车，Ctrl+A全选删除。瞬间多出几个G空间。",
        "手机充电慢？用牙签清理一下充电口的灰尘。大部分'电池老化'其实只是接触不良。",
        "Excel里按Ctrl+E，可以自动识别你的输入规律，一秒填充几百行数据。这个功能90%的人不知道。",
    ],
    "facts": [
        "麦当劳最大的利润来源不是汉堡，是房地产。它拥有全球最值钱的商业地产组合之一，靠收租比卖汉堡赚得多。",
        "你手机里的GPS定位精度能达到3米，靠的是爱因斯坦相对论。卫星上的时钟每天快38微秒，不修正的话定位误差会每天累积10公里。",
        "星巴克故意把你的名字写错，因为这会让更多人拍照发朋友圈吐槽，等于免费广告。这个策略叫'可控失误营销'。",
    ],
    "business": [
        "外贸新人最容易犯的错：一上来就做独立站。正确顺序是先上eBay/Amazon验证产品，有单了再建站。",
        "做跨境生意的核心不是语言，是选品。老外愿意花15美元买的东西，在1688上可能只要15块人民币。差距越大的品类越赚钱。",
    ],
}

def run(cmd):
    print(f"  $ {cmd[:100]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠ {result.stderr[:200]}")
    return result

def generate_video(script_text, title, output_name):
    TEMP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    audio_file = TEMP_DIR / "audio.mp3"
    bg_image = TEMP_DIR / "bg.jpg"
    caption_img = TEMP_DIR / "caption.png"
    output_file = OUTPUT_DIR / output_name
    
    print(f"\n🎬 Generating: {title}")
    print(f"   Script: {script_text[:80]}...")
    
    # Step 1: Text-to-Speech (edge-tts - FREE, no API key)
    print("   1/4 Generating voice...")
    # Save text to file for edge-tts
    text_file = TEMP_DIR / "script.txt"
    text_file.write_text(script_text, encoding='utf-8')
    
    # edge-tts command
    r = run(f'edge-tts --voice zh-CN-XiaoxiaoNeural -f "{text_file}" --write-media "{audio_file}"')
    if not audio_file.exists() or audio_file.stat().st_size < 1000:
        # Fallback: use espeak or generate silence
        print("   ⚠ edge-tts failed, generating silence...")
        run(f'ffmpeg -f lavfi -i anullsrc=r=24000:cl=mono -t 15 -q:a 9 -acodec libmp3lame "{audio_file}" -y')
    
    # Get audio duration
    r = run(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_file}"')
    duration = float(r.stdout.strip() or 15)
    print(f"   Duration: {duration:.1f}s")
    
    # Step 2: Generate background image with text baked in
    print("   2/4 Creating background with captions...")
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (VIDEO_WIDTH, VIDEO_HEIGHT), (18, 18, 32))
        draw = ImageDraw.Draw(img)
        
        # Gradient background
        for i in range(0, VIDEO_HEIGHT, 3):
            color = (15 + i//35, 15 + i//45, 28 + i//25)
            draw.line([(0, i), (VIDEO_WIDTH, i)], fill=color, width=3)
        
        # Find Chinese font
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font = None
        font_title = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 44)
                    font_title = ImageFont.truetype(fp, 60)
                    break
                except:
                    continue
        if font is None:
            font = ImageFont.load_default()
            font_title = font
        
        # Draw title at top
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tx = (VIDEO_WIDTH - bbox[2]) // 2
        # Title background
        draw.rectangle([0, 60, VIDEO_WIDTH, 140], fill=(245, 158, 11, 200))
        draw.text((tx, 75), title, font=font_title, fill=(255, 255, 255))
        
        # Draw script text in center
        wrapper = textwrap.TextWrapper(width=16)
        lines = wrapper.wrap(script_text)[:7]
        
        line_height = 65
        total_h = len(lines) * line_height
        y = (VIDEO_HEIGHT - total_h) // 2 + 50
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (VIDEO_WIDTH - bbox[2]) // 2
            # Shadow + highlight
            draw.text((x+3, y+3), line, font=font, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
            y += line_height
        
        # Footer text
        footer = "AI Generated · PricePulse"
        bbox = draw.textbbox((0, 0), footer, font=font)
        fx = (VIDEO_WIDTH - bbox[2]) // 2
        draw.text((fx, VIDEO_HEIGHT - 100), footer, font=font, fill=(150, 150, 170))
        
        img.save(bg_image, 'JPEG', quality=90)
        print("   Background + captions rendered with PIL")
        
    except Exception as e:
        print(f"   ⚠ PIL error: {e}, fallback to solid bg")
        run(f'ffmpeg -f lavfi -i color=c=0x121220:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1 -frames:v 1 "{bg_image}" -y')
    
    # Step 3: Simple FFmpeg - image + audio
    print(f"   3/3 Compiling video ({duration:.1f}s)...")
    cmd = (
        f'ffmpeg -loop 1 -i "{bg_image}" -i "{audio_file}" '
        f'-c:v libx264 -preset ultrafast -crf 28 -tune stillimage '
        f'-c:a aac -b:a 128k -t {duration} '
        f'-pix_fmt yuv420p -shortest '
        f'"{output_file}" -y'
    )
    
    run(cmd)
    
    if output_file.exists():
        size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"\n✅ DONE: {output_file} ({size_mb:.1f}MB, {duration:.0f}s)")
    else:
        print(f"\n❌ FAILED: output not created")
    
    return output_file.exists()

def main():
    print("=" * 50)
    print("  AI Short Video Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # Pick random topic + script
    topic = random.choice(TOPICS)
    scripts = SCRIPTS.get(topic["category"], SCRIPTS["money"])
    script_text = random.choice(scripts)
    
    # Generate filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"short_{ts}.mp4"
    
    success = generate_video(script_text, topic["title"], output_name)
    
    if success:
        print(f"\n📱 Video ready: output/{output_name}")
        print(f"   Upload to TikTok/Douyin/YouTube Shorts")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
