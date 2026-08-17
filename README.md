# jared

Conversa com um modelo de linguagem no terminal. Desenho em uma frase:
**o modelo propõe, você aciona.**

```bash
jared                         # abre na pasta atual
jared -f                      # abre com ferramentas ligadas
jared -m qwen-think           # outro perfil do registro
jared --projeto llm-local     # já com o contexto do projeto carregado
jared "o que é um contig?"    # resposta única, serve para pipe e script
jared --modelos               # lista o registro e sai
```

## Por que existe

Trocar de modelo tinha de ser **uma linha de configuração**, não uma alteração
de código. O registro fica em `~/.config/jared/modelos.toml`; o programa não
sabe nada sobre modelo específico.

## O perfil — quem o assistente é

`~/.config/jared/perfil.md` **é** o prompt de sistema. Markdown puro, editável
com `/perfil`, e o programa não interpreta nada ali: manda como está.

Isso existe por causa de um erro concreto. Na primeira versão o prompt estava
cravado no código, afirmando que o dono era pesquisador de bioinformática e
listando Sanger, contigs e BLAST — inferido de um repositório de notas, sem
ninguém ter pedido. A correção não foi trocar o assunto: foi **o programa
deixar de ter opinião** sobre isso.

`/perfil padrao` restaura a semente, guardando a versão anterior ao lado.

## A abertura

Cinco direções, escolhidas com `/abertura <nome> [paleta]` — ou `jared
--aberturas` para ver todas:

| | |
|---|---|
| `selo` | cerimonial e simétrico; a moldura é o sigilo |
| `espinha` | sem moldura; o texto pende de um tentáculo na calha |
| `dossie` | ficha de caso; dados tabulados, sem figura |
| `silhueta` | a figura encapuzada em blocos, estado ao lado |
| `nenhuma` | só a linha de estado |

Paletas: `carmim`, `ouro`, `bruma`.

Restrição de desenho que veio da técnica: só entram caracteres de **largura 1
garantida** — ASCII, desenho de caixa (U+2500–257F) e blocos (U+2580–259F).
Glifo de largura ambígua desalinha a moldura em metade dos terminais.

## Comandos de dentro

| | |
|---|---|
| `/think on\|off` | liga o raciocínio — custa minutos por resposta |
| `/modelo <apelido>` · `/modelos` | troca de modelo no meio da conversa |
| `/ferramentas on\|leitura\|off` | libera o modelo para agir na pasta |
| `/pasta <caminho>` | muda a raiz do confinamento |
| `/skills [busca]` · `/skill <nome>` | procura e carrega uma das skills instaladas |
| `/projetos` · `/projeto <nome>` | carrega overview + status + 2 sessões do segundo cérebro |
| `/descarregar [nome]` | tira do contexto |
| `/ctx` | quanto do contexto está ocupado |
| `/limpar` · `/salvar [nome]` | esquece / grava a conversa |
| `/config` · `/recarregar` | edita e relê o `modelos.toml` |
| `/ref [acervo] <busca>` | procura num acervo de referência |
| `/ref+ <n>` | carrega o resultado no contexto |
| `!<comando>` | roda um comando **seu**, sem passar pelo modelo |

`Tab` completa comando, apelido de modelo, nome de skill e nome de projeto.

## Skills

São 136 skills nesta máquina. O programa **não** injeta nenhuma por padrão: lê
só `name` + `description` de cada `SKILL.md` para poder buscar, e o corpo entra
apenas quando você escolhe. É a ADR 0043 aplicada — recuperação, não prompt.

## Acervos de referência

Pastas grandes de markdown ou de livros, indexadas para busca. Declaradas em
`[acervos]` no `modelos.toml`:

```toml
[acervos]
h4cker = "~/Área de trabalho/SEC-Jared/h4cker-master"
livros = { raiz = "~/Área de trabalho/SEC-Jared/Security-Books-main", pdf = true }
```

`/ref <busca>` acha o verbete, `/ref+ <n>` carrega o trecho no contexto. Índice
barato (caminho + título + sumário), corpo sob demanda — a ADR 0043 de novo.
Para livros, o corpo é o **sumário**, não o livro inteiro. `pdftotext` extrai o
texto (sem pip); PDF escaneado entra achável pelo nome. Regenerar: `/ref
reindexar` ou `python3 -m nucleo.indexar`.

## As ferramentas, e o que as trava

Cinco ações: `listar`, `ler`, `buscar`, `escrever`, `executar`. **Não existe
ferramenta para apagar.**

As travas não foram inventadas aqui; são as que as ADRs do próprio autor já
estabeleceram, trazidas para o terminal:

- **link simbólico é resolvido** antes de comparar com a raiz (ADR 0021).
  `resultados.csv` apontando para `~/.ssh/id_rsa` não passa — testado nos 7
  casos de fuga em `testes/`.
- **sem shell por padrão** (ADR 0020). `|`, `>`, `&&`, `;`, `` ` ``, `$()` são
  recusados com explicação; o escape é declarado (`bash -c "…"`) e aparece
  inteiro na tela antes de rodar.
- **a confirmação mostra o `argv` já separado**, não a intenção declarada pelo
  modelo — você vê o comando exato que vai executar.
- **escrever mostra o diff** antes de perguntar.
- **nome de ferramenta inventado não vira ação** (ADR 0035): vira uma resposta
  dizendo quais existem, para o modelo se corrigir.
- programa interativo (`sudo`, `vim`, `python` pelado) é recusado: sem PTY ele
  travaria a conversa.

`/ferramentas leitura` dispensa a confirmação de `ler`/`buscar`/`listar`.
`escrever` e `executar` **sempre** perguntam.

## Modelo remoto

O registro aceita qualquer API compatível com OpenAI. Quando o modelo ativo é
remoto, a barra de estado escreve `remoto` em vermelho e o programa avisa ao
abrir e ao trocar — porque nesse caso **o texto sai da máquina**, que é
exatamente o custo que as ADRs 0008/0021/0033 administram.

Um modelo remoto sem a variável de ambiente da chave aparece no `/modelos` como
indisponível, com o nome da variável que falta.

## Instalação

O código mora aqui; o lançador em `~/.local/bin/jared` aponta para ele.
Requisitos: Python 3.11+ (usa `tomllib`) e o servidor do Ollama de pé:

```bash
~/.local/ollama-dist/bin/ollama serve &
```

Nenhuma dependência de `pip` — a máquina não tem.

## Testes

```bash
python3 testes/teste_confinamento.py    # 7 casos de fuga de caminho
python3 testes/teste_comandos.py        # 10 casos de triagem de comando
```
