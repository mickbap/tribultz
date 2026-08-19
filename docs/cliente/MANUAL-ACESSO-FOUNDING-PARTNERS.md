# Manual de Acesso — Programa Founding Partners

**Tribultz · Validação fiscal CBS/IBS**
Versão 1 · 18 de agosto de 2026

Bem-vindo ao Programa Founding Partners. Este manual cobre o essencial: como
entrar, o que você tem disponível, como validar sua primeira nota e a quem
recorrer. Leva cerca de dez minutos do primeiro acesso ao primeiro resultado.

---

## 1. Como o seu acesso é criado

Seu acesso **não é criado por autocadastro**. A Tribultz provisiona a conta e
envia as credenciais — isso é deliberado: garante que o CNPJ e o responsável
estejam corretos antes de qualquer dado fiscal entrar na plataforma.

Você recebe da Tribultz:

| Item | O que é |
|---|---|
| **E-mail de acesso** | o endereço informado no cadastro do programa |
| **Senha inicial** | definida pela Tribultz, com no mínimo 8 caracteres |
| **Empresa e CNPJ** | já vinculados à sua conta |
| **Vigência do seu acesso** | data de início e de término |

Seu e-mail já vem **verificado** — não há link de confirmação para clicar.

> **Sobre a vigência.** O acesso do Programa tem data de início e de término. É
> assim por desenho: o Programa é uma autorização por período, não uma
> assinatura. Antes do término, a Tribultz entra em contato para tratar a
> continuidade. Se você perder a data, o acesso passa a se comportar como conta
> sem plano ativo — nada é apagado.

---

## 2. Primeiro acesso

**1.** Acesse **https://tribultz.com.br/login**

**2.** Informe o e-mail e a senha inicial que recebeu.

**3.** Você cai no **Painel**, já dentro da sua empresa.

### Troque a senha inicial

A senha que você recebeu foi definida por outra pessoa, então troque no primeiro
dia:

**1.** No menu à esquerda, abra **Configurações**.
**2.** Na seção **Senha**, informe a senha atual e a nova (mínimo 8 caracteres).
**3.** Confirme. A nova senha vale a partir do próximo login.

Se você preferir, ou se esquecer a senha atual, o caminho alternativo continua
valendo: **/login** → **Esqueci minha senha** → link no seu e-mail.

---

## 3. O que você tem disponível

Founding Partners recebem o equivalente ao **plano Contador**, o mais completo:

| Recurso | Disponível |
|---|---|
| Validação de NF-e, NFC-e e NFS-e | **sem limite de quantidade** |
| Validação em lote | sim |
| Relatório em PDF | sim |
| Painel e Compliance Score | sim |
| Acesso à API | sim |
| Múltiplos CNPJs | sim — até **50** vínculos |
| Crédito IBS/CBS, Fechamento, Auditoria, Exceções | sim |

Se algum item acima não aparecer para você, fale com a gente antes de concluir
que não faz parte — pode ser configuração do seu acesso.

---

## 4. O mapa da plataforma

O menu à esquerda tem tudo. Em ordem de uso típico:

| Menu | Para que serve |
|---|---|
| **Painel** | visão geral: volume validado, achados, pendências |
| **Validar XML** | envie uma NF-e, NFC-e ou NFS-e e receba o laudo |
| **SPED Fiscal** | envie o arquivo SPED para conferência |
| **Compliance Score** | nota consolidada da sua conformidade e o que a derruba |
| **Fechamento** | consolidação do período, para conferir antes de transmitir |
| **Auditoria** | histórico com evidência de cada validação |
| **Exceções** | casos que você decidiu tratar como exceção justificada |
| **Jobs** | acompanhamento de processamentos longos |
| **Split Payment** | conteúdo e simulação do mecanismo previsto para 2027 |
| **Crédito IBS/CBS** | apuração de crédito |
| **Faturamento** | seu plano e histórico |
| **Configurações** | seus dados, chaves de API, LGPD e privacidade |
| **Suporte** | abertura de chamado |

---

## 5. Sua primeira validação, em três passos

**1.** Menu **Validar XML**.

**2.** Arraste o arquivo ou clique em **Selecionar arquivo**. Aceita `.xml` de
NF-e, NFC-e e NFS-e, até **2 MB** por arquivo.

**3.** O resultado sai na hora, organizado por severidade:

| Severidade | Significado | O que fazer |
|---|---|---|
| **FATAL** | a SEFAZ rejeita, ou rejeitará na vigência da regra | corrigir antes de transmitir |
| **ALERTA** | divergência que merece conferência, sem bloqueio garantido | avaliar caso a caso |
| **INFO** | observação de contexto | ciência |

Cada achado traz **a regra aplicada, o campo, o trecho do XML e a base legal** —
é o que torna o laudo utilizável numa discussão com contador, cliente ou
fiscalização. Você pode exportar em TXT e em PDF.

