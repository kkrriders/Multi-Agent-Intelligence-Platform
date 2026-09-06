# RAG retrieval ablation

Generated 2026-09-05 10:44 UTC by `benchmarks/rag_ablation.py`.

Hit rate (found the source chunk) over 5 cases, by retrieval mode:

| mode | hit rate |
|---|---|
| vector | 5/5 |
| keyword | 2/5 |
| hybrid | 5/5 |

| kind | query | vector | keyword | hybrid |
|---|---|---|---|---|
| paraphrase | what's the daily food budget when I'm on a business trip | hit | miss | hit |
| paraphrase | when do people have to leave the building | hit | miss | hit |
| rare_term | QX-88214-B | hit | hit | hit |
| rare_term | INFRA-77219 | hit | hit | hit |
| either | laptop monitor first day onboarding | hit | miss | hit |

Hybrid regressed vs. its best single mode on: none — hybrid never lost.