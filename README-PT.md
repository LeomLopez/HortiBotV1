# 📦 Bot de Controle de Estoque – Telegram

Sistema de controle de estoque via **Telegram**, desenvolvido em **Python**, com foco em **validade, FIFO e rastreabilidade**, aplicado em ambiente real (restaurante).

Mais do que um bot, o projeto funciona como uma **camada de captura de dados operacionais**, preparando informações confiáveis para **análise de consumo, otimização de compras e modelos preditivos**.

---

## 🎯 Problema

Em operações de cozinha e restaurante, o controle de estoque costuma ser:

- manual ou baseado em planilhas paralelas
- sujeito a erro humano
- sem rastreabilidade por lote e validade
- difícil de transformar em dados analisáveis

Essas limitações geram desperdício, decisões de compra imprecisas e dados históricos pouco confiáveis.

---

## ✅ Solução

Um bot acessível pelo **Telegram** que permite:

- registrar entradas e saídas em tempo real
- controlar validade por lote
- aplicar lógica FIFO
- separar o estoque por setor
- gerar um histórico completo de movimentações

Tudo isso **sem necessidade de aplicativo próprio**, utilizando uma ferramenta já conhecida pela equipe.

---

## ⚙️ Funcionalidades principais

- 📥 Entrada de produtos por setor
- 📤 Saída com validações de estoque e unidade
- 🛠️ Ajuste de lote (correção de erro humano)
- 🗑️ Descarte manual
- ⚠️ Consulta de itens vencidos por setor
- 📦 Consulta de estoque (FIFO / visão compacta)
- ❄️ Controle de congelados por contêiner (C1, C2, C3)
- 🔎 Busca por produto, setor ou contêiner
- 📊 Histórico completo de movimentações

---

## 🧠 Decisões de design importantes

- ❌ Sem descarte automático  
  → o sistema informa, mas a decisão operacional permanece humana

- 🔒 Ajuste apenas total  
  → evita distorções nos dados analíticos

- 📊 Ajustes não entram nas análises de consumo  
  → garante dados reais e limpos

Essas decisões priorizam **qualidade e confiabilidade dos dados**, não apenas automação.

---

## 🏗️ Arquitetura (resumo)

- **Interface:** Telegram Bot
- **Backend:** Python
- **Banco de dados:** PostgreSQL
- **Modelo:** registro de movimentos + estado atual do estoque
- **Persistência:** histórico completo (não destrutivo)

---

## 📁 Estrutura do projeto

telegram-inventory-bot/
├── controllers/
├── models/
├── views/
├── docs/
│ └── Manual_Bot_Estoque_Telegram.pdf
├── main.py
├── README.md
└── README_PT.md

---

## 📄 Documentação

📘 Manual do usuário (PDF):  
👉 `docs/Manual_Bot_Estoque_Telegram.pdf`

O manual foi escrito para usuários operacionais (estoque e cozinha), com exemplos reais de uso.

---

## 📈 Próximos passos (roadmap)

- Resumo diário automático de vencimentos
- Relatórios por setor e período
- Extração de dados para análise estatística
- Modelos preditivos de consumo
- Painel administrativo (dashboard)

---

## 👤 Autor

Projeto desenvolvido por **Leomar Lopez**  
Perfil voltado à **Análise de Dados e Engenharia de Software**, com interesse em transformar operações logísticas reais em dados acionáveis para apoiar decisões baseadas em dados.

---

## 📌 Observação final

Este projeto foi utilizado como **base para estudo e aplicação prática** de:

- controle de estoque
- qualidade de dados
- modelagem para análise futura

Não é apenas um bot, mas um **sistema de coleta de dados operacionais reais**.