> **Uma observação honesta sobre severidade e datas.** Boa parte das regras da
> Reforma tem data de entrada em produção futura. Antes dessa data, o motor
> aponta como **alerta**, não como fatal — porque a nota não será rejeitada
> ainda. Depois da data, o mesmo achado escala. Isso é intencional: preferimos
> que você saiba com antecedência do que ser surpreendido no dia.

---

## 6. Trabalhando com mais de um CNPJ

Se o seu acesso tem mais de uma empresa vinculada, o **seletor no topo da tela**
troca entre elas. Ele aparece somente quando há mais de uma — com uma única
empresa, o nome fica fixo, sem seletor. Cada empresa tem seus próprios documentos, histórico e
indicadores.

**Para incluir um CNPJ novo, fale com a gente.** Na versão atual, a inclusão de
CNPJ é feita pela Tribultz, não pela tela — o seu plano permite até 50 vínculos,
mas o cadastro de cada um passa por nós. Estamos trabalhando para você fazer isso
sozinho; enquanto isso, o pedido é atendido por e-mail ou WhatsApp, normalmente
no mesmo dia útil.

---

## 7. Acesso via API

Seu plano inclui API. Em **Configurações → API Keys** você emite a sua chave.

- A chave aparece **uma única vez**, no momento da criação. Guarde-a com
  segurança — não conseguimos recuperá-la depois, apenas revogar e emitir outra.
- Você recebe **100 créditos** na criação da chave.
- Até **5 chaves ativas** por conta.
- A chave vai no cabeçalho `X-API-Key` das requisições.

Chave comprometida? Revogue em **Configurações → API Keys** e emita outra. Não
existe rotação automática.

---

## 8. Seus dados

- **Diagnóstico gratuito do site** (o de `/diagnostico`, sem cadastro): o XML é
  processado em memória e descartado; nada é gravado. Política publicada em
  **https://tribultz.com.br/data-policy**.
- **Dentro da plataforma**, com a sua conta: os documentos são armazenados,
  isolados por empresa, e retidos por **365 dias**, quando são expurgados.
- **Links de download** de documento expiram em **15 minutos** — se um link
  parar de funcionar, basta gerar novamente na tela.
- **LGPD:** em **Configurações → Meus Dados** você consulta e solicita exclusão.
  Encarregado de dados: **dpo@tribultz.com.br**.

---

## 9. Suporte

| Canal | Quando usar |
|---|---|
| **Suporte** no menu (dentro da plataforma) | chamado técnico com histórico rastreável |
| **contato@tribultz.com.br** | qualquer assunto, inclusive antes de conseguir entrar |
| **WhatsApp (51) 99188-1026** | urgência e dúvidas rápidas |
| **https://tribultz.com.br/contato** | canais abertos, sem precisar estar logado |

Como Founding Partner, seu retorno tem prioridade na nossa fila de produto — é
literalmente por isso que o Programa existe. Divergência de regra fiscal,
resultado que você acha errado ou tela que não faz o que promete: mande. Achado
de cliente do Programa entra na fila de correção junto dos nossos próprios.

---

## 10. Perguntas que costumam aparecer

**Preciso de cartão de crédito?**
Não. O acesso do Programa não passa por cobrança.

**O que acontece quando a vigência termina?**
A Tribultz procura você antes disso. Nada é apagado no vencimento; o acesso passa
a se comportar como conta sem plano ativo até a definição da continuidade.

**Posso convidar alguém da minha equipe?**
Na versão atual, não pela tela — o convite de usuário adicional é feito por nós.
Peça pelos canais de suporte.

**O laudo serve como prova em autuação?**
O relatório traz data e hora, identificação do arquivo, regra aplicada e base
legal, e o PDF é exportável para o seu processo de auditoria. Não substitui
parecer do seu contador; serve para embasá-lo.

**A validação garante que a nota será aceita?**
A validação confere sua nota contra as regras publicadas nas Notas Técnicas
vigentes. É uma verificação determinística e auditável, não uma garantia emitida
pela SEFAZ — quem autoriza a nota é o fisco.

**A quantidade de regras muda?**
Sim, e é o ponto. A Reforma está em construção: as Notas Técnicas mudam com
frequência, e o motor acompanha. Quando uma regra entra, muda de data ou é
suspensa, isso aparece em **https://tribultz.com.br/changelog**.

---

## Onde encontrar cada coisa

| | |
|---|---|
| Entrar | https://tribultz.com.br/login |
| Trocar a senha | https://tribultz.com.br/settings → seção "Senha" |
| Recuperar senha | https://tribultz.com.br/login → "Esqueci minha senha" |
| Contato aberto | https://tribultz.com.br/contato |
| Novidades da plataforma | https://tribultz.com.br/changelog |
| Política de dados | https://tribultz.com.br/data-policy |
| Diagnóstico sem cadastro | https://tribultz.com.br/diagnostico |

*Tribultz é uma marca 6tech. Dúvidas sobre este manual: contato@tribultz.com.br*
