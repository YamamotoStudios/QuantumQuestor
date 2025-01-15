
# Quantum Questor: Keyword and Article Generation System

Welcome to the **Quantum Questor** repository! This project is the heart of an automated keyword and content generation system designed to support the **Quantum Questor** website. The goal is to efficiently generate trend-reactive keywords and articles tailored to gaming, technology, and lifestyle topics.

## 📚 Project Overview

This repository is structured as a **monorepo**, containing all components of the Quantum Questor system:
- **Keyword Generator**: Generates keywords using APIs like RapidAPI's Google Keyword Insight.
- **Database Setup**: Manages the schema and storage for keyword and article data.
- **API Integration**: Handles external API connections and integrations.
- **Article Generation**: Uses OpenAI's GPT APIs to draft articles from the generated keywords.
- **Shared Utilities**: Common scripts and utilities to streamline development.

---

## 🚀 Features

### 1. **Keyword Generation**
- Fetches trending keywords using external APIs.
- Filters based on volume, competition, and relevance.
- Employs semantic similarity analysis to refine keywords.
- Configurable blacklist and intent patterns for enhanced customization.

### 2. **Database Setup**
- Schema designed to store keywords, metadata, and generated articles.
- JSON-based storage for flexibility and scalability.

### 3. **Content Generation**
- Uses OpenAI GPT APIs to draft high-quality articles from selected keywords.
- Configurable models (e.g., GPT-3.5 Turbo, GPT-4o Mini) for optimal cost-quality balance.

### 4. **Automation**
- Integrated with CI/CD pipelines for automated keyword fetching, article generation, and deployment.

---

## 🛠️ Repository Structure

```plaintext
/quantum-questor
├── /keyword_generator    # Keyword generation scripts and logic
├── /db_setup             # Database schema and migration scripts
├── /api_integration      # API wrappers and integration logic
├── /article_generation   # Article drafting and content management
├── /shared_libraries     # Shared utilities and helper scripts
├── /docs                 # Documentation and guides
└── /tests                # Unit and integration tests
```

---

## 🏗️ Setup and Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/quantum-questor.git
   cd quantum-questor
   ```

2. **Install Dependencies**
   - Python dependencies:
     ```bash
     pip install -r requirements.txt
     ```

3. **Environment Configuration**
   - Create a `.env` file with the following:
     ```env
     RAPIDAPI_KEY=<your-rapidapi-key>
     OPENAI_API_KEY=<your-openai-api-key>
     ```

4. **Run the System**
   - Fetch keywords:
     ```bash
     python keyword-generator/fetch_keywords.py
     ```
   - Generate articles:
     ```bash
     python article-generation/generate_articles.py
     ```

---

## 🌐 APIs Used

- **[RapidAPI Google Keyword Insight](https://rapidapi.com/)**: For keyword discovery and trend analysis.
- **[OpenAI GPT APIs](https://openai.com/)**: For generating high-quality articles.

---

## 🗃️ Database Schema

### Keywords Table
| Column          | Type   | Description                         |
|------------------|--------|-------------------------------------|
| `id`            | UUID   | Unique identifier for the keyword   |
| `text`          | String | Keyword text                        |
| `volume`        | Int    | Search volume                       |
| `trend`         | Float  | Trend percentage                    |
| `competition`   | String | Competition level (`low`, `high`)   |
| `created_at`    | Date   | Timestamp of entry creation         |

### Articles Table
| Column          | Type   | Description                         |
|------------------|--------|-------------------------------------|
| `id`            | UUID   | Unique identifier for the article   |
| `title`         | String | Article title                       |
| `content`       | Text   | Generated article content           |
| `keywords`      | JSON   | Associated keywords                 |
| `created_at`    | Date   | Timestamp of entry creation         |

---

## 🤝 Contributing

We welcome contributions to the Quantum Questor system! Here's how you can help:
1. Fork the repository.
2. Create a new feature branch: `git checkout -b feature-name`.
3. Commit your changes: `git commit -m 'Add some feature'`.
4. Push the branch: `git push origin feature-name`.
5. Open a pull request.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🧠 Future Enhancements

- Integration of GPT-4o Mini for improved article quality.
- Advanced trend analysis and prediction algorithms.
- Comprehensive analytics dashboard.

---

## 📬 Contact

For inquiries or support, please email **contact@quantumquestor.com** or visit our website at [Quantum Questor](https://www.quantumquestor.com).

---

### ⭐ If you find this project useful, please consider starring this repository!
```
