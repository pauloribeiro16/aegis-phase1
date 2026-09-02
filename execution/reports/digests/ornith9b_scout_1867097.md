# Ornith 1.5 (9B) — resultado do teste (JOB 1867097)

**Avaliado por:** GLM-5.3-Flash (o assistente desta sessão), 2026-09-02
**Caso:** TinyTask (4 chamadas ao modelo: análise de GDPR + CRA)
**Tempo total:** 4,2 minutos — **o mais rápido de todos os testados**

**Resumo em português simples:** O ornith é um modelo pequeno (9B) mas
surpreendeu: respondeu quase ao nível do qwen3.8 (que é 3× maior) e foi
**3 a 4 vezes mais rápido** que todos. Seguiu o formato pedido,
respondeu correctamente às questões principais, e — ao contrário do
qwen3.5 — produziu a lista de implicações e lacunas estruturada com
esforço e referências. **Nota: 4.4 e 4.1 em 5.**

---

## O que o modelo respondeu

### Questão 1 — Interpretações e exclusões (CRA e GDPR)

Activou correctamente as interpretações e exclusões, e em cada decisão
indicou **o facto da empresa que a determinou**. Exemplos:

- "A exclusão CRA de produto não colocado no mercado **não se aplica**
  porque o caso confirma que a TinyTask coloca produtos no mercado da UE."
- "A interpretação de prazos sectoriais GDPR **não se activa** porque o
  sector 'Tecnologia/Software' não está na lista ['saúde', 'energia'...]
  — mas a obrigação geral de notificação em 72h mantém-se para todos."

Esta última distinção (a interpretação específica não se activa, mas a
obrigação de base mantém-se) é sofisticada — nem todos os modelos a fazem.

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 5 | Cada decisão cita o facto que a determinou |
| Exactidão regulamentar | 4.5 | Todos os veredictos correctos |
| Utilidade prática | 3 | Respondeu às questões, sem recomendações extra (é da questão 2) |
| Seguiu o formato pedido | 5 | Formato perfeito |
| Sem "encher" | 4 | Denso |
| **Nota final** | **4.4 / 5** | |

### Questão 2 — Racional, implicações e lacunas

Produziu **2 implicações + 4 lacunas estruturadas**, cada uma com:
- descrição com artigo do regulamento (ex.: "CRA Art. 14(1)... 24h")
- esforço estimado ("horas a dias", "meses")
- dependências entre itens
- referências para os ficheiros do método e factos da empresa

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 4 | Referências presentes, **mas** 2 usam um marcador genérico ("DOC04:SEC-NN") que não existe no caso — a verificar |
| Exactidão regulamentar | 4 | Citou "Art. 36" para documentação técnica onde o qwen3.8 citou "Art. 13 + Anexo VII" — um dos dois está errado, a verificar |
| Utilidade prática | 4.5 | Esforço + dependências presentes; faltou prioridade P1/P2 |
| Seguiu o formato pedido | 4 | Campos estruturados, mas dentro de uma secção única em vez de secções separadas (implicações vs lacunas) |
| Sem "encher" | 4 | Longo mas denso |
| **Nota final** | **4.1 / 5** | |

## Tempo e custos

| | ornith 9B | qwen3.8 27B | qwen3.5 27B |
|---|---|---|---|
| Tempo total das chamadas | **4,2 min** | 12,6 min | 17,5 min |
| Tamanho do modelo | 5,6 GB | ~17 GB | ~17 GB |

**O melhor rácio qualidade/tempo medido até agora.** Se responder bem
às questões de fase seguinte (ainda não testadas neste modelo), é um
candidato sério.

## O que verificar manualmente (se quiseres)

1. As referências "DOC04:SEC-NN" — parecem marcadores genéricos e não
   chaves reais do caso. Se confirmares, a nota da questão 2 desce para
   ~3.8.
2. A citação "Art. 36" para documentação técnica (conflita com o
   qwen3.8, que citou Art. 13 + Anexo VII).

## Comparação com os outros modelos testados

| Modelo | Questão 1 | Questão 2 | Tempo |
|---|---|---|---|
| qwen3.8 27B | 4.7 | 4.9 | 12,6 min |
| **ornith 9B** | **4.4** | **4.1** | **4,2 min** |
| granite 30B | 3.5 | 4.4 | 28 min |
| qwen3.5 27B | 3.5 | 3.3 | 17,5 min |
