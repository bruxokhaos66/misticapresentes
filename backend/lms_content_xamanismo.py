"""Conteúdo editorial oficial do curso introdutório de Xamanismo.

A instalação é uma migração de conteúdo idempotente: grava no mesmo SQLite e
nas mesmas tabelas usadas pelo painel da Escola Mística, uma única vez por
versão. Depois disso o conteúdo pode ser editado normalmente pelo admin sem ser
sobreposto a cada inicialização.
"""

from __future__ import annotations

from datetime import datetime

SLUG = "xamanismo-introducao"
# v1 foi implantada em produção antes da correção de acesso_publico/requer_matricula
# (PR #316). Como a instalação só roda quando `VERSAO` ainda não consta em
# lms_content_versions, bancos que já tinham v1 registrada nunca receberiam o
# UPDATE que libera o curso — o endpoint público continuava 404 mesmo com o
# código corrigido. v2 força a reaplicação uma única vez nesses bancos; a
# instalação em si continua idempotente (UPSERT/UPDATE), preservando IDs,
# matrículas, progresso e tentativas de quiz já existentes.
VERSAO = "xamanismo-modulo-1-v2"
# Controle de versão independente do Módulo 2 (PR #318): sua própria migração
# idempotente, sem afetar nem ser afetada pela versão do Módulo 1 acima.
VERSAO_MODULO_2 = "xamanismo-modulo-2-v1"


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


PLACEHOLDER_CAPA = """
<figure class="aula-imagem-placeholder" role="img" aria-label="Placeholder de capa: floresta escura sob um céu estrelado, em tons de verde-musgo e dourado">
  <span aria-hidden="true">✦</span>
  <figcaption><strong>Imagem de capa em preparação.</strong> Sugestão: floresta e céu estrelado, sem representar povos ou cerimônias específicas. Crédito: acervo próprio/licença a definir.</figcaption>
</figure>
"""


AULA_1 = PLACEHOLDER_CAPA + """
<p class="aula-kicker">Aula 1 · Fundamentos e linguagem</p>
<h2>O que é o Xamanismo?</h2>
<p class="aula-subtitulo">Um primeiro mapa para compreender um termo amplo sem apagar a diversidade de quem mantém tradições vivas.</p>

<p>Há palavras que parecem abrir uma porta para a floresta, para o céu e para perguntas muito antigas. <em>Xamanismo</em> é uma delas. Ela costuma evocar cura, transe, cantos, tambores e contato com a natureza. Mas o primeiro gesto de uma jornada respeitosa é diminuir a pressa: essa palavra não nomeia uma religião única, nem um conjunto universal de rituais, e muito menos uma identidade que possa ser aplicada igualmente a todos os povos originários.</p>

<h3>Uma palavra nascida em um contexto específico</h3>
<p><strong>Conhecimento histórico:</strong> o termo “xamã” chegou ao vocabulário europeu por meio de relatos sobre povos da Sibéria. Sua origem é geralmente associada a <em>šamān</em>, palavra de línguas tungúsicas, em especial o evenki. Pesquisadores passaram a usar “xamanismo” para comparar certas funções religiosas e práticas encontradas na Sibéria e na Ásia Central. Com o tempo, o rótulo foi estendido a contextos muito diferentes.</p>
<p>Essa expansão ajuda a fazer comparações, mas também cria um risco: imaginar que sociedades distantes compartilham uma única tradição. Elas não compartilham. Povos siberianos, amazônicos, andinos, norte-americanos, africanos, oceânicos e de tantas outras regiões têm histórias, línguas, territórios, autoridades, cosmologias e nomes próprios para seus especialistas e práticas. Alguns reconhecem afinidade com a palavra “xamanismo”; outros não a utilizam ou rejeitam sua aplicação.</p>

<aside class="aula-box aula-box-sabia"><h3>Você sabia?</h3><p>“Xamã” não é um título universal. Em cada povo podem existir nomes e responsabilidades muito diferentes para pessoas que cuidam, aconselham, cantam, interpretam sonhos, conduzem cerimônias ou guardam conhecimentos. Traduzir todos esses papéis como “xamã” pode esconder diferenças importantes.</p></aside>

<h3>Semelhanças não significam identidade</h3>
<p><strong>Comparação antropológica:</strong> em diversas sociedades existem pessoas reconhecidas por mediar relações entre a comunidade, a natureza, os ancestrais ou o mundo espiritual; há também práticas de canto, dança, jejum, narrativa, oração, sonho e uso ritual de objetos. Essas semelhanças permitem perguntas comparativas. Elas não provam uma origem única nem tornam as práticas intercambiáveis.</p>
<p>Em linguagem introdutória, podemos tratar “xamanismo” como um termo amplo usado por pesquisadores e praticantes contemporâneos para falar de tradições distintas nas quais cura, proteção, sentido, comunidade e relações com o ambiente ocupam lugar relevante. A definição é uma ferramenta de estudo, não uma gaveta capaz de conter toda a diversidade humana.</p>

<h3>O que as pessoas buscam?</h3>
<p>Ao longo do tempo, seres humanos procuraram respostas para a doença, o luto, o medo, os conflitos, a incerteza e o desejo de pertencimento. Em muitas culturas, essas respostas não separam nitidamente corpo, mente, comunidade, território e espiritualidade. Uma cerimônia pode ter valor religioso e, ao mesmo tempo, organizar vínculos sociais, transmitir memória e oferecer cuidado.</p>
<p><strong>Crença espiritual:</strong> uma comunidade pode compreender que sonhos, espíritos, ancestrais ou forças da natureza participam do processo de cura. O curso apresenta essa crença como parte de uma visão de mundo, sem declará-la fato científico. <strong>Evidência científica:</strong> a ciência pode observar comportamentos, relatos, relações sociais e alterações fisiológicas, mas seus métodos não confirmam automaticamente a existência ou a interpretação espiritual desses seres e forças.</p>

<aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência</h3><p>Antropologia, história, psicologia e outras áreas podem estudar rituais, estados de atenção, memória, expectativa, apoio comunitário e respostas do corpo. Um efeito percebido pode envolver contexto, vínculo, significado e mecanismos fisiológicos. Isso não transforma toda explicação espiritual em comprovação científica, nem autoriza substituir diagnóstico ou tratamento profissional.</p></aside>

<h3>Tradição espiritual, religião e interpretações modernas</h3>
<p>Uma <strong>tradição espiritual</strong> pode estar integrada à vida de um povo, ao território, à língua, aos parentescos e às formas de aprender. Uma <strong>religião organizada</strong> costuma ter instituições, doutrinas ou autoridades mais formalizadas, embora as fronteiras variem. Já o <strong>xamanismo contemporâneo</strong> ou “neoxamanismo” reúne adaptações recentes, muitas vezes urbanas e combinadas com psicologia, terapias, esoterismo ou desenvolvimento pessoal.</p>
<p>Essas interpretações modernas existem e merecem ser estudadas como fenômeno contemporâneo. Porém, não devem ser apresentadas como reprodução automática de uma tradição indígena. Uma prática criada em um retiro urbano possui outro contexto, outra autoridade e outra história.</p>

<aside class="aula-box aula-box-respeito"><h3>Respeito às Tradições</h3><p>Não existe “a cultura indígena”. Existem povos indígenas e originários diversos, contemporâneos e atuantes, cada qual com cultura, espiritualidade, língua, organização e visão de mundo próprias. Respeitar começa por aprender o nome do povo, ouvir suas próprias vozes, reconhecer seus direitos e não copiar conhecimentos restritos, símbolos sagrados ou cerimônias sem consentimento.</p></aside>

<h3>Um mapa de cinco lentes</h3>
<ul>
  <li><strong>História:</strong> o que documentos e pesquisas permitem reconstruir.</li>
  <li><strong>Tradição cultural:</strong> conhecimentos e práticas reconhecidos e transmitidos por uma comunidade.</li>
  <li><strong>Crença espiritual:</strong> interpretações do sagrado aceitas em determinado contexto.</li>
  <li><strong>Interpretação contemporânea:</strong> releituras urbanas ou recentes, com autoria e contexto próprios.</li>
  <li><strong>Evidência científica:</strong> resultados produzidos por métodos verificáveis, sempre com limites.</li>
</ul>

<aside class="aula-box aula-box-refletir"><h3>Para refletir</h3><p>Quando você escuta a palavra “xamanismo”, quais imagens aparecem? Elas vieram de uma comunidade específica, de pesquisa histórica, do cinema, das redes sociais ou de uma experiência pessoal? Identificar a origem de nossas imagens é o começo de um olhar mais consciente.</p></aside>

<h3>Glossário da aula</h3>
<dl class="aula-glossario"><dt>Cosmologia</dt><dd>Modo como um povo compreende o universo, os seres e suas relações.</dd><dt>Evenki</dt><dd>Língua e povo tungúsico associados à origem histórica do termo <em>šamān</em>.</dd><dt>Povos originários</dt><dd>Povos com continuidade histórica e vínculos próprios com seus territórios, culturas e formas de organização.</dd><dt>Neoxamanismo</dt><dd>Conjunto diverso de releituras modernas, muitas vezes urbanas, inspiradas em ideias associadas ao xamanismo.</dd></dl>

<h3>Resumo</h3>
<p>“Xamanismo” é um termo amplo, historicamente ligado à Sibéria, que passou a ser usado em comparações entre práticas distintas. Ele pode orientar uma introdução, desde que não transforme povos diferentes em uma tradição única. História, cultura, crença, releitura contemporânea e ciência são lentes complementares — não sinônimos.</p>
<p class="aula-aviso"><strong>Nota de cuidado:</strong> este curso é educativo. Não substitui orientação médica, psicológica, jurídica ou religiosa e não ensina consumo, preparo ou administração de substâncias.</p>
<p class="aula-cta">Continue para a Aula 2 e descubra por que essas tradições permanecem vivas. A história do termo e seus debates será aprofundada na formação completa sobre <strong>História do Xamanismo</strong>.</p>
"""


