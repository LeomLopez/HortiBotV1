# 📦 Telegram Inventory Control Bot

A **Telegram-based inventory control system** developed in **Python**, focused on **product expiration, FIFO logic, and data quality**, designed and used in a real restaurant environment.

More than a chatbot, this project acts as an **operational data capture layer**, generating clean and reliable data for **consumption analysis, process optimization, and future predictive models**.

🇧🇷 Portuguese version: `README_PT.md`

---

## 🎯 Problem

In many restaurant and kitchen operations, inventory control is usually:

- manual or spreadsheet-based
- prone to human error
- lacking batch and expiration traceability
- difficult to transform into analyzable data

These limitations lead to waste, poor purchasing decisions, and unreliable historical data.

---

## ✅ Solution

A lightweight inventory system operated entirely via **Telegram**, allowing teams to:

- register product entries and exits in real time
- control expiration dates per batch
- apply FIFO logic naturally
- separate inventory by sector (produce, frozen, dry goods, etc.)
- maintain a full, non-destructive movement history

All of this **without requiring a dedicated app**, using a tool already familiar to the team.

---

## ⚙️ Main Features

- 📥 Product entry by sector
- 📤 Product exit with stock and unit validation
- 🛠️ Batch adjustment (human error correction)
- 🗑️ Manual discard registration
- ⚠️ Expired items listing by sector
- 📦 Inventory view (FIFO / compact view)
- ❄️ Frozen products control by container (C1, C2, C3)
- 🔎 Search by product, sector, or container
- 📊 Complete movement history

---

## 🔘 Button Workflow

The bot includes an interactive Telegram button menu to reduce typing errors and guide the operator through the daily workflow.

Main sector buttons:

- 🥕 HortiFruti
- ❄️ Frozen products
- 📦 Dry goods
- 🧪 Chemical stock
- 🧻 Disposable stock

Subsector and container buttons:

- 🥬 Vegetables
- 🍎 Fruits
- 🧀 Dairy
- 🧊 Picking
- 📦 C1, C2, C3

Action buttons available after selecting a sector:

- 📦 View stock
- 🔎 Search
- ➕ Entry
- ➖ Exit
- ↩️ Return from production
- 🔁 Move batch
- 🛠 Adjustment
- 📋 List expired items for discard
- 🗑 Discard
- ♻️ Supplier return
- ⬅️ Back

Operations entered through buttons are reviewed before saving. The operator must tap **✅ Confirm** to record the movement or **❌ Cancel** to discard the pending operation.

---

## 🧠 Key Design Decisions

- ❌ No automatic discarding  
  → the system informs; operational decisions remain human

- 🔒 Adjustments must remove the entire batch  
  → prevents partial corrections that distort analytical data

- 📊 Adjustments are excluded from consumption analysis  
  → ensures clean, real consumption metrics

These decisions prioritize **data reliability over blind automation**.

---

## 🏗️ Architecture Overview

- **Interface:** Telegram Bot
- **Backend:** Python
- **Database:** PostgreSQL
- **Data model:** Movement-based logging + current stock state
- **Persistence:** Full historical record (non-destructive)

---

## 📁 Project Structure

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

## 📄 Documentation

📘 User Manual (Portuguese – PDF):  
`docs/Manual_Bot_Estoque_Telegram.pdf`

The manual is written for **non-technical operational users** (kitchen and inventory staff), with real usage examples.

---

## 📈 Roadmap

- Daily automated expiration summary
- Sector-based reports
- Data export for statistical analysis
- Consumption prediction models
- Administrative dashboard

---

## 👤 Author

Developed by **Leomar Lopez**  
Profile focused on **Data Analysis and Software Engineering**, with interest in turning real logistical operational processes into actionable data.

---

## 📌 Final Note

This project was built as a **real-world operational system**, not a demo.

Its main value lies in:

- data integrity
- traceability
- analytical readiness

The bot is a means — **the data is the real asset**.
