from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICO = ASSETS / "mistica_xamanico_moderno.ico"
PNG = ASSETS / "mistica_xamanico_moderno.png"


def estrela(draw, cx, cy, r1, r2, pontos, fill):
    pts = []
    for i in range(pontos * 2):
        ang = -math.pi / 2 + i * math.pi / pontos
        r = r1 if i % 2 == 0 else r2
        pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    draw.polygon(pts, fill=fill)


def gerar_base(tamanho=1024):
    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = tamanho // 2

    # fundo circular premium
    for raio in range(cx, 0, -1):
        t = raio / cx
        r = int(24 + 40 * (1 - t))
        g = int(18 + 18 * (1 - t))
        b = int(38 + 28 * (1 - t))
        a = 255
        draw.ellipse((cx - raio, cy - raio, cx + raio, cy + raio), fill=(r, g, b, a))

    # halo dourado
    for i in range(14):
        margin = 74 + i * 4
        alpha = max(18, 150 - i * 9)
        draw.ellipse((margin, margin, tamanho - margin, tamanho - margin), outline=(233, 185, 82, alpha), width=5)

    # lua crescente
    lua = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(lua)
    d2.ellipse((235, 185, 765, 795), fill=(239, 198, 103, 255))
    d2.ellipse((370, 145, 875, 760), fill=(35, 25, 50, 255))
    lua = lua.filter(ImageFilter.GaussianBlur(0.25))
    img.alpha_composite(lua)

    draw = ImageDraw.Draw(img)

    # cristal central
    cristal = [
        (cx, 250),
        (690, 430),
        (610, 760),
        (cx, 870),
        (414, 760),
        (334, 430),
    ]
    draw.polygon(cristal, fill=(70, 116, 83, 235), outline=(238, 196, 99, 255))
    draw.line([(cx, 250), (cx, 870)], fill=(205, 232, 172, 170), width=9)
    draw.line([(334, 430), (690, 430)], fill=(205, 232, 172, 120), width=7)
    draw.line([(414, 760), (610, 760)], fill=(205, 232, 172, 90), width=6)

    # folhas / penas laterais
    for lado in (-1, 1):
        for idx, y in enumerate((440, 535, 630)):
            x = cx + lado * (190 + idx * 16)
            bbox = (x - 70, y - 34, x + 70, y + 34)
            draw.ellipse(bbox, fill=(89, 123, 70, 185), outline=(206, 170, 79, 185), width=4)
            draw.line((cx + lado * 78, y, x + lado * 58, y), fill=(224, 191, 104, 160), width=5)

    # estrela mística
    estrela(draw, cx, 165, 42, 18, 8, (245, 211, 122, 255))
    draw.ellipse((cx - 21, 144, cx + 21, 186), fill=(255, 236, 166, 255))

    # pontos de brilho
    for x, y, r in [(248, 306, 10), (780, 318, 8), (268, 760, 7), (760, 742, 9), (512, 930, 6)]:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(244, 211, 130, 210))

    return img


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    img = gerar_base(1024)
    img.save(PNG)
    tamanhos = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ICO, sizes=tamanhos)
    print("Icone gerado:", ICO)
    print("PNG gerado:", PNG)


if __name__ == "__main__":
    main()