AULA_2 = PLACEHOLDER_CAPA + """
<p class="aula-kicker">Aula 2 · Continuidade, encontros e responsabilidades</p>
<h2>Por que o Xamanismo ainda existe?</h2>
<p class="aula-subtitulo">Tradições permanecem porque pessoas e comunidades as vivem, recriam e transmitem no presente.</p>

<p>Uma tradição não atravessa séculos como uma peça imóvel guardada em uma vitrine. Ela atravessa o tempo porque alguém ensina, alguém aprende, alguém recorda e alguém decide continuar. Quando falamos de práticas chamadas de xamânicas, falamos também de famílias, mestres, aprendizes, comunidades e povos que enfrentaram mudanças, proibições, deslocamentos e pressões externas sem deixar de produzir vida cultural.</p>

<h3>Herança viva, não relíquia do passado</h3>
<p><strong>Tradição cultural:</strong> conhecimentos podem ser transmitidos por histórias, cantos, observação, convivência, participação em cerimônias, cuidado com o território e aprendizado com pessoas mais experientes. Essa transmissão não é simples cópia. Cada geração responde ao seu tempo, e a própria comunidade decide o que pode mudar, o que deve ser protegido e quem está autorizado a ensinar.</p>
<p>Povos originários existem no presente. Vivem em aldeias e cidades, usam tecnologias, frequentam universidades, produzem arte, ciência, política e comunicação, ao mesmo tempo que mantêm ou retomam línguas, conhecimentos e vínculos territoriais. Falar apenas em “ancestrais do passado” apaga essa presença contemporânea.</p>

<aside class="aula-box aula-box-sabia"><h3>Você sabia?</h3><p>A UNESCO descreve o patrimônio cultural imaterial como vivo e continuamente recriado por seus portadores. A continuidade depende da transmissão entre pessoas e gerações — e do direito das próprias comunidades de reconhecer, cuidar e definir seu patrimônio.</p></aside>

<h3>Espiritualidade, comunidade e natureza</h3>
<p>Em muitas tradições, espiritualidade não é uma atividade isolada para momentos especiais. Ela pode orientar relações de parentesco, alimentação, cuidado, território, memória e responsabilidade coletiva. O ambiente não aparece apenas como cenário ou “recurso”, mas como rede de relações da qual a comunidade participa.</p>
<p>Isso não significa que todos os povos tenham a mesma “religião da natureza”. A frase seria outra generalização. Significa apenas que, em contextos específicos, conhecimentos ecológicos, práticas sociais e interpretações espirituais podem estar profundamente entrelaçados.</p>

<h3>O interesse urbano contemporâneo</h3>
<p>Nas cidades, cresce a procura por retiros, espiritualidade, autoconhecimento e experiências de reconexão. Entre os motivos possíveis estão solidão, crise ambiental, sofrimento emocional, busca de pertencimento e insatisfação com respostas estritamente materiais. Psicologia, estudos da religião e antropologia ajudam a compreender esse movimento sem reduzir toda experiência a uma única causa.</p>
<p><strong>Interpretação contemporânea:</strong> práticas urbanas podem criar comunidades e significados genuínos para seus participantes. Ainda assim, usar palavras, símbolos ou cerimônias de outro povo não concede automaticamente legitimidade tradicional. É preciso dizer de onde veio a prática, quem autorizou seu compartilhamento, para onde vão os recursos e quais limites foram estabelecidos pelos detentores do conhecimento.</p>

<aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência</h3><p>A ciência pode investigar efeitos psicológicos, sociais, culturais e fisiológicos associados a rituais: redução ou aumento de estresse, mudanças de atenção, expectativa, pertencimento, apoio social e respostas corporais. Resultados dependem do desenho do estudo, da amostra e do contexto. Pesquisas ainda limitadas não autorizam promessas de cura nem confirmam automaticamente interpretações espirituais. Práticas espirituais não são substitutas automáticas de cuidados médicos ou psicológicos.</p></aside>

<h3>Quando o encontro vira apropriação</h3>
<p>Intercâmbio cultural pode ocorrer com respeito, consentimento e benefício mútuo. A <strong>apropriação cultural</strong> aparece quando elementos de uma comunidade historicamente marginalizada são retirados de seu contexto, transformados em produto ou autoridade pessoal, enquanto as pessoas que os mantêm são silenciadas, estereotipadas ou não recebem reconhecimento e benefício.</p>
<p>Sinais de alerta incluem promessas extraordinárias, títulos autoproclamados após formações muito curtas, venda de cerimônias secretas, imitação de vestimentas sagradas, mistura de povos como se fossem iguais e uso de imagens caricatas. Também é prudente desconfiar de quem desencoraja tratamento de saúde, exige obediência absoluta ou encobre riscos.</p>

<aside class="aula-box aula-box-respeito"><h3>Respeito às Tradições</h3><p>Priorize materiais produzidos por autores e organizações indígenas, remunere o trabalho, respeite conhecimentos que não são públicos e verifique como a comunidade deseja ser nomeada. Apoiar direitos territoriais, linguísticos e culturais costuma ser mais responsável do que colecionar símbolos fora de contexto.</p></aside>

<h3>Ciência, antropologia, psicologia e espiritualidade em diálogo</h3>
<p>Esses campos fazem perguntas diferentes. A história procura processos e documentos; a antropologia observa sentidos e relações em contexto; a psicologia investiga experiências e comportamentos; as ciências biomédicas medem processos do organismo; a espiritualidade oferece interpretações existenciais dentro de tradições e trajetórias pessoais.</p>
<p>Um diálogo responsável não obriga uma área a fingir que é outra. A ciência não precisa validar toda crença para estudar seus efeitos, e uma tradição não precisa ser reduzida a uma variável de laboratório para ter valor cultural. O ponto de encontro mais fértil costuma ser a clareza sobre métodos, limites, linguagem e ética.</p>

<aside class="aula-box aula-box-refletir"><h3>Para refletir</h3><p>Antes de participar ou comprar uma experiência apresentada como “xamânica”, que perguntas você faria sobre origem, consentimento, segurança, formação de quem conduz e relação com as comunidades citadas?</p></aside>

<h3>Glossário da aula</h3>
<dl class="aula-glossario"><dt>Patrimônio cultural imaterial</dt><dd>Práticas, conhecimentos e expressões vivas reconhecidos por suas comunidades.</dd><dt>Transmissão intergeracional</dt><dd>Passagem e recriação de conhecimentos entre gerações.</dd><dt>Apropriação cultural</dt><dd>Uso descontextualizado ou exploratório de elementos culturais, sobretudo em relações desiguais de poder.</dd><dt>Estudos da consciência</dt><dd>Campo interdisciplinar que pesquisa experiências conscientes por diferentes métodos.</dd></dl>

<h3>Resumo</h3>
<p>As tradições continuam porque comunidades vivas as transmitem, protegem e recriam. O interesse urbano amplia encontros, mas também traz riscos de exploração e simplificação. Ciência e espiritualidade podem dialogar quando suas perguntas e limites permanecem claros. Respeito exige escuta, contexto, consentimento e responsabilidade.</p>
<p class="aula-aviso"><strong>Nota de cuidado:</strong> este módulo não oferece instruções sobre substâncias ou cerimônias e não substitui orientação médica, psicológica, jurídica ou religiosa.</p>
<p class="aula-cta"><strong>Nos próximos módulos, você conhecerá as origens históricas do xamanismo, sua presença em diferentes regiões do mundo e a diversidade das tradições dos povos originários.</strong> Em um curso específico, estudaremos com mais profundidade as tradições dos povos originários; outros percursos abordarão, com contexto e segurança, espiritualidade, Rapé, Ayahuasca e medicinas da floresta.</p>
"""


