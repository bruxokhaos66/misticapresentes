"""Conteúdo editorial oficial do curso introdutório de Xamanismo.

A instalação é uma migração de conteúdo idempotente: grava no mesmo SQLite e
nas mesmas tabelas usadas pelo painel da Escola Mística, uma única vez por
versão. Depois disso o conteúdo pode ser editado normalmente pelo admin sem ser
sobreposto a cada inicialização.
"""

from __future__ import annotations

from datetime import datetime

SLUG = "xamanismo-introducao"
VERSAO = "xamanismo-modulo-1-v1"


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
