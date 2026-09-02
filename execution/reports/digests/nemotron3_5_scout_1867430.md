# Nemotron 3.5 Lightning (30B) — resultado do teste (JOB 1867430)

**Avaliado por:** GLM-5.3-Flash (o assistente desta sessão), 2026-09-02
**Caso:** TinyTask (4 chamadas ao modelo: análise de GDPR + CRA)
**Tempo total:** 15 minutos — **o mais rápido dos modelos 30B**

**Resumo em português simples:** O nemotron foi **impecável**: 4 chamadas
sem uma única falha (nem repetições, nem erros), respondeu YES com
confiança ALTA em ambas as regulações, e produziu as listas de
implicações e lacunas no formato mais limpo de todos os testados.
Tal como o granite, respondeu "não sei" (INDETERMINATE) sobre a
exclusão open-source porque faltam factos no caso — é a resposta dele.
**Nota: 4.6 e 4.7 em 5 — o melhor resultado de sempre no benchmark.**

---

## O que o modelo respondeu

### Questão 1 — Interpretações e exclusões (CRA e GDPR)

Todas as decisões correctas, cada uma com o predicado citado:

- "A interpretação de duplo reporte **aplica-se** porque o papel da
  empresa é fabricante (role_matrix.cra.role = 'manufacturer') e o
  Art. 14(1) exige reporte em 24h de vulnerabilidades activamente
  exploradas."
- "A exclusão open-source fica **INDETERMINATE**: sem a licença do
  software e o propósito comercial documentados no caso, não é possível
  confirmar nem refutar. Pelo Recital 18, OSS comercial (modelo Red Hat)
  está em scope; OSS puro sem fim comercial está fora."

Reparou que a TinyTask tem gestão de vulnerabilidades PARCIAL
(dependabot + scans manuais) e usou esse facto para justificar a
relevância do reporte voluntário — liga os factos ao conselho.

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 4.5 | Predicados citados com os valores do caso; o "não sei" é honesto e fundamentado |
| Exactidão regulamentar | 4.5 | Art. 14(1)/(2), Art. 15, Art. 2, Recital 18 — tudo correcto |
| Utilidade prática | 4 | Consequências explicadas por item |
| Seguiu o formato pedido | 5 | Formato perfeito, confiança ALTA reportada |
| Sem "encher" | 5 | Densa e sem repetição |
| **Nota final** | **4.6 / 5** | |

### Questão 2 — Racional, implicações e lacunas

**5 implicações + 2 lacunas**, cada uma com o formato mais completo de
todos os modelos: identificador, descrição com artigos, esforço
estimado ajustado ao tamanho da empresa ("horas a dias — tier MICRO"),
dependências entre itens, e referências duplas (método + factos).

Exemplos reais do output:
- "IMP-D-04.1-1: detecção de breach e notificação em 72h (Art. 33(1))...
  a empresa tem incident_response PARCIAL e não tem playbook para o
  conflito 24h CRA vs 72h GDPR... esforço: dias"
- "GAP-GDPR-DPIA: sem avaliação de impacto apesar de monitorização
  sistemática... prioridade **P1**"

| Critério | Nota (0-5) | Porquê |
|---|---|---|
| Baseou-se nos factos do caso | 4.5 | Referências completas; ligou readiness PARTIAL/NO a cada lacuna |
| Exactidão regulamentar | 4.5 | Art. 32, 33, 34, 28, 35, 30 — correctos |
| Utilidade prática | 5 | Esforço + dependências + prioridades P1/P2 |
| Seguiu o formato pedido | 5 | Campos estruturados perfeitos |
| Sem "encher" | 5 | Denso |
| **Nota final** | **4.7 / 5** | |

## Tempo e custos

| | nemotron 30B | qwen3.8 27B | ornith 9B | granite 30B |
|---|---|---|---|---|
| Tempo total das chamadas | **~13 min** | 12,6 min | 4,2 min | ~28 min |
| Falhas durante o run | **0** | 0 | 0 | 2 (rede) |

## O que verificar manualmente (se quiseres)

1. O "não sei" sobre open-source — os factos que ele diz faltar
   (licença, propósito comercial) existem ou não no caso TinyTask?
   Se existirem e ele os não tiver visto, é um ponto a investigar.

## Comparação com os outros modelos testados

| Modelo | Questão 1 | Questão 2 | Tempo | Falhas |
|---|---|---|---|---|
| **nemotron 30B** | **4.6** | **4.7** | **13 min** | **0** |
| qwen3.8 27B | 4.7 | 4.9 | 12,6 min | 0 |
| ornith 9B | 4.4 | 4.1 | 4,2 min | 0 |
| granite 30B | 3.5 | 4.4 | 28 min | 2 |
| qwen3.5 27B | 3.5 | 3.3 | 17,5 min | 0 |

**O nemotron empata com o qwen3.8 em qualidade, é igualmente rápido, e
foi o único 30B sem qualquer falha.** Novo líder do benchmark junto com
o qwen3.8.
