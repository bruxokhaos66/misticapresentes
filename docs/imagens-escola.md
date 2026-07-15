# Auditoria visual e prompts de imagem — Escola Mística

Este documento é o registro central da auditoria visual da plataforma de
estudo (`escola.html` / `escola-curso.html`) e o repositório de prompts
cinematográficos para as imagens que ainda dependem de fotografia real ou
geração assistida por IA licenciada. Ele cobre o único curso com conteúdo
publicado no momento — **Introdução ao Xamanismo** (`backend/lms_content_xamanismo.py`)
— e serve de modelo para os próximos cursos da Escola.

Nenhuma imagem final foi substituída por banco de imagens genérico, IA
caricata ou símbolos de povos específicos. Onde não havia asset próprio
pronto para produção, o padrão adotado é: **ilustração vetorial (SVG)
original, leve e definitiva o suficiente para uso em produção agora**, com o
prompt fotográfico documentado aqui para uma substituição 1:1 futura (mesmo
nome de arquivo, sem tocar em código ou banco).

## Por que SVG e não fotografia gerada agora

A geração de imagem via IA (Higgsfield, disponível nesta sessão) exige plano
pago na conta conectada — uma decisão de assinatura que não nos cabe tomar
sozinhos. Seguindo a própria ordem de prioridade deste projeto (assets
existentes → imagens próprias → imagens licenciadas → SVG artístico próprio
**ou** prompt para geração futura), optamos por entregar agora ilustrações
vetoriais originais e deixar os prompts prontos abaixo. Assim que houver
orçamento de geração ou fotografia licenciada, cada arquivo pode ser trocado
1:1 pelo nome indicado, sem qualquer alteração de HTML/CSS/backend.

---

## 1. Auditoria — estado antes desta atualização

| Item | Local | Problema encontrado | Ação |
|---|---|---|---|
| Capa da Aula 1 e Aula 2 (Módulo 1) | `backend/lms_content_xamanismo.py`, `PLACEHOLDER_CAPA` | **Placeholder textual visível ao aluno**: "Placeholder de capa", "Imagem de capa em preparação", "Crédito: acervo próprio/licença a definir" — exatamente o tipo de texto técnico que nunca deveria aparecer para quem está estudando. | **Corrigido.** Substituído por duas capas SVG exclusivas (`modulo-1-aula-1-capa.svg`, `modulo-1-aula-2-capa.svg`), sem texto de sistema, com `alt` e legenda editorial. |
| Capa do Módulo 2 e das 3 aulas | `assets/escola/xamanismo/*.svg` | Ilustrações já existentes e coerentes com a identidade visual, mas em estilo de infográfico plano — abaixo do padrão "cinematográfico" desejado para as capas de aula (mapa e linha do tempo continuam corretos como infográfico). | **Corrigido** (atualização de modernização visual). As 3 capas de aula do Módulo 2 (`aula-origem-termo-xama.svg`, `aula-tradicoes-regioes.svg`, `aula-xamanismo-moderno.svg`) foram redesenhadas no mesmo padrão cinematográfico multi-camada do Módulo 1: gradientes em várias camadas, profundidade/névoa, sem texto embutido na imagem (o título já existe no `figcaption`). `modulo-2-capa.svg` não é referenciada em nenhuma aula hoje (fica reservada para uso futuro no catálogo) e não foi alterada nesta atualização. Prompts fotográficos de upgrade seguem preparados abaixo (itens 3.3 a 3.6) para substituição 1:1 quando houver plano pago de geração de imagem ou banco licenciado — Higgsfield está disponível na sessão mas exige plano pago, testado e confirmado nesta atualização. |
| `mapa-tradicoes.svg` / `linha-tempo-xamanismo.svg` | idem | Nenhum — são intencionalmente esquemáticos (o próprio conteúdo da aula pede um mapa "não geográfico" e uma linha do tempo, não uma fotografia). | Mantidos como estão; não devem virar fotografia. |
| Dimensões/layout shift | todas as `<img>` do curso | Nenhum problema: todas já declaram `width`/`height` e `loading="lazy"`. | Mantido; novo CSS reforça moldura sem alterar as dimensões. |
| Alt text / legenda / crédito | todas as `<img>` do curso | Nenhum problema estrutural; texto do `alt` já descritivo. | Mantido; padronizado via helper `_capa()` único para os dois módulos. |
| Excesso de texto sem apoio visual | Aulas 1–2 (Módulo 1) | As duas aulas mais longas do curso tinham **zero** imagem real (só o placeholder textual) apoiando ~1.400 palavras de leitura corrida. | Corrigido com a capa exclusiva de cada aula (item acima). Um componente de divisor elegante (`.aula-divisor`) foi adicionado ao CSS para uso futuro entre blocos longos de texto. |
| Imagens fora de contexto / repetidas / distorcidas / de baixo grau | — | Não encontradas. O curso não usa nenhuma imagem de banco genérico, nenhuma imagem repetida entre aulas, nenhuma foto de "índio genérico" ou cocar fora de contexto. | Nada a corrigir; manter esse padrão nos próximos cursos. |
| Catálogo de cursos (`escola.js`, capa do card) | `plataforma-curso-capa` | Sem `imagem` cadastrada, cai num emblema tipográfico (`☾`) — aceitável como fallback elegante, não é um placeholder textual. | Mantido; ver nota no item 4. |