def _capa(arquivo: str, alt: str, legenda: str) -> str:
    return (
        f'<figure class="aula-imagem">'
        f'<img src="assets/escola/xamanismo/{arquivo}" width="1200" height="630" loading="lazy" alt="{alt}">'
        f'<figcaption>{legenda} <span class="aula-imagem-credito">Ilustração original — Mística Escola.</span></figcaption>'
        f"</figure>"
    )


CAPA_M2_AULA_1 = _capa(
    "aula-origem-termo-xama.svg",
    "Ilustração de uma taiga siberiana nevada ao entardecer, com abetos escuros sob um céu dourado e azul profundo",
    "A taiga siberiana, cenário histórico associado à origem da palavra “xamã”.",
)
CAPA_M2_AULA_2 = _capa(
    "aula-tradicoes-regioes.svg",
    "Ilustração de um globo estilizado com pontos luminosos em diferentes regiões do mundo",
    "Práticas rituais comparáveis existem em regiões distintas — sem uma origem comum.",
)
CAPA_M2_AULA_3 = _capa(
    "aula-xamanismo-moderno.svg",
    "Ilustração combinando a silhueta de uma floresta ancestral com contornos geométricos de uma cidade contemporânea",
    "Da transmissão comunitária às releituras urbanas do século XX e XXI.",
)


AULA_M2_1 = CAPA_M2_AULA_1 + """
<p class="aula-kicker">Módulo 2 · Aula 1 · Origem da palavra</p>
<h2>A origem da palavra “xamã”</h2>
<p class="aula-subtitulo">De onde vem esse nome tão repetido — e por que ele nasceu em um lugar muito específico do mundo.</p>

<p>Em uma região marcada por florestas, neve, deslocamentos e longos invernos, diferentes comunidades desenvolveram formas próprias de compreender a vida, a doença, os sonhos, os animais e os ancestrais. Foi observando parte dessas comunidades que viajantes, comerciantes e, mais tarde, pesquisadores europeus registraram pela primeira vez a palavra que hoje conhecemos como “xamã”. Esse é o ponto de partida deste módulo: não uma lenda única, mas um termo com um lugar, uma língua e uma história específicos.</p>

<h3>Uma palavra tungúsica</h3>
<p><strong>Conhecimento histórico:</strong> a maior parte dos linguistas e historiadores associa a palavra “xamã” a <em>šamān</em>, termo de línguas tungúsicas — família linguística falada por diversos povos do leste e do centro da Sibéria. O evenki, um desses povos e dessa língua, costuma ser citado como referência central nessa origem. A partir dos séculos XVII e XVIII, relatos de viajantes, missionários e diplomatas europeus que atravessaram a Sibéria começaram a mencionar essa palavra para descrever determinadas figuras espirituais que encontravam.</p>
<p>É importante notar o que essa origem documentada permite afirmar e o que não permite. Ela mostra de onde veio a <em>palavra</em> que passou a ser usada em português, inglês, francês e outras línguas ocidentais. Ela não mostra que todas as práticas espirituais do mundo derivam de um único povo siberiano — isso seria confundir a história de um termo com a história de todas as tradições que, mais tarde, passaram a ser descritas com ele.</p>

<aside class="aula-box aula-box-historia"><h3>Olhar da História</h3><p>Os primeiros registros escritos sobre “xamãs” siberianos vêm de relatos de viajantes russos e europeus entre os séculos XVII e XVIII, num contexto de expansão comercial e territorial pela Sibéria. Esses relatos foram escritos por pessoas de fora daquelas comunidades, o que significa que carregam também os olhares, as expectativas e, por vezes, os preconceitos de quem os escreveu — um cuidado que a história como disciplina leva em conta ao interpretar essas fontes.</p></aside>

<h3>Quem eram — e são — os povos da Sibéria</h3>
<p>A Sibéria não é habitada por um único povo, mas por uma diversidade de grupos com línguas, histórias e organizações sociais próprias: entre eles estão os evenki, os iacutos (sakha), os nenets, os buriates, os tuvanos e muitos outros. Cada um desses povos tem — e teve historicamente — nomes, funções e responsabilidades próprios para as pessoas que cuidavam da vida espiritual, da cura, do aconselhamento e da mediação com o mundo natural e ancestral da comunidade.</p>
<p>Em algumas dessas tradições, a pessoa reconhecida nesse papel podia atuar em cerimônias de cura, na interpretação de sonhos, no aconselhamento em momentos de crise, na proteção da comunidade e na condução de rituais que reforçavam os laços entre as pessoas, os antepassados e o território. Essas funções não eram idênticas de um povo para outro, e nem todos os povos da própria Sibéria usavam a mesma palavra para nomeá-las.</p>

<aside class="aula-box aula-box-sabia"><h3>Você sabia?</h3><p>Antes de “xamanismo” virar um termo acadêmico amplo, cada povo siberiano já tinha sua própria palavra e sua própria compreensão sobre quem exercia esse papel espiritual — e sobre o que essa pessoa podia ou não fazer. A palavra “xamã”, tal como é usada hoje em português, é uma tradução aproximada, cunhada por observadores externos.</p></aside>

<h3>Do uso tradicional ao uso moderno</h3>
<p>Quando pesquisadores ocidentais adotaram a palavra “xamã”, eles a fizeram viajar para muito além do contexto em que nasceu. Aos poucos, o termo passou a ser aplicado — por conveniência acadêmica e, depois, por popularização — a especialistas espirituais de povos completamente diferentes, em continentes distantes da Sibéria. Essa extensão é útil para fins de comparação, mas tem um custo: pode dar a impressão de que “xamã” é um título universal, válido e reconhecido por qualquer povo espiritual do mundo. Não é.</p>
<p><strong>Interpretação contemporânea:</strong> hoje, fora da Sibéria, a palavra também é usada de maneira ainda mais solta — inclusive por pessoas que se autodenominam “xamãs” sem vínculo direto com nenhuma tradição comunitária específica. Reconhecer essa diferença de uso, entre o termo em seu contexto histórico e o termo popularizado, é um dos primeiros passos para estudar o assunto com honestidade.</p>

<aside class="aula-box aula-box-respeito"><h3>Respeito às Tradições</h3><p>Nomes, funções e papéis mudam de cultura para cultura. Chamar automaticamente de “xamã” qualquer especialista espiritual de qualquer povo do mundo apaga o nome que aquele povo já usa e a especificidade de sua função. Ao estudar uma tradição específica, vale a pena perguntar: como esse povo chama essa pessoa em sua própria língua? Esse cuidado será retomado com mais profundidade em cursos futuros dedicados a povos específicos.</p></aside>

<h3>Cura, aconselhamento, proteção e comunidade</h3>
<p>Ainda que não seja possível generalizar entre todos os povos, em algumas comunidades sibero-tungúsicas o especialista espiritual tradicionalmente citado nos relatos históricos podia estar associado a funções como: cuidar de pessoas doentes por meio de práticas rituais; aconselhar a comunidade em decisões importantes; realizar cerimônias de proteção antes de caçadas ou deslocamentos; e manter viva a memória sobre os ancestrais e os espíritos associados ao território. Essas funções relacionavam a pessoa profundamente à vida coletiva — o papel raramente era só individual ou apenas religioso no sentido estrito.</p>

<h3>Palavras importantes</h3>
<dl class="aula-glossario">
  <dt>Tungúsico</dt><dd>Família de línguas faladas por povos do leste e centro da Sibéria, entre eles o evenki — de onde vem a origem documentada da palavra “xamã”.</dd>
  <dt>Evenki</dt><dd>Povo e língua siberianos frequentemente citados como referência central na origem histórica do termo <em>šamān</em>.</dd>
  <dt>Etimologia</dt><dd>O estudo da origem e da formação histórica de uma palavra.</dd>
  <dt>Especialista espiritual</dt><dd>Termo mais neutro, usado neste curso para se referir a pessoas com funções de cura, aconselhamento ou mediação espiritual em diferentes culturas, sem presumir que todas compartilham o mesmo nome ou papel.</dd>
</dl>

<aside class="aula-box aula-box-refletir"><h3>Para refletir</h3><p>Antes desta aula, de onde vinha a sua ideia sobre o que é um “xamã”? Ela tinha relação com algum povo específico, com filmes, redes sociais ou experiências pessoais? Perceber a origem das nossas imagens mentais é o primeiro passo para estudar o tema com mais cuidado.</p></aside>

<h3>Resumo</h3>
<p>A palavra “xamã” tem uma origem documentada nas línguas tungúsicas da Sibéria, especialmente associada ao povo evenki. Ela nomeava, em contextos específicos, pessoas com funções de cura, aconselhamento, proteção e mediação espiritual. Ao longo do tempo, pesquisadores estenderam esse termo para descrever papéis semelhantes em outros povos do mundo — uma extensão útil para comparação, mas que não torna “xamã” um título universal.</p>
<p class="aula-aviso"><strong>Nota de cuidado:</strong> este conteúdo é educativo e apresenta interpretações históricas e antropológicas. Não substitui orientação médica, psicológica, jurídica ou religiosa e não descreve nem incentiva o uso de substâncias.</p>
<p class="aula-cta">Na próxima aula, você vai conhecer tradições rituais semelhantes em outras partes do mundo — e entender por que parecidas não significa iguais. Este panorama introdutório será aprofundado, com muito mais contexto histórico e cultural, em cursos futuros da formação em <strong>História do Xamanismo</strong>.</p>
"""


