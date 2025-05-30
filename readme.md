# Model Database

This repository contains a set of Python scripts and a simple Firebase-powered frontend for scraping and managing data from agency websites.

## 🔍 Purpose

This project automates the process of gathering and maintaining a database of models listed online. It:

- Scrapes key model data (name, profile URL, images, measurements, availability).
- Stores the information in a **Cloud Firestore** database.
- Tracks and logs additions and removals over time.
- Provides a web-based admin console to monitor scrape logs and view summary stats.

## 🛠 Structure

```
/
├── scrapers/
│   ├── viviens_women.py          # Scrapes the women's mainboard
│   ├── viviens_men.py            # Scrapes the men's board
│
├── public/
│   ├── index.html                # Main interface (search, gallery, etc.)
│   ├── admin.html                # Admin interface to view scrape logs
│   ├── script.js                 # Frontend logic
│   ├── style.css                 # Styling
│
├── .github/workflows/
│   └── scrape.yml                # GitHub Actions workflow to run the scrapers on schedule or manually
│
├── serviceAccount.json          # Firebase service account (not committed in production)
├── README.md
```

## 🔗 Technologies

- **Python** (Playwright, Firebase Admin SDK)
- **Firebase** (Firestore, Hosting)
- **GitHub Actions** for automation
- **HTML/CSS/JavaScript** frontend

## ⚙️ Automation

GitHub Actions (`scrape.yml`) runs the scrapers and logs:

- Models added or removed from each board
- Failures (with error messages)
- Timestamps for each scrape

These logs are saved in the `scrape_logs` collection in Firestore and displayed in the admin console.

## 🔐 Secrets & Environment

- Firebase Admin SDK key is stored as a GitHub secret (`FIREBASE_SERVICE_ACCOUNT_BASE64`).
- The frontend uses Firebase config variables embedded in `index.html` and `admin.html`.

## 📊 Admin Console

Open `public/admin.html` locally or via Firebase Hosting to:

- View scrape history
- See which board was scraped
- See how many models were added/removed
- Hover over errors for full failure messages

## ✅ Status

- ✔ Women’s board scrape and logging
- ✔ Men’s board scrape and logging
- ✔ Realtime model count in frontend
- ✔ Failure detection and reporting
- ✔ Firestore sync + cleanup
- 🔜 Additional agency support (future)

## 🚀 Hosting

This project is designed to be deployed using Firebase Hosting. Run the following to preview locally:

```bash
firebase emulators:start
```

Or deploy:

```bash
firebase deploy
```


## View live
[Model Gallery](https://jessemorley.github.io/agency-scraper/)
[Logs](https://jessemorley.github.io/agency-scraper/admin.html)