## 2. O que foi entregue nesta atualização

- `assets/escola/xamanismo/modulo-1-aula-1-capa.svg` — capa exclusiva da Aula 1 ("O que é o Xamanismo?").
- `assets/escola/xamanismo/modulo-1-aula-2-capa.svg` — capa exclusiva da Aula 2 ("Por que o Xamanismo ainda existe?").
- `backend/lms_content_xamanismo.py` — placeholder textual removido; nova migração idempotente `instalar_capas_modulo1_xamanismo` (versão `xamanismo-modulo-1-capas-v1`) para levar a correção também aos bancos já instalados, via `UPDATE` (preserva id da aula e progresso do aluno).
- `escola-curso.css` — moldura cinematográfica para `.aula-imagem` (vinheta inferior sutil, sombra, borda), remoção do CSS morto de placeholder, novo componente `.aula-divisor` para separar seções de texto longas sem precisar de mais imagens.

## 2a. Atualização de modernização visual (Módulo 2)

Escopo: elevar as 3 capas de aula do Módulo 2 ao mesmo padrão cinematográfico do
Módulo 1, sem alterar arquitetura, API, banco ou nomes de arquivo (nenhuma
mudança em `backend/lms_content_xamanismo.py` foi necessária — os três
arquivos SVG foram substituídos no mesmo caminho).

- `assets/escola/xamanismo/aula-origem-termo-xama.svg` — reescrita como taiga
  siberiana em múltiplas camadas de silhueta com névoa e sol baixo dourado,
  sem título embutido na imagem (era um infográfico plano com texto SVG fixo).
- `assets/escola/xamanismo/aula-tradicoes-regioes.svg` — globo reescrito com
  halo atmosférico, brilho suave clipado à esfera (`clipPath`) e pontos com
  `feGaussianBlur` para bloom, sem texto embutido.
- `assets/escola/xamanismo/aula-xamanismo-moderno.svg` — composição dividida
  floresta/biblioteca com camadas de profundidade, estantes desfocadas
  (`feGaussianBlur`) sob luz quente e caminho dourado pontilhado com brilho
  sutil, sem texto embutido.
- Tentativa de geração fotográfica via Higgsfield (`soul_location`, prompts já
  documentados na seção 3) confirmada bloqueada: `Requires basic plan or
  higher` na conta conectada. Os prompts continuam válidos para substituição
  1:1 futura assim que houver plano pago ou banco licenciado.
- `modulo-2-capa.svg` não é usado em nenhuma aula atualmente e não foi
  alterado; `mapa-tradicoes.svg` e `linha-tempo-xamanismo.svg` permanecem
  esquemáticos, como já determinado nesta auditoria.

## 2b. Migração para artes fotográficas oficiais