AULA_M2_2 = CAPA_M2_AULA_2 + """
<p class="aula-kicker">Módulo 2 · Aula 2 · Panorama comparado</p>
<h2>Tradições semelhantes em diferentes regiões</h2>
<p class="aula-subtitulo">Cantos, tambores, silêncio, sonhos e plantas aparecem em muitos povos — mas cada tradição tem seu próprio nome, sua própria história e seus próprios guardiões.</p>

<p>Se você viajasse pelo mundo perguntando quem cuida da saúde espiritual, dos sonhos, dos ancestrais e da relação com a natureza em diferentes comunidades, encontraria respostas muito diferentes — e, ao mesmo tempo, alguns elementos que se repetem: cantos, tambores, danças, jejuns, silêncio ritual, plantas, símbolos e narrativas. Essa aula percorre esse panorama com uma regra simples: descrever semelhanças sem apagar diferenças.</p>

<h3>Um padrão encontrado, não uma origem única</h3>
<p><strong>Interpretação antropológica:</strong> pesquisadores identificaram, em sociedades muito distantes entre si, a presença recorrente de especialistas espirituais, curadores, líderes rituais e guardiões de conhecimentos — pessoas que ocupam, em cada cultura, um papel de mediação entre a comunidade e aquilo que ela considera sagrado, ancestral ou natural. Essa recorrência intrigou antropólogos ao longo do século XX e ajudou a consolidar “xamanismo” como uma categoria comparativa de estudo.</p>
<p>Mas é preciso ter cautela com a conclusão que se tira dessa recorrência. Práticas parecidas podem ter surgido de formas totalmente independentes, como respostas humanas semelhantes a desafios semelhantes — a doença, a morte, o desconhecido, a necessidade de coesão social — sem que isso implique contato histórico entre os povos ou uma origem espiritual comum. Não é correto afirmar que todas essas tradições vieram de uma única fonte ancestral, seja ela siberiana ou de qualquer outro lugar.</p>

<aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência e da Antropologia</h3><p>A antropologia compara práticas culturais para entender tanto padrões humanos recorrentes quanto particularidades locais. Quando pesquisadores encontram elementos parecidos — como o uso ritual de tambores ou de estados alterados de atenção — eles investigam se há relação histórica direta entre os povos ou se são desenvolvimentos paralelos e independentes. As duas explicações são cientificamente possíveis, e a resposta muda de caso para caso; a existência de semelhança, por si só, não decide a questão.</p></aside>

<h3>Um panorama por regiões</h3>
<p>A seguir, um quadro comparativo simples, pensado apenas como um primeiro mapa de estudo — não como uma lista de tradições equivalentes entre si. Cada linha representa um contexto cultural amplo e diverso internamente, com múltiplos povos, línguas e cosmologias próprias.</p>

<div class="aula-tabela-wrap">
<table class="aula-tabela">
  <caption>Quadro comparativo introdutório — elementos rituais por região (visão panorâmica, não exaustiva)</caption>
  <thead>
    <tr><th scope="col">Região</th><th scope="col">Contexto cultural</th><th scope="col">Exemplos de elementos rituais citados por pesquisadores</th><th scope="col">Cuidado contra generalização</th></tr>
  </thead>
  <tbody>
    <tr><th scope="row">Sibéria e Ásia Central</th><td>Diversos povos tungúsicos, turcomongóis e siberianos, cada um com língua e cosmologia próprias.</td><td>Tambor cerimonial, canto, jornadas em estado ritual, mediação com espíritos da natureza.</td><td>Não são um bloco único: evenki, buriates, sakha e outros têm tradições distintas entre si.</td></tr>
    <tr><th scope="row">América do Norte</th><td>Centenas de povos indígenas com línguas, territórios e governos próprios.</td><td>Cerimônias sazonais, jejum, cantos, sonhos, uso ritual de ervas específicas de cada povo.</td><td>Não existe “a” espiritualidade nativo-americana; cada nação tem sua própria tradição.</td></tr>
    <tr><th scope="row">América do Sul</th><td>Povos amazônicos, andinos e de outras regiões, com línguas e cosmologias muito diversas.</td><td>Cantos ritualísticos, uso cerimonial de plantas específicas de cada povo, curandeirismo comunitário.</td><td>Amazônia e Andes têm tradições distintas; um curso futuro tratará cada povo com profundidade.</td></tr>
    <tr><th scope="row">Regiões árticas (além da Sibéria)</th><td>Povos como os inuit, adaptados a ambientes gelados e de subsistência da caça.</td><td>Cantos, tambores, narrativas sobre espíritos dos animais e do gelo.</td><td>Inuit e povos siberianos não são o mesmo grupo, ainda que ambos vivam em regiões árticas.</td></tr>
    <tr><th scope="row">Partes da África</th><td>Diversidade imensa de povos, línguas e religiões tradicionais, cada uma com sistema próprio.</td><td>Cultos de possessão, adivinhação, curandeirismo, cerimônias comunitárias — descritos por termos locais próprios, nem sempre traduzidos como “xamanismo”.</td><td>O termo “xamanismo” é usado com muita cautela por africanistas; cada tradição tem nome e sistema próprios.</td></tr>
    <tr><th scope="row">Partes da Oceania</th><td>Povos aborígenes australianos e povos das ilhas do Pacífico, com cosmologias próprias.</td><td>Narrativas ancestrais, cerimônias ligadas ao território, guardiões de conhecimento tradicional.</td><td>“Tempo do Sonho” australiano, por exemplo, é um conceito próprio — não deve ser traduzido como “xamanismo”.</td></tr>
  </tbody>
</table>
</div>

<figure class="aula-imagem aula-imagem-mapa">
  <img src="assets/escola/xamanismo/mapa-tradicoes.svg" width="1200" height="640" loading="lazy" alt="Mapa-múndi esquemático destacando a Sibéria e a Ásia Central, com pontos independentes marcando outras regiões com tradições rituais comparáveis, sem setas de conexão entre eles">
  <figcaption>Mapa esquemático (não geográfico) — cada ponto representa uma região com tradições próprias, sem indicar uma origem comum. <span class="aula-imagem-credito">Ilustração original — Mística Escola.</span></figcaption>
</figure>

<h3>O que realmente se repete</h3>
<p>Alguns elementos aparecem, com frequência, em diferentes tradições estudadas por antropólogos: o uso de som ritual (canto, tambor, chocalho); estados de atenção alterados, obtidos por dança, jejum, privação de sono ou outras técnicas; a importância dos sonhos como fonte de conhecimento; e a existência de uma pessoa (ou grupo de pessoas) reconhecida pela comunidade como intermediária nesse tipo de experiência. Isso é uma observação sobre recorrência, não uma prova de origem comum.</p>

<aside class="aula-box aula-box-sabia"><h3>Você sabia?</h3><p>Alguns antropólogos preferem usar o termo no plural — “xamanismos” — ou evitam usá-lo totalmente fora do contexto sibero-tungúsico, justamente para não sugerir uma tradição única e universal onde, na verdade, existe uma grande diversidade de sistemas culturais independentes.</p></aside>

<aside class="aula-box aula-box-respeito"><h3>Respeito às Tradições</h3><p>Cada povo mencionado neste panorama tem nomes, histórias, cosmologias e responsabilidades próprias — muitos deles têm, inclusive, palavras específicas em sua própria língua para os papéis descritos aqui, diferentes de “xamã”. Este quadro é apenas um ponto de partida para o estudo; conhecer um povo de verdade exige ouvir suas próprias vozes e fontes, algo que os próximos módulos e cursos desta formação vão aprofundar.</p></aside>

<h3>Palavras importantes</h3>
<dl class="aula-glossario">
  <dt>Etnografia</dt><dd>Método de pesquisa baseado na observação direta e na convivência com uma comunidade, usado por antropólogos para descrever suas práticas culturais.</dd>
  <dt>Desenvolvimento independente</dt><dd>Quando práticas semelhantes surgem em povos sem contato histórico entre si, como resposta a desafios humanos parecidos.</dd>
  <dt>Cosmologia</dt><dd>O modo como um povo compreende a origem, a estrutura e o funcionamento do universo e dos seres que nele habitam.</dd>
  <dt>Curandeirismo</dt><dd>Termo amplo usado para práticas de cura tradicionais, que variam muito de comunidade para comunidade.</dd>
</dl>

<aside class="aula-box aula-box-refletir"><h3>Para refletir</h3><p>Olhando o quadro comparativo, qual região desperta mais a sua curiosidade? O que você já sabia sobre ela antes desta aula — e o que dessa informação vinha de fontes confiáveis?</p></aside>

<h3>Resumo</h3>
<p>Elementos rituais parecidos — cantos, tambores, jejuns, sonhos, plantas, especialistas espirituais — aparecem em povos de regiões muito distintas do planeta. Essa recorrência é um achado importante da antropologia comparada, mas não prova uma origem única. Cada povo mantém seus próprios nomes, histórias e cosmologias, e generalizações apagam essa diversidade.</p>
<p class="aula-aviso"><strong>Nota de cuidado:</strong> este panorama é introdutório e não descreve rituais específicos de nenhum povo com profundidade suficiente para reprodução. Não incentiva o uso de substâncias nem qualquer prática sem orientação adequada.</p>
<p class="aula-cta">Na aula final deste módulo, você vai entender como esse conjunto de tradições diversas passou a ser chamado, no Ocidente, de “xamanismo” — e o que isso significou. Os povos originários das Américas, com toda a sua diversidade, ganharão um módulo próprio e cursos de aprofundamento específicos.</p>
"""


