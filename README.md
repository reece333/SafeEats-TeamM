# SafeEats

SafeEats is an open-source web application that helps users find allergy-friendly restaurants and dishes, based on their specific dietary needs and preferences. Users can find restaurants in a specific location, filter by food preferences or allergens, and save their preferences to their profile.

This repository contains the source code for the SafeEats restaurant web application, which is where restaurants’ menu data gets added to the application. For the user-side web application, see https://github.com/SafeEats-TeamH-Spring-2024-COMP-523/SafeEatsH 

## Features
* User account creation and authentication.
* Restaurant creation, including restaurant name, address, description, phone number, and cuisine type.
* Menu item creation, including item name, description, price, automatic ingredient-list parsing for allergens, and manual allergen checkoff. 
* Menu item management, which allows users to edit and delete menu items.

## Prerequisites

- Python **3.12** only for local development. Do **not** use **3.14** (see backend setup below).
- Node.js and npm (see [https://nodejs.org/](https://nodejs.org/))
- Git
- Firebase **Blaze (pay-as-you-go)** if you need **menu or restaurant image uploads**: Cloud Storage requires a Blaze plan. Without it, uploads often fail with unclear errors. See [Firebase pricing](https://firebase.google.com/pricing).

## Clone the repository

```bash
git clone https://github.com/reece333/SafeEats-TeamM.git
cd SafeEats-TeamM
```

Use your fork’s URL if you forked the project.

## Setting up environment variables

Get a populated `.env` from **whoever maintains this project**, **or** build your own:

1. Follow **[Firebase setup](#firebase-setup)** below.
2. Copy [backend/app/.env.example](backend/app/.env.example) to `backend/app/.env` and fill in values (that file lists every variable the backend uses).

If someone shares a `.env` with you and email renamed it, rename it back so the file is exactly `.env` inside `backend/app/`.

```bash
cp backend/app/.env.example backend/app/.env   # macOS / Linux
```

```powershell
Copy-Item backend\app\.env.example backend\app\.env   # Windows PowerShell
```

The app loads `.env` from `backend/app/` when you run the backend from that directory.

## Firebase setup

Use one Firebase project for development (and deployment secrets on Render, if applicable).

- Enable **Realtime Database** and set **`DATABASE_URL`** to your database URL (see `.env.example`).
- Create a **service account** with access to your project, download the JSON key, and put the **entire JSON as a single-line string** in **`FIREBASE_CREDENTIALS`** in `.env` (see `.env.example`).
- For image uploads: enable **Cloud Storage**, note the default bucket name (often `your-project-id.appspot.com`), and set **`FIREBASE_STORAGE_BUCKET`** in `.env`. Image upload features depend on Storage; **Storage on Firebase requires the Blaze plan**. Without Blaze, expect failures when testing uploads.

Full variable names and placeholders are in [backend/app/.env.example](backend/app/.env.example).

## Setting up the backend

> **Python version matters.** This project targets Python **3.12** (see [backend/runtime.txt](backend/runtime.txt)). **Avoid Python 3.14.** Wheels for `pydantic-core` are not reliable there yet, and you may see `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.

Python dependencies are listed only in **[backend/requirements.txt](backend/requirements.txt)**. Run all `pip` commands from the **`backend/`** directory.

[backend/app/main.py](backend/app/main.py) uses flat imports (`from routes import router`), so **start uvicorn from inside `backend/app/`** after activating the venv under `backend/`.

#### 1. Create and activate a virtual environment

On Windows, check installed interpreters with `py -0`. If 3.12 is missing, install it from [python.org/downloads](https://www.python.org/downloads/). On macOS or Linux, use `python3.12 --version` or `python3 --version` after installing 3.12.

```bash
cd backend
```

Create the venv against Python 3.12. If you already have a broken `.venv`, delete it first (`rm -rf .venv` on Unix; remove the `.venv` folder on Windows).

**Windows (recommended: targets 3.12 explicitly)**

```bash
py -3.12 -m venv .venv
```

**macOS / Linux**

```bash
python3.12 -m venv .venv
```

If `python3.12` is not on your PATH but 3.12 is your default `python3`, use `python3 -m venv .venv`.

Activate the venv:

| Environment | Command |
|-------------|---------|
| macOS / Linux | `source .venv/bin/activate` |
| Windows Git Bash | `source .venv/Scripts/activate` |
| Windows PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |

Sanity check: `python --version` should print **3.12.x**.

```bash
python --version
```

#### 2. Install dependencies

```bash
pip install -r requirements.txt
```

If pip warns you to upgrade and refuses with `ERROR: To modify pip...`, that is a Windows quirk. Pip cannot overwrite its own executable while running. Either ignore it (pip 24.x is fine for this project) or run:

```bash
python -m pip install --upgrade pip
```

#### 3. Run the development server

```bash
cd app
uvicorn main:app --reload
```

The API runs at [http://localhost:8000](http://localhost:8000).

If you see `uvicorn: command not found` even with the venv active, the launcher shim may be missing. Use the module form:

```bash
python -m uvicorn main:app --reload
```

Or reinstall uvicorn: `pip install --force-reinstall --no-deps uvicorn==0.22.0`.

## Running the application

Use **two terminals**: **uvicorn** for the backend and **npm** for the frontend.

**Terminal 1 (backend)** (venv created and dependencies installed as above):

```bash
cd backend
source .venv/bin/activate              # macOS / Linux
# source .venv/Scripts/activate        # Windows Git Bash
# .\.venv\Scripts\Activate.ps1         # Windows PowerShell
# .venv\Scripts\activate.bat           # Windows cmd
cd app
uvicorn main:app --reload
```

**Terminal 2 (frontend):**

```bash
cd frontend
npm install                 # first time only
npm start
```

The web app serves at [http://localhost:3000](http://localhost:3000). Keep both processes running while developing.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.** Your venv is likely on Python 3.14. Recreate it with Python 3.12, for example: `deactivate`, remove `.venv`, then `py -3.12 -m venv .venv` (Windows) or `python3.12 -m venv .venv` (macOS/Linux), activate, and `pip install -r requirements.txt` again from `backend/`.
- **`uvicorn: command not found`** (with `(.venv)` active). Run `python -m uvicorn main:app --reload` from `backend/app`, or `pip install --force-reinstall --no-deps uvicorn==0.22.0`.
- **`ModuleNotFoundError: No module named 'routes'`.** You started uvicorn from the wrong directory. `cd backend/app` first, then run uvicorn.
- **`ERROR: To modify pip, please run...`.** Use `python -m pip install --upgrade pip`, or skip the upgrade.
- **Firebase / startup errors.** Confirm `backend/app/.env` exists, `FIREBASE_CREDENTIALS` is valid JSON (often one line in the env file), and `DATABASE_URL` matches your Firebase Realtime Database URL.
- **Image upload / Storage errors.** Set **`FIREBASE_STORAGE_BUCKET`** to your Cloud Storage bucket and confirm the Firebase project is on the **Blaze** plan (Storage requires it).
- **Other missing packages.** `pip install <package-name>` inside the activated venv, and consider adding the dependency to [backend/requirements.txt](backend/requirements.txt).

## Deployment
The app is deployed at https://safeeats-teamm.onrender.com. It may take several minutes for the backend to boot up after accessing the site, as we are on the free plan. We made two separate deployments for the project. One runs the backend and the other runs the frontend. I would recommend forking the repository, adding the .env values into Render, then making sure you’re in the correct directories when you install the dependencies for the frontend and the backend. Otherwise, you install and run the build similar to how you run it in your local environment. See the Render documentation for more details. https://render.com/docs

Adapted from https://github.com/SafeEats-TeamH-Spring-2024-COMP-523/SafeEatsH 
