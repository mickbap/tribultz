# Persistência de Estado dos Agentes na CrewAI

## O Desafio: Reinício de Contêiner e Consistência Fiscal
Cálculos de reforma tributária são transacionais, envolvendo múltiplas etapas em cadeia. Se um contêiner for desligado (evicção ou *restart* do Docker), o estado em memória dos agentes da CrewAI não pode ser perdido.

## Planejamento de Implementação

1. **Memória Abstraída (Storage-Backed Memory):**
   - Não utilizaremos a memória "In-Memory" padrão como única fonte da verdade da CrewAI em produção.
   - O estado de cada tarefa (*task context*, *memory buffer* de agentes, e o histórico da conversa) será persistido em um storage rápido e transacional, como **Redis** (para state efêmero rápido) ou **PostgreSQL / MongoDB** via abstração do LangChain/LlamaIndex.
   
2. **Check-pointing Constante:**
   - A cada avanço de etapa de um Agente ou repasse de tarefa (Handoff), o sistema salva o `checkpoint_id`.
   - Em caso de *crash* e subida de um novo contêiner, o serviço de Orquestração busca o último checkpoint atrelado àquela sessão transacional e remonta o grafo de memória do Agente.

3. **Idempotência no Cálculo Tributário:**
   - Para garantir consistência fiscal, todas as ferramentas (`tools`) que interagem com o mundo externo serão desenhadas para serem idempotentes (podem ser chamadas mais de uma vez sem alterar o resultado base de forma destrutiva, exceto a emissão final, sob controle estrito de *lock* distribuído).