AULA_M2_3 = CAPA_M2_AULA_3 + """
<p class="aula-kicker">Módulo 2 · Aula 3 · Do estudo acadêmico ao mundo contemporâneo</p>
<h2>Como o xamanismo chegou ao mundo moderno</h2>
<p class="aula-subtitulo">De relatos de viajantes a um fenômeno urbano global — e por que essa trajetória exige cuidado.</p>

<p>Até aqui, você viu de onde vem a palavra “xamã” e como práticas comparáveis aparecem em povos distintos ao redor do mundo. Falta uma pergunta: como esse conjunto de observações virou o “xamanismo” que hoje aparece em livrarias, redes sociais e retiros espirituais nas grandes cidades? Essa aula percorre esse caminho — dos estudos acadêmicos ao chamado neoxamanismo.</p>

<h3>Viajantes, linguistas e os primeiros antropólogos</h3>
<p><strong>Conhecimento histórico:</strong> depois dos primeiros relatos de viajantes sobre a Sibéria, nos séculos XVII e XVIII, o interesse europeu por essas práticas cresceu ao longo dos séculos XIX e XX. Linguistas estudaram a origem da palavra; etnógrafos passaram temporadas com comunidades siberianas registrando cerimônias, cantos e narrativas; e, aos poucos, antropólogos começaram a comparar o que encontravam na Sibéria com práticas observadas em outras partes do mundo — nas Américas, na África, na Ásia e na Oceania.</p>
<p>Foi nesse processo comparativo, sobretudo ao longo do século XX, que o termo “xamanismo” deixou de descrever apenas fenômenos siberianos e passou a ser usado como categoria de análise mais ampla em antropologia da religião. Alguns pesquisadores utilizam o termo dessa forma ampliada; outros preferem termos mais específicos para cada povo, justamente para evitar generalizações.</p>

<h3>O interesse ocidental por espiritualidade e estados de consciência</h3>
<p>Ao longo do século XX, sobretudo a partir das décadas de 1950, 1960 e 1970, cresceu no Ocidente um interesse amplo por espiritualidades não cristãs, estados alterados de consciência e experiências vividas como transcendentes. Esse interesse teve várias fontes: publicações acadêmicas e best-sellers sobre práticas espirituais de outros povos, movimentos contraculturais que questionavam valores estabelecidos, e um clima social de busca por novos sentidos existenciais.</p>
<p><strong>Interpretação contemporânea:</strong> nesse contexto, surgiu o que hoje é chamado de <em>neoxamanismo</em> — um conjunto diverso de práticas modernas, geralmente urbanas, que se inspiram em elementos associados ao xamanismo (tambor, jornada ritual, busca por cura ou autoconhecimento), muitas vezes combinados com psicologia, terapias alternativas e esoterismo contemporâneo. É importante frisar: o neoxamanismo é um fenômeno do seu próprio tempo e contexto — não é a mesma coisa que a tradição comunitária de um povo específico, mesmo quando toma elementos emprestados dela.</p>

<div class="aula-timeline-wrap">
<figure class="aula-imagem aula-imagem-timeline">
  <img src="assets/escola/xamanismo/linha-tempo-xamanismo.svg" width="1200" height="460" loading="lazy" alt="Linha do tempo esquemática, com datas aproximadas, mostrando desde tradições anteriores aos registros escritos até os debates contemporâneos sobre respeito cultural">
  <figcaption>Linha do tempo introdutória — as datas são aproximadas; tradições ancestrais não têm um marco inicial exato. <span class="aula-imagem-credito">Ilustração original — Mística Escola.</span></figcaption>
</figure>
</div>

<h3>Tradições comunitárias e adaptações urbanas: o que muda</h3>
<p>Uma tradição comunitária costuma estar ligada a um povo específico, com transmissão entre gerações, autoridade reconhecida pela própria comunidade, língua, território e responsabilidades coletivas. Uma adaptação urbana neoxamânica, por outro lado, costuma ser aprendida em cursos, retiros ou livros, muitas vezes fora do território e da língua de origem, e sem o mesmo sistema de autorização comunitária. Isso não torna a experiência urbana automaticamente falsa ou sem valor para quem a vive — mas significa que ela é outra coisa, com outra história e outra responsabilidade.</p>

<h3>Benefícios e riscos do interesse contemporâneo</h3>
<p>O interesse contemporâneo por essas tradições trouxe efeitos em várias direções. Por um lado, ajudou a dar visibilidade a povos e conhecimentos historicamente marginalizados, e despertou em muitas pessoas um interesse genuíno por ecologia, saúde mental e espiritualidade. Por outro lado, também trouxe riscos reais.</p>

<aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência e da Antropologia</h3><p>Pesquisadores em antropologia e estudos da religião frequentemente apontam dois riscos principais no interesse contemporâneo pelo tema: a <strong>apropriação cultural</strong> — quando símbolos, cerimônias ou conhecimentos de um povo são retirados de seu contexto original, comercializados e desvinculados de sua autoria, sem consentimento nem retorno para a comunidade — e a <strong>comercialização irresponsável</strong>, quando cerimônias, objetos sagrados ou até substâncias são vendidos sem o conhecimento, a segurança e a autorização que a tradição original exige.</p></aside>

<h3>Símbolos fora de contexto</h3>
<p>Um risco frequente é o uso de símbolos de povos diferentes misturados entre si, como se fossem intercambiáveis — um cocare de um povo, um símbolo gráfico de outro, uma palavra de uma terceira língua, tudo reunido numa única “estética xamânica” genérica. Esse tipo de mistura apaga justamente o que este módulo procurou destacar: cada povo tem seus próprios símbolos, com seus próprios significados, muitas vezes restritos a contextos e pessoas específicas dentro da própria comunidade.</p>

<aside class="aula-box aula-box-respeito"><h3>Respeito às Tradições</h3><p>Os povos originários citados ao longo deste módulo não são figuras do passado: são povos vivos e contemporâneos, com suas próprias organizações, pesquisadores, lideranças e formas de comunicação. A forma mais responsável de se aproximar desses temas é priorizar as vozes desses povos e de pesquisadores especializados — algo que esta formação levará a sério nos módulos e cursos seguintes, dedicados à diversidade dos povos originários das Américas.</p></aside>

<h3>Quatro lentes para não confundir</h3>
<p>Ao longo deste módulo, vale reforçar a diferença entre quatro tipos de conhecimento que frequentemente se misturam quando o assunto é xamanismo:</p>
<ul>
  <li><strong>História documentada:</strong> o que registros, relatos e pesquisas historiográficas permitem reconstruir com evidências datáveis.</li>
  <li><strong>Tradição oral:</strong> conhecimentos transmitidos de geração em geração dentro de uma comunidade, com sua própria lógica interna de autoridade e validação.</li>
  <li><strong>Interpretação antropológica:</strong> leituras comparativas produzidas por pesquisadores, sujeitas a revisão, debate e diferentes escolas de pensamento.</li>
  <li><strong>Crença espiritual:</strong> convicções sobre o sagrado, aceitas dentro de uma tradição ou por uma pessoa, que não são o mesmo tipo de afirmação que um dado histórico ou científico.</li>
</ul>
<p>Misturar essas quatro lentes é uma das formas mais comuns de simplificar — e, às vezes, distorcer — este assunto. Um bom estudo do xamanismo mantém essas lentes separadas, mesmo quando elas dialogam entre si.</p>

<h3>Palavras importantes</h3>
<dl class="aula-glossario">
  <dt>Neoxamanismo</dt><dd>Conjunto diverso de práticas contemporâneas, geralmente urbanas, inspiradas em elementos associados ao xamanismo, com contexto e autoria distintos das tradições comunitárias originais.</dd>
  <dt>Apropriação cultural</dt><dd>Uso de elementos culturais de um povo fora de contexto, sem consentimento, autoria reconhecida ou retorno para a comunidade de origem.</dd>
  <dt>Contracultura</dt><dd>Movimentos sociais que, sobretudo a partir da década de 1960, questionaram valores estabelecidos no Ocidente, incluindo modelos religiosos e de consciência.</dd>
  <dt>Povos originários</dt><dd>Povos com continuidade histórica e vínculo próprio com seus territórios, línguas e culturas, presentes e atuantes no mundo contemporâneo.</dd>
</dl>

<aside class="aula-box aula-box-refletir"><h3>Para refletir</h3><p>Pense em uma experiência, produto ou conteúdo “xamânico” que você já viu anunciado. Com base no que aprendeu neste módulo, quais perguntas você faria sobre a origem dessa prática, sobre quem autorizou seu uso e sobre para onde vai o que é pago por ela?</p></aside>

<h3 id="revisao-livre">Atividade livre de revisão</h3>
<p>As perguntas abaixo são uma revisão opcional, pensada para você conferir sua própria compreensão do módulo. Clique em cada pergunta para revelar o comentário depois de pensar em uma resposta.</p>
<p class="aula-aviso"><strong>Esta é uma atividade livre de revisão. Ela não substitui a avaliação oficial da formação.</strong> Suas respostas não são enviadas, salvas ou avaliadas por ninguém — a correção é só para o seu próprio estudo, aqui no navegador.</p>
<div class="aula-revisao">
  <details class="aula-revisao-item"><summary>1. A palavra “xamã” tem origem documentada em qual contexto?</summary><p>Nas línguas tungúsicas da Sibéria, com destaque para o povo evenki — não em uma origem universal válida para todos os povos espirituais do mundo.</p></details>
  <details class="aula-revisao-item"><summary>2. Práticas rituais parecidas em povos distantes entre si provam uma origem comum?</summary><p>Não necessariamente. Elas podem ter surgido de forma independente, como resposta a desafios humanos semelhantes — a antropologia investiga caso a caso.</p></details>
  <details class="aula-revisao-item"><summary>3. Todo especialista espiritual de qualquer povo do mundo pode ser chamado corretamente de “xamã”?</summary><p>Não. Cada povo tem nomes, funções e responsabilidades próprios; usar “xamã” de forma universal apaga essa diversidade.</p></details>
  <details class="aula-revisao-item"><summary>4. O que é o neoxamanismo?</summary><p>Um conjunto de práticas contemporâneas, geralmente urbanas, inspiradas em elementos associados ao xamanismo — com contexto, autoria e história diferentes das tradições comunitárias originais.</p></details>
  <details class="aula-revisao-item"><summary>5. Qual é a diferença entre tradição oral e interpretação antropológica?</summary><p>A tradição oral é o conhecimento transmitido dentro de uma comunidade, com sua própria autoridade interna. A interpretação antropológica é uma leitura comparativa produzida por pesquisadores externos, sujeita a debate acadêmico.</p></details>
  <details class="aula-revisao-item"><summary>6. Por que misturar símbolos de povos diferentes é considerado um problema?</summary><p>Porque cada povo tem símbolos com significados próprios, muitas vezes restritos a contextos específicos; misturá-los sem critério apaga essa especificidade e pode configurar apropriação cultural.</p></details>
</div>

<h3>Resumo</h3>
<p>O termo “xamanismo” percorreu um longo caminho: de relatos de viajantes na Sibéria a categoria de estudo antropológico, até se tornar um fenômeno urbano contemporâneo conhecido como neoxamanismo. Esse caminho trouxe benefícios — visibilidade, diálogo, interesse por saúde mental e ecologia — e riscos reais, como apropriação cultural e comercialização irresponsável. Manter separadas as lentes da história, da tradição oral, da interpretação antropológica e da crença espiritual é essencial para estudar o tema com responsabilidade.</p>
<p class="aula-aviso"><strong>Nota de cuidado:</strong> este módulo é educativo. Não substitui orientação médica, psicológica, jurídica ou religiosa e não descreve, ensina ou incentiva o consumo de substâncias.</p>
<p class="aula-cta">Na próxima etapa, conheceremos a diversidade dos povos originários das Américas e compreenderemos por que não existe uma única espiritualidade indígena. Essa jornada será aprofundada, com muito mais tempo e cuidado, na formação completa em <strong>História do Xamanismo</strong>.</p>

<h3>Referências e leituras recomendadas</h3>
<p class="aula-referencias">Este módulo se apoia em interpretações amplamente discutidas por historiadores, linguistas e antropólogos especializados no tema — entre eles, estudos clássicos sobre a etimologia tungúsica do termo “xamã”, trabalhos de antropologia comparada da religião sobre práticas rituais em diferentes continentes, publicações da UNESCO sobre patrimônio cultural imaterial e materiais produzidos por organizações e pesquisadores indígenas sobre autorrepresentação e apropriação cultural. Nenhuma dessas fontes é citada aqui como consenso absoluto: onde existe debate acadêmico, este curso procurou indicá-lo. Aprofundaremos essas referências, com indicação de autores e obras específicas, na formação completa.</p>
"""


