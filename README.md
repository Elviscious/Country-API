# 🌍 Country currency and exchange API

## 🌟 Project Overview

This is a **FastAPI** application designed to serve cached and processed country data. It aggregates information from external sources (country details and exchange rates) into an internal PostgreSQL database, allowing for fast retrieval, filtering, and analysis (such as estimated GDP calculation). It also generates a summary image of the cache status and top economic performers.

### 🔑 Key Features:

- **Data Refresh:** Programmatically fetch, process, and cache country and currency data.
- **Data Persistence:** Uses **SQLAlchemy** with **PostgreSQL** to store and manage data.
- **Filtering & Sorting:** API endpoints support filtering by region/currency and sorting by name/estimated GDP.
- **Status Image Generation:** Creates a PNG image summarizing the database status and top 5 countries by estimated GDP.
- **Robust Error Handling:** Provides clear JSON responses for validation, not-found errors, and external service outages.

---

## 💻 Setup and Installation

### 1\. Prerequisites

Ensure you have the following installed:

- **Python 3.9+**
- **pip** (Python package installer)
- A running **PostgreSQL** database instance.

### 2\. Clone the Repository and Install Dependencies

```bash
# Clone the repository (replace with your actual URL if needed)
git clone <repository-url>
cd <project-directory>

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # On Windows, use: .\venv\Scripts\activate

# Install all required Python packages
# (fastapi, uvicorn, sqlalchemy, psycopg2-binary, python-dotenv, requests, Pillow)
pip install -r requirements.txt
```

### 3\. Configure Environment Variables

Create a file named **`.env`** in the root directory of the project to store your database connection string.

**`.env` Example:**

```
DATABASE_URL="postgresql+psycopg2://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>"
```

- **Example Local URL:** `postgresql+psycopg2://postgres:mysecretpassword@localhost:5432/country_db`

---

## ▶️ Running Locally

### 1\. Start the Server

Run the application using Uvicorn. The `--reload` flag enables live code changes.

```bash
uvicorn main:app --reload
```

The application will be accessible at `http://127.0.0.1:8000`.

### 2\. Initialize the Database and Cache Data (Crucial Step)

The database tables are created on startup, but they are initially empty. You **must** run the refresh endpoint once to populate the database and generate the summary image.

**Call this endpoint via cURL, a browser, or an API client:**

```bash
curl -X POST http://127.0.0.1:8000/countries/refresh
```

A successful response indicates that the database has been populated and the summary image (`cache/summary.png`) has been created.

---

## 📘 API Reference

All endpoints are hosted at the base URL, e.g., `http://127.0.0.1:8000`.

### 1\. Status and Data Refresh

| Method | Endpoint             | Description                                                      | Success Response                                                                               |
| :----- | :------------------- | :--------------------------------------------------------------- | :--------------------------------------------------------------------------------------------- |
| `POST` | `/countries/refresh` | Fetches, processes, and caches data from external sources.       | `200 OK` + `{"message": "...", "last_refreshed_at": "YYYY-MM-DDTHH:MM:SS.ffffff+00:00"}`       |
| `GET`  | `/status`            | Returns the count of cached countries and the last refresh time. | `200 OK` + `{"total_countries": 250, "last_refreshed_at": "YYYY-MM-DDTHH:MM:SS.ffffff+00:00"}` |
| `GET`  | `/countries/image`   | Returns the cached summary image (`cache/summary.png`).          | `200 OK` + `image/png` (FileResponse)                                                          |

### 2\. Country Operations (Read, Query, and Delete)

| Method   | Endpoint                    | Description                                                        | Query Parameters (Optional)                                                                                          | Error Responses   |
| :------- | :-------------------------- | :----------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------- | :---------------- |
| `GET`    | `/countries`                | Returns a list of countries, with optional filtering/sorting.      | `region` (e.g., `Africa`), `currency` (e.g., `NGN`), `sort` (one of: `name_asc`, `name_desc`, `gdp_asc`, `gdp_desc`) | `400 Bad Request` |
| `GET`    | `/countries/{country_name}` | Retrieves details for a single country by name (case-insensitive). | None                                                                                                                 | `404 Not Found`   |
| `DELETE` | `/countries/{country_name}` | Deletes a country record by name (case-insensitive).               | None                                                                                                                 | `404 Not Found`   |

### 💡 Example Query

To get all African countries sorted by estimated GDP (descending):

```
GET http://127.0.0.1:8000/countries?region=Africa&sort=gdp_desc
```

### 🚨 Standard Error Format

| HTTP Status                 | JSON Detail                                                       |
| :-------------------------- | :---------------------------------------------------------------- |
| **400 Bad Request**         | `{"error": "Validation failed", "details": "..."}`                |
| **404 Not Found**           | `{"error": "Country not found"}`                                  |
| **503 Service Unavailable** | `{"error": "External data source unavailable", "details": "..."}` |
