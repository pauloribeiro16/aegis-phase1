# Granite 4.2 (30B) — resultado do teste (JOB 1867429)

**Avaliado por:** GLM-5.3-Flash (o assistente desta sessão), 2026-09-02
**Caso:** TinyTask (4 chamadas ao modelo: análise de GDPR + CRA)
**Tempo total:** 36 minutos (o mais lento dos testados)

**Resumo em português simples:** O granite seguiu o formato de resposta
pedido e respondeu correctamente às questões principais. Mas é **muito
lento** (36 min vs 4 min do ornith), e numa das questões respondeu
"não sei" (INDETERMINATE) em vez de decidir — porque diz que faltam
factos sobre a licença do software no caso TinyTask. Isso é a resposta
dele: honesta, não adivinhou. **Nota: 3.5 e 4.4 em 5.**

---

## O que o modelo respondeu (GRAND-E CASOS)

### Questão 1 — Interpretações e exclusões (CRA e GDPR)

**CRA:** Activou correctamente as 2 interpretações
(notificação de vulnerabilidades em 24h à ENISA; reporte voluntário) e
marcou como "não aplicável" a exclusão de produtos não colocados no
mercado europeu.

**Sobre o software open-source, respondeu "não sei" (INDETERMINATE):**
disse que faltam factos no caso TinyTask sobre a licença do software e o
propósito comercial para poder decidir se a exclusão open-source se
aplica. Não adivinhou — parou e sinalizou.

**GDPR:** Na questão dos prazos sectoriais, respondeu correctamente "não
se aplica" (TinyTask não é dos sectores listados).

**Pontos fortes:** citou sempre onde foi buscar a decisão (factos da
empresa, artigos do regulamento). Não inventou artigos.
**Ponto fraco:** a auto-confiança que reportou foi "LOW" (baixa) — mesmo
onde acertou.

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 3.5 | Citou os factos, mas reportou confiança baixa e deixou 1 questão em aberto |
| Exactidão regulamentar | 3 | Acertou nas questões CRA; ficou a dever a decisão sobre open-source |
| Utilidade prática | 3 | Respondeu às questões, sem recomendações extra |
| Seguiu o formato pedido | 5 | Formato perfeito, sem desvios |
| Sem "encher" (respostas densas) | 4 | Denso e directo |
| **Nota final** | **3.5 / 5** | |

### Questão 2 — Racional, implicações e lacunas

Aqui o granite foi **forte**: produziu uma lista estruturada de
implicações e lacunas, cada uma com:
- descrição (ex.: "CRA Art. 14(1) exige reporte à ENISA em 24h")
- esforço estimado ("horas a dias", "meses")
- dependências entre lacunas
- referências para os ficheiros do método e factos da empresa

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 4.5 | Cada item com referências completas |
| Exactidão regulamentar | 4 | Artigos correctos (Art. 14, 15, Anexo I) |
| Utilidade prática | 5 | Esforço + dependências + referências: accionável por um DPO |
| Seguiu o formato pedido | 5 | Campos estruturados perfeitos |
| Sem "encher" | 4 | Denso |
| **Nota final** | **4.4 / 5** | |

## Tempo e custos

| | granite 30B | qwen3.8 27B | ornith 9B |
|---|---|---|---|
| Tempo total das chamadas | **~28 min** | 12.6 min | 4.2 min |
| Velocidade | ~200 tok/s | ~600 tok/s | ~600 tok/s |

**3× mais lento que o qwen3.8** no mesmo hardware. É o pior rácio
qualidade/tempo dos modelos testados até agora.

## O que verificar manualmente (se quiseres)

1. Se os factos sobre licença open-source existem ou não no caso
   TinyTask — foi a isso que o granite respondeu "não sei".
2. Houve 2 falhas de rede a meio (o servidor do modelo ficou 2× sem
   responder e a pipeline repetiu as chamadas automaticamente). Se
   acontecer noutros scouts, pode valer a pena reiniciar o servidor.

## Comparação com os outros modelos testados

| Modelo | Questão 1 | Questão 2 | Tempo |
|---|---|---|---|
| qwen3.8 27B | 4.7 | 4.9 | 12.6 min |
| ornith 9B | 4.4 | 4.1 | 4.2 min |
| **granite 30B** | **3.5** | **4.4** | **28 min** |
| qwen3.5 27B | 3.5 | 3.3 | 17.5 min |

O granite empatou com o qwen3.5 na questão 1 e foi melhor na questão 2,
mas é o mais lento de todos.