QUESTOES = [
    ("Por que o termo “xamanismo” deve ser usado com cuidado?", ["Porque nomeia uma religião mundial única", "Porque é um termo amplo aplicado a tradições distintas", "Porque todas as tradições recusam a palavra", "Porque se refere apenas a práticas modernas"], 1, "Correta: o termo é uma ferramenta ampla e pode ocultar diferenças. As demais confundem diversidade com unidade, fazem uma afirmação universal ou ignoram sua origem histórica."),
    ("A origem histórica mais aceita da palavra “xamã” está ligada a:", ["Línguas tungúsicas da Sibéria, como o evenki", "Uma palavra portuguesa medieval", "Uma doutrina criada no século XXI", "Uma única língua indígena das Américas"], 0, "Correta: a etimologia é associada a šamān, em línguas tungúsicas. As demais atribuem origem geográfica ou temporal incompatível com o conteúdo."),
    ("O que a existência de práticas semelhantes em povos diferentes permite concluir?", ["Que todos vieram de uma religião única", "Que os rituais podem ser copiados livremente", "Que é possível comparar, sem afirmar que são idênticos", "Que todas as crenças são cientificamente comprovadas"], 2, "Correta: semelhanças permitem comparação contextual. Elas não provam origem única, não anulam consentimento e não equivalem a evidência científica."),
    ("Qual frase diferencia corretamente crença espiritual e evidência científica?", ["Toda crença é um fato de laboratório", "A ciência confirma automaticamente explicações espirituais", "Crenças não têm valor cultural", "A ciência pode estudar efeitos sem confirmar toda interpretação espiritual"], 3, "Correta: métodos científicos estudam efeitos observáveis e têm limites. As demais confundem campos ou negam indevidamente o valor cultural."),
    ("O que caracteriza uma abordagem respeitosa aos povos originários?", ["Tratálos como uma única cultura", "Reconhecer povos, línguas e visões de mundo distintas", "Apresentálos apenas no passado", "Usar símbolos sagrados sem consultar ninguém"], 1, "Correta: diversidade e presença contemporânea são essenciais. As outras opções generalizam, apagam ou desrespeitam consentimento."),
    ("Por que tradições ancestrais permanecem vivas?", ["Porque nunca mudam", "Porque são apenas peças de museu", "Porque comunidades as transmitem e recriam", "Porque dependem exclusivamente das redes sociais"], 2, "Correta: continuidade envolve transmissão e recriação comunitária. Imobilidade, museificação ou uma tecnologia isolada não explicam tradições vivas."),
    ("Qual situação é um sinal de risco de apropriação cultural?", ["Citar a comunidade e respeitar limites", "Remunerar autores indígenas", "Ouvir como um povo deseja ser nomeado", "Vender cerimônia descontextualizada e silenciar seus detentores"], 3, "Correta: exploração sem contexto, voz ou benefício é sinal de apropriação. As demais são práticas de reconhecimento e respeito."),
    ("O que a ciência pode estudar em relação a rituais?", ["Efeitos psicológicos, sociais, culturais e fisiológicos", "A verdade definitiva de toda cosmologia", "Somente se a tradição abandonar sua identidade", "Nada, em nenhuma circunstância"], 0, "Correta: esses efeitos podem ser investigados com métodos adequados. As demais exageram o alcance da ciência ou negam a possibilidade de pesquisa."),
    ("Uma prática urbana inspirada no xamanismo é automaticamente uma tradição indígena?", ["Sim, se usar tambor", "Sim, se for vendida como retiro", "Não; tem contexto e autoridade próprios", "Sim, se misturar símbolos de muitos povos"], 2, "Correta: releituras contemporâneas devem ser nomeadas como tais. Objetos, marketing ou mistura de símbolos não conferem legitimidade tradicional."),
    ("Qual é a orientação de segurança apresentada no módulo?", ["Substituir tratamentos por práticas espirituais", "Usar substâncias sem acompanhamento", "Considerar o curso uma prescrição médica", "Não confundir prática espiritual com tratamento profissional"], 3, "Correta: o curso é educativo e não substitui cuidados profissionais. As demais contradizem explicitamente os limites e cuidados ensinados."),
]


