# Prompts para imagens finais do Módulo 2 — Xamanismo

> Anexo técnico de `docs/imagens-escola.md`, que é o documento central da
> auditoria visual da Escola e da lista completa de prompts (Módulo 1 e 2).
> Mantido aqui por já estar referenciado no código; não editar os dois
> documentos de forma divergente.

Este módulo já é publicado com ilustrações vetoriais (SVG) originais, leves,
acessíveis e sem dependência externa — não são placeholders vazios, mas uma
versão elegante e definitiva o suficiente para produção. Quando a Mística
Escola tiver arte finalizada (fotografia tratada, ilustração digital ou
geração assistida por IA com licença adequada), os arquivos abaixo podem ser
substituídos 1:1, mantendo o mesmo nome e caminho (não é necessário alterar
código nem banco de dados).

Diretriz visual geral: estética xamânica sofisticada; floresta; céu
estrelado; fogo cerimonial; tambores; natureza; paisagens da Sibéria; tons
verde-musgo (#536b37), dourado (#f0c56a), marrom, azul profundo (#0b1220) e
preto. Evitar: caricaturas, fantasias genéricas, cocares fora de contexto,
representação sexualizada, mistura aleatória de símbolos de povos
diferentes, qualquer rosto ou figura humana identificável como pertencente a
um povo específico sem consentimento/licença documentada.

## 1. `modulo-2-capa.svg` → `modulo-2-capa.webp` (1200×630)
Prompt: "Cinematic editorial illustration, horizontal cover art for an
online course module about the history of shamanism. A dark ancestral
forest silhouette at dusk, distant snow-dusted mountains, a small
ceremonial bonfire glowing at the center-bottom, a starry deep-blue sky
above. Palette: moss green, deep blue, warm gold, black. No people, no
readable symbols from any specific culture, no text. Sophisticated,
mystical but not fantastical, professional stock-illustration quality."

## 2. `aula-origem-termo-xama.svg` → `aula-origem-termo-xama.webp` (1200×630)
Prompt: "Wide illustration of a Siberian taiga landscape at golden-hour
dusk: dark spruce and fir silhouettes, light snow on the ground, a pale sun
low on the horizon, deep blue and gold sky. No people, no tents, no
campfires with figures. Evocative of Siberia and Central Asia without
depicting any specific ethnic group. Muted, painterly, professional."

## 3. `aula-tradicoes-regioes.svg` → `aula-tradicoes-regioes.webp` (1200×630)
Prompt: "Abstract minimalist illustration of a stylized globe or world
silhouette on a dark background, with a handful of soft glowing gold dots
scattered across different continents (no connecting lines between them,
no arrows implying a single point of origin). Palette: moss green, gold,
deep black. No flags, no country borders, no cultural symbols, no people."

## 4. `aula-xamanismo-moderno.svg` → `aula-xamanismo-moderno.webp` (1200×630)
Prompt: "Illustration blending an ancestral forest silhouette on the left
with a stylized contemporary city skyline on the right, connected by a
faint golden dotted path. Represents the transition from communal
tradition to urban neo-shamanism, without depicting people, rituals or
identifiable cultural symbols. Palette: moss green, gold, deep blue,
black. Editorial, sophisticated, not fantastical."

## 5. `mapa-tradicoes.svg` → versão final (mapa esquemático, 1200×640)
Manter o caráter **não geográfico/esquemático** (evitar mapa-múndi real
demarcando fronteiras políticas). Se optar por um mapa real:
Prompt: "Schematic, stylized world map (not a precise geopolitical map),
dark background, highlighting Siberia and Central Asia with a soft gold
glow and clear label, plus independent unconnected marker dots (no arrows)
over North America, South America, Arctic regions, parts of Africa and
parts of Oceania, each with a small neutral label. Educational
infographic style, moss-green and gold on near-black, legend included."
Legenda obrigatória a manter: mapa esquemático, não indica origem única.

## 6. `linha-tempo-xamanismo.svg` → versão final (linha do tempo, 1200×460)
Prompt: "Minimalist horizontal timeline infographic on a dark background,
gold nodes connected by a thin moss-green line, approximate date ranges
from 'before written records' through Siberian first written accounts
(17th–18th century), 19th century linguistic studies, early-to-mid 20th
century anthropology, 1960s–1980s Western popularization and
neo-shamanism, late 20th century commercial retreats, to present-day
debates on cultural respect. Clean editorial typography, gold and cream
text on near-black, no photos, no people."

## Observações de produção
- Ao gerar/produzir as versões finais, converter para **WebP** (ou AVIF)
  comprimido, mantendo `width`/`height` explícitos no HTML para não haver
  layout shift (os SVGs atuais já declaram 1200×630 / 1200×460 / 1200×640).
- Manter texto alternativo (`alt`) e legenda (`figcaption`) equivalentes
  aos já escritos no conteúdo de cada aula (`backend/lms_content_xamanismo.py`).
- Registrar crédito e licença da imagem final na própria legenda
  (`<span class="aula-imagem-credito">`), como já ocorre com o texto
  "Ilustração original — Mística Escola."
- Nenhuma imagem deve retratar pessoas, cerimônias específicas ou símbolos
  sagrados de um povo determinado sem pesquisa de licenciamento e, quando
  aplicável, consentimento documentado.