Escopo: as ilustrações SVG (provisórias) das capas de Módulo 1, Módulo 2 e de
4 das 5 aulas cobertas neste documento foram substituídas pelas artes
fotográficas oficiais fornecidas pela Mística Escola, convertidas para WebP.
Diferente do que a seção 3 previa (prompts "sem pessoas, sem cocar, sem
cerimônia"), as fotos oficiais entregues retratam pessoas, cocares e cenas
cerimoniais — decisão de conteúdo da própria Mística Escola, que substitui a
diretriz "sem pessoas" documentada abaixo para estes arquivos específicos.

| Arquivo (novo, `.webp`) | Usado em | Substitui |
|---|---|---|
| `modulo-1-capa.webp` | Capa do Módulo 1 (`curso_modulos.imagem`, novo) | — (recurso novo) |
| `modulo-1-aula-1-capa.webp` | Aula 1 — "O que é o Xamanismo?" | `modulo-1-aula-1-capa.svg` |
| `modulo-1-aula-2-capa.webp` | Aula 2 — "Por que o Xamanismo ainda existe?" | `modulo-1-aula-2-capa.svg` |
| `modulo-2-capa.webp` | Capa do Módulo 2 (`curso_modulos.imagem`, novo) | `modulo-2-capa.svg` |
| `aula-tradicoes-regioes.webp` | Módulo 2 · Aula 2 | `aula-tradicoes-regioes.svg` |
| `aula-xamanismo-moderno.webp` | Módulo 2 · Aula 3 | `aula-xamanismo-moderno.svg` |

Não alterado: `aula-origem-termo-xama.svg` (Módulo 2 · Aula 1) — nenhuma arte
fotográfica oficial equivalente foi fornecida para esta aula; o SVG
cinematográfico continua em produção. `mapa-tradicoes.svg` e
`linha-tempo-xamanismo.svg` permanecem esquemáticos, como já determinado.

Migração de banco: `instalar_capas_v2_modulo1_xamanismo`
(`xamanismo-modulo-1-capas-v2`), `instalar_capas_modulo2_xamanismo`
(`xamanismo-modulo-2-capas-v1`) e `instalar_capas_modulos_xamanismo`
(`xamanismo-modulos-capas-v1`), todas em `backend/lms_content_xamanismo.py` —
idempotentes, via `UPDATE` (nunca `DELETE`+`INSERT`), preservando matrículas,
progresso e tentativas de quiz já registrados. A capa de módulo é um campo
novo (`curso_modulos.imagem`, adicionado via `ALTER TABLE` tolerante em
`garantir_tabelas_lms`) e não existia antes desta atualização.

## 3. Prompts cinematográficos para produção futura

Diretriz visual comum a todos os prompts abaixo — **manter em todos**:

> Paleta: verde-musgo (#516832/#536b37), dourado (#f2c96d/#f0c56a), marrom,
> preto, azul profundo (#0b1220). Sem pessoas, sem rostos, sem cerimônia
> específica retratada, sem cocar, sem mistura de símbolos de povos
> diferentes, sem texto embutido na imagem, sem estética de fantasia
> medieval, sem brilho/lens-flare exagerado, sem "índio genérico". Estilo
> fotografia editorial/documental, não ilustração de banco de imagens
> genérico. Proporção final 1200×630 (3:2 aproximado) para capas de aula,
> exceto onde indicado.

### 3.1 Módulo 1 · Aula 1 — "O que é o Xamanismo?"
Arquivo final: `modulo-1-aula-1-capa.webp` (substitui `modulo-1-aula-1-capa.svg`, mesmo caminho).

**Prompt:** "Cinematic wide landscape photograph of an ancestral forest at
dawn, viewed from a low hillside. Tall old-growth trees stand in layered
silhouette on both sides, framing a soft golden sunrise breaking through
thin morning mist between the trunks. A handful of the last stars still
fade into a deep blue pre-dawn sky above the treeline. Thin ground fog
drifts near the forest floor. Composition: rule-of-thirds horizon, foliage
silhouettes as foreground/midground framing, open sky as negative space for
future text overlay. Lighting: golden-hour backlight with soft volumetric
mist, high dynamic range. Lens: 24mm wide-angle equivalent, deep focus, no
distortion. Color grade: moss green shadows, warm gold highlights, deep
blue sky falling to black at the edges. Atmosphere: contemplative,
unhurried, mysterious but not ominous. Depth: at least three silhouette
layers receding into haze. Aspect ratio: 3:2. Photographic style: editorial
documentary nature photography, not painterly, not fantasy. Natural
elements: forest, mist, stars, dawn sky, no water, no fire. Cultural
restriction: no people, no ceremony, no ritual objects, no ethnic symbols
of any kind — this cover must not imply any specific people or ceremony,
only the idea of a first contemplative glimpse before definitions."

### 3.2 Módulo 1 · Aula 2 — "Por que o Xamanismo ainda existe?"
Arquivo final: `modulo-1-aula-2-capa.webp`.

**Prompt:** "Cinematic close-up/medium landscape photograph of an ancient,
thick-rooted tree at dusk, its exposed roots visible in the foreground soil,
with a small new sapling or young shoot growing beside it in soft golden
rim light. Deep blue-to-amber gradient sky behind, out of focus. Composition:
the old tree trunk occupies the left third, the young sprout the right
third, connected visually by warm side-light — a metaphor for continuity
and transmission between generations, without any human figure. Lighting:
warm low-angle dusk sun as rim light, cool ambient fill from the sky. Lens:
85mm-equivalent shallow depth of field, soft bokeh background. Color grade:
moss green foliage, warm gold rim light, dark brown bark, deep blue negative
space. Atmosphere: quiet permanence, living heritage, hopeful continuity.
Depth: sharp foreground root/sapling, soft blurred background. Aspect ratio:
3:2. Photographic style: editorial nature macro/landscape hybrid,
documentary quality. Natural elements: tree, roots, sapling, dusk sky, no
water, no fire. Cultural restriction: no people, no ceremony, no ritual
objects, no symbols tied to any specific people."

### 3.3 Módulo 2 · Capa do módulo
Arquivo final: `modulo-2-capa.webp` (substitui `modulo-2-capa.svg`).

**Prompt:** "Cinematic editorial photograph, horizontal cover for a course
module about the history of shamanism. A dark ancestral forest silhouette
at dusk, distant snow-dusted mountains on the horizon, a small ceremonial
bonfire glow at the center-bottom (glow only, no visible ritual or figures
around it), a starry deep-blue sky above fading to black at the top edge.
Composition: symmetrical, fire glow as central focal point, mountains and
treeline as horizontal bands. Lighting: warm firelight glow against cool
starlight, strong contrast. Lens: 35mm-equivalent, deep focus. Color grade:
moss green, deep blue, warm gold, black. Atmosphere: sophisticated, mystical,
grounded — not fantastical. Depth: foreground treeline, midground fire glow,
background mountains and stars. Aspect ratio: 3:2. Photographic style:
professional editorial nature/travel photography. Natural elements: forest,
mountains, fire glow, starry sky. Cultural restriction: no people, no
readable ceremonial symbols from any specific culture, no text."

### 3.4 Módulo 2 · Aula 1 — "A origem da palavra xamã"
Arquivo final: `aula-origem-termo-xama.webp`.

**Prompt:** "Cinematic wide photograph of a Siberian taiga landscape at
golden-hour dusk in winter: dark spruce and fir silhouettes, a thin layer of
snow on the ground, a pale low sun near the horizon, deep blue and gold sky
above. Composition: horizon at the lower third, tree silhouettes as
repeating vertical rhythm, open cold sky for negative space. Lighting: low
raking winter sun, cool ambient shadow, warm horizon glow. Lens:
35mm-equivalent, deep focus, slight haze for distance compression. Color
grade: muted blues and golds, desaturated greens, near-black silhouettes.
Atmosphere: historical, remote, austere but not bleak. Depth: near
tree line sharp, distant ridge softened by cold-air haze. Aspect ratio: 3:2.
Photographic style: muted painterly-documentary, professional travel/nature
photography. Natural elements: taiga, snow, conifers, winter dusk sky, no
water. Cultural restriction: no people, no tents, no campfires with figures,
evocative of Siberia and Central Asia without depicting any specific ethnic
group or ceremony."

### 3.5 Módulo 2 · Aula 2 — "Tradições semelhantes em diferentes regiões"
Arquivo final: mantém `mapa-tradicoes.svg` — **não fotografar**. Este é o
único item do curso onde a diretriz do briefing é seguida à risca: "mapa
artístico, elementos naturais, diferentes paisagens, sem representar povos
específicos". Se um dia for redesenhado, deve continuar esquemático/não
geopolítico (ver observação já registrada em
`assets/escola/xamanismo/PROMPTS_IMAGENS_MODULO2.md`), nunca virar fotografia
de pessoas ou cerimônias.

### 3.6 Módulo 2 · Aula 3 — "Como o xamanismo chegou ao mundo moderno"
Arquivo final: `aula-xamanismo-moderno.webp`.

**Prompt:** "Cinematic split composition photograph: on the left, a dark
ancestral forest silhouette at dusk; on the right, softly blurred rows of
old library bookshelves and a warm reading lamp, suggesting research and
contemporary study. A faint golden dotted light path (bokeh dots, not
graphic arrows) visually bridges the two halves at the horizon line.
Composition: forest occupies the left 55%, library the right 45%, connected
by a soft gold gradient at the seam. Lighting: cool blue dusk light on the
forest side, warm incandescent library light on the right, gradual color
temperature transition through the center. Lens: 50mm-equivalent, shallow
depth of field on the library side, deeper focus on the forest side. Color
grade: moss green and deep blue on the left, warm gold and brown on the
right. Atmosphere: tradition meeting scholarship, thoughtful, not
technological/sci-fi. Depth: forest silhouettes layered front-to-back;
library shelves soft-focused into bokeh. Aspect ratio: 3:2. Photographic
style: editorial double-exposure-style composite, documentary quality, no
surreal collage effects. Natural elements: forest, dusk sky; built elements:
bookshelves, reading lamp — no laptops, no phones, no futuristic tech.
Cultural restriction: no people, no ritual objects, no ethnic symbols,
represents the transition from communal oral tradition to contemporary
research without depicting any specific culture or ceremony."

### 3.7 Linha do tempo e mapa (infográficos)
`linha-tempo-xamanismo.svg` e `mapa-tradicoes.svg` devem continuar como
infográfico vetorial (dados, não fotografia). Prompts de estilo, caso um
redesenho seja necessário, seguem documentados em
`assets/escola/xamanismo/PROMPTS_IMAGENS_MODULO2.md` (mantido como anexo
técnico deste documento).

---

## 4. Próximos cursos — como aplicar este padrão

Quando um novo curso for publicado (fora do escopo desta atualização, que
não altera arquitetura, API ou banco):

1. Toda aula deve nascer com uma capa própria — nunca reaproveitar a mesma
   imagem entre aulas de temas diferentes.
2. Seguir a mesma ordem de prioridade de fontes: assets existentes →
   produção própria → licenciada → SVG artístico original **ou** prompt
   documentado aqui, nunca um placeholder textual visível ao aluno.
3. Usar sempre o helper `_capa()` (ou equivalente) para garantir
   `width`/`height`, `loading="lazy"`, `alt` descritivo, legenda e crédito
   consistentes — nunca uma tag `<img>` solta no conteúdo.
4. Catálogo de cursos (`plataforma-curso-capa` em `escola.js`): ao cadastrar
   `imagem` no curso, seguir a mesma paleta e diretriz de estilo; sem
   imagem cadastrada, o emblema tipográfico atual (`☾`) já é um fallback
   elegante e deve ser mantido — nunca substituí-lo por um placeholder de
   sistema.
5. Registrar todo novo prompt cinematográfico neste arquivo, na mesma
   estrutura (composição, iluminação, lente, cores, atmosfera, profundidade,
   proporção, estilo fotográfico, elementos naturais, restrições culturais).