def instalar_conteudo_xamanismo(conn) -> bool:
    """Instala a versão oficial uma vez e retorna True quando houve mudança."""
    from backend.lms import garantir_tabelas_lms

    garantir_tabelas_lms(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS lms_content_versions (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
    if conn.execute("SELECT 1 FROM lms_content_versions WHERE versao=?", (VERSAO,)).fetchone():
        return False

    agora = _agora()
    conn.execute(
        """INSERT INTO curso_config (slug,titulo,descricao,nota_minima,certificado,requer_matricula,publicado,atualizado_em)
        VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET titulo=excluded.titulo,
        descricao=excluded.descricao,nota_minima=excluded.nota_minima,certificado=excluded.certificado,
        requer_matricula=excluded.requer_matricula,publicado=excluded.publicado,atualizado_em=excluded.atualizado_em""",
        (SLUG, "Introdução ao Xamanismo — As Origens da Sabedoria Ancestral", "Curso introdutório sobre história, diversidade cultural, espiritualidade e leitura crítica do xamanismo.", 70, 0, 0, 1, agora),
    )
    existente = conn.execute("SELECT id FROM curso_modulos WHERE slug=? AND ordem=0", (SLUG,)).fetchone()
    if existente:
        modulo_id = int(existente["id"])
        conn.execute("UPDATE curso_modulos SET titulo=?,descricao=?,nota_minima=70,publicado=1,acesso_publico=1 WHERE id=?", ("Módulo 1 — O Chamado do Xamanismo", "Fundamentos históricos, diversidade cultural e permanência das tradições.", modulo_id))
        conn.execute("DELETE FROM curso_aulas WHERE modulo_id=? AND NOT EXISTS (SELECT 1 FROM aluno_aula_progresso p WHERE p.aula_id=curso_aulas.id)", (modulo_id,))
    else:
        modulo_id = int(conn.execute("INSERT INTO curso_modulos (slug,titulo,descricao,ordem,nota_minima,publicado,acesso_publico,criado_em) VALUES (?,?,?,?,?,?,?,?)", (SLUG, "Módulo 1 — O Chamado do Xamanismo", "Fundamentos históricos, diversidade cultural e permanência das tradições.", 0, 70, 1, 1, agora)).lastrowid)

    aulas = [
        ("O que é o Xamanismo?", "Um primeiro mapa para compreender um termo amplo sem apagar a diversidade cultural.", AULA_1, 0, 12),
        ("Por que o Xamanismo ainda existe?", "Tradições vivas, transmissão entre gerações e os encontros responsáveis do presente.", AULA_2, 1, 12),
    ]
    for titulo, descricao, conteudo, ordem, duracao in aulas:
        if not conn.execute("SELECT 1 FROM curso_aulas WHERE modulo_id=? AND ordem=?", (modulo_id, ordem)).fetchone():
            conn.execute("""INSERT INTO curso_aulas (modulo_id,titulo,descricao,tipo,conteudo,ordem,duracao_min,obrigatoria,publicado,criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (modulo_id, titulo, descricao, "texto", conteudo, ordem, duracao, 1, 1, agora))

    quiz = conn.execute("SELECT id FROM curso_quizzes WHERE modulo_id=?", (modulo_id,)).fetchone()
    if quiz:
        quiz_id = int(quiz["id"])
        conn.execute("UPDATE curso_quizzes SET titulo=?,nota_minima=70,num_perguntas=10,max_tentativas=3,intervalo_min=0,embaralhar_perguntas=1,embaralhar_opcoes=1,publicado=1 WHERE id=?", ("Avaliação — O Chamado do Xamanismo", quiz_id))
        sem_tentativas = not conn.execute("SELECT 1 FROM quiz_tentativas WHERE quiz_id=? LIMIT 1", (quiz_id,)).fetchone()
        if sem_tentativas:
            conn.execute("DELETE FROM quiz_opcoes WHERE pergunta_id IN (SELECT id FROM quiz_perguntas WHERE quiz_id=?)", (quiz_id,))
            conn.execute("DELETE FROM quiz_perguntas WHERE quiz_id=?", (quiz_id,))
    else:
        quiz_id = int(conn.execute("""INSERT INTO curso_quizzes (modulo_id,titulo,nota_minima,num_perguntas,max_tentativas,intervalo_min,embaralhar_perguntas,embaralhar_opcoes,publicado,criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (modulo_id, "Avaliação — O Chamado do Xamanismo", 70, 10, 3, 0, 1, 1, 1, agora)).lastrowid)
        sem_tentativas = True
    if sem_tentativas and not conn.execute("SELECT 1 FROM quiz_perguntas WHERE quiz_id=?", (quiz_id,)).fetchone():
        for ordem, (enunciado, opcoes, correta, explicacao) in enumerate(QUESTOES):
            pid = int(conn.execute("INSERT INTO quiz_perguntas (quiz_id,enunciado,tipo,explicacao,ordem,ativa,criado_em) VALUES (?,?,?,?,?,?,?)", (quiz_id, enunciado, "unica", explicacao, ordem, 1, agora)).lastrowid)
            for pos, texto in enumerate(opcoes):
                conn.execute("INSERT INTO quiz_opcoes (pergunta_id,texto,correta,ordem) VALUES (?,?,?,?)", (pid, texto, 1 if pos == correta else 0, pos))

    # Destino real da progressão: fica bloqueado até as duas aulas e a avaliação.
    m2_existente = conn.execute("SELECT id FROM curso_modulos WHERE slug=? AND ordem=1", (SLUG,)).fetchone()
    if m2_existente:
        conn.execute("UPDATE curso_modulos SET acesso_publico=1 WHERE id=?", (int(m2_existente["id"]),))
    else:
        m2 = int(conn.execute("INSERT INTO curso_modulos (slug,titulo,descricao,ordem,nota_minima,publicado,acesso_publico,criado_em) VALUES (?,?,?,?,?,?,?,?)", (SLUG, "Módulo 2 — Origens e Caminhos", "Próxima etapa da jornada, em preparação editorial.", 1, 70, 1, 1, agora)).lastrowid)
        conn.execute("""INSERT INTO curso_aulas (modulo_id,titulo,descricao,tipo,conteudo,ordem,duracao_min,obrigatoria,publicado,criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (m2, "Em breve: origens históricas e diversidade", "Conteúdo do próximo módulo em preparação.", "texto", "<h2>Sua próxima etapa foi liberada</h2><p>Em breve, este espaço receberá as origens históricas do xamanismo, sua presença em diferentes regiões e a diversidade das tradições dos povos originários.</p>", 0, 1, 1, 1, agora))

    conn.execute("INSERT INTO lms_content_versions (versao,aplicada_em) VALUES (?,?)", (VERSAO, agora))
    return True


def instalar_conteudo_modulo2_xamanismo(conn) -> bool:
    """Substitui o placeholder do Módulo 2 pelo conteúdo editorial completo.

    Migração de conteúdo idempotente e independente da versão do Módulo 1
    (VERSAO): tem seu próprio marcador (VERSAO_MODULO_2) para poder ser
    aplicada mesmo em bancos que já registraram a versão anterior. Nunca
    apaga aulas com progresso registrado por algum aluno; preserva o
    módulo em acesso_publico=1 e não cria nem toca em nenhum outro módulo.
    """
    from backend.lms import garantir_tabelas_lms

    garantir_tabelas_lms(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS lms_content_versions (versao TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL)")
    if conn.execute("SELECT 1 FROM lms_content_versions WHERE versao=?", (VERSAO_MODULO_2,)).fetchone():
        return False

    agora = _agora()
    titulo_modulo = "Módulo 2 — As Origens e os Caminhos do Xamanismo"
    descricao_modulo = "As origens históricas do termo, tradições rituais comparáveis em diferentes regiões e o caminho do xamanismo até o mundo contemporâneo."

    existente = conn.execute("SELECT id FROM curso_modulos WHERE slug=? AND ordem=1", (SLUG,)).fetchone()
    if existente:
        modulo_id = int(existente["id"])
        conn.execute(
            "UPDATE curso_modulos SET titulo=?,descricao=?,nota_minima=70,publicado=1,acesso_publico=1 WHERE id=?",
            (titulo_modulo, descricao_modulo, modulo_id),
        )
        conn.execute(
            "DELETE FROM curso_aulas WHERE modulo_id=? AND NOT EXISTS (SELECT 1 FROM aluno_aula_progresso p WHERE p.aula_id=curso_aulas.id)",
            (modulo_id,),
        )
    else:
        modulo_id = int(conn.execute(
            "INSERT INTO curso_modulos (slug,titulo,descricao,ordem,nota_minima,publicado,acesso_publico,criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (SLUG, titulo_modulo, descricao_modulo, 1, 70, 1, 1, agora),
        ).lastrowid)

    aulas = [
        ("A origem da palavra “xamã”", "De onde vem esse nome tão repetido — e por que ele nasceu em um lugar muito específico do mundo.", AULA_M2_1, 0, 13),
        ("Tradições semelhantes em diferentes regiões", "Cantos, tambores e sonhos aparecem em muitos povos — mas cada tradição tem seu próprio nome e sua própria história.", AULA_M2_2, 1, 14),
        ("Como o xamanismo chegou ao mundo moderno", "De relatos de viajantes a um fenômeno urbano global — e por que essa trajetória exige cuidado.", AULA_M2_3, 2, 15),
    ]
    for titulo, descricao, conteudo, ordem, duracao in aulas:
        if not conn.execute("SELECT 1 FROM curso_aulas WHERE modulo_id=? AND ordem=?", (modulo_id, ordem)).fetchone():
            conn.execute(
                """INSERT INTO curso_aulas (modulo_id,titulo,descricao,tipo,conteudo,ordem,duracao_min,obrigatoria,publicado,criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (modulo_id, titulo, descricao, "texto", conteudo, ordem, duracao, 1, 1, agora),
            )
        else:
            conn.execute(
                "UPDATE curso_aulas SET titulo=?,descricao=?,conteudo=?,duracao_min=? WHERE modulo_id=? AND ordem=?",
                (titulo, descricao, conteudo, duracao, modulo_id, ordem),
            )

    conn.execute("INSERT INTO lms_content_versions (versao,aplicada_em) VALUES (?,?)", (VERSAO_MODULO_2, agora))
    return True